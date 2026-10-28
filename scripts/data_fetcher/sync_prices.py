#!/usr/bin/env python3
"""
价格增量同步（state 记账版 v2）

核心规则（与用户确认的口径一致）：
- 只管近一个月：任务集 = 两系列中 end_date >= now-31天 的所有 yes_token
  （Polymarket 官方 API 的 1min 历史价格只保留近一个月）
- 价格起点：事件 start_date 前 1 小时；终点不设死
- 市场完成判定（满足任一即标 complete，之后永不重扫）：
  1) 最终价 >= 0.9995 或 <= 0.0005（含极个别 0.995 收尾的会在规则 2 兜住）
  2) 市场已结束（closed 或 超过 end_date+6h）且探测已越过 end_date+6h 仍无新价格
- 增量起点 = 上次探测终点 - 30 分钟（向前覆盖，确保无缝隙）
- 单次请求窗口 <= 1 天（API 对 1min 粒度的限制），按天切块
- 每次探测的终点记账到 price_sync_state.last_probe_ts，作为下次的增量起点

用法:
    python scripts/data_fetcher/sync_prices.py                # 正常增量
    python scripts/data_fetcher/sync_prices.py --dry-run      # 只打印任务清单，不请求
    python scripts/data_fetcher/sync_prices.py --full         # 忽略 complete 标记全量重扫近31天
    python scripts/data_fetcher/sync_prices.py --limit-markets 5
"""

import sys
import argparse
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_fetcher.config import DB_PATH, CLOB_BASE
from scripts.data_fetcher.http_client import get_json

# ===== 可调参数 =====
GRACE_SECONDS = 6 * 3600      # 结束后宽限期 6h
OVERLAP_SECONDS = 30 * 60     # 增量起点向前覆盖 30 分钟
DAY_SECONDS = 86400
PRICE_HI = 0.9995
PRICE_LO = 0.0005
RECENT_DAYS = 31              # 只管近一个月
START_OFFSET = 3600           # 价格起点 = 事件 start_date 前 1h
SERIES_IDS = (10000, 10816)
SERIES_SLUGS = ('elon-tweets', 'elon-tweets-48h')


def parse_iso_z(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
    except ValueError:
        return None


def fetch_chunk(token_id: str, start_ts: int, end_ts: int) -> list[dict]:
    """拉一段 1min 价格，失败抛 RuntimeError（由上层计数重试）。"""
    params = {'market': token_id, 'fidelity': 1,
              'startTs': int(start_ts), 'endTs': int(end_ts)}
    data = get_json(f"{CLOB_BASE}/prices-history", params,
                    max_retries=4, base_delay=1.5, timeout=30)
    if isinstance(data, dict):
        return data.get('history', []) or []
    return []


def save_prices_bulk(conn: sqlite3.Connection, token_id: str, market_id: str,
                     history: list[dict]) -> int:
    """批量插入价格（INSERT OR IGNORE 去重），复用外部连接。"""
    if not history:
        return 0
    data = []
    for point in history:
        ts = point.get('t')
        price = point.get('p')
        if ts is None or price is None:
            continue
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        data.append((token_id, market_id, float(price), int(ts), dt_utc))
    if not data:
        return 0
    conn.executemany(
        'INSERT OR IGNORE INTO prices (token_id, market_id, price, timestamp_unix, timestamp_utc) '
        'VALUES (?, ?, ?, ?, ?)', data)
    conn.commit()
    return len(data)


def build_tasks(conn: sqlite3.Connection) -> list[dict]:
    """任务集：两系列近 31 天结束（或未结束）事件的所有 yes_token。"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')
    rows = conn.execute('''
        SELECT m.id, m.yes_token_id, m.closed, m.end_date,
               e.id, e.start_date, e.end_date, e.closed
        FROM markets m
        JOIN events e ON m.event_id = e.id
        WHERE m.yes_token_id IS NOT NULL
          AND (e.series_id IN (?, ?) OR e.series_slug IN (?, ?))
          AND (e.end_date IS NULL OR e.end_date >= ?)
        ORDER BY e.start_date, m.id
    ''', (*SERIES_IDS, *SERIES_SLUGS, cutoff)).fetchall()
    return [
        {'market_id': r[0], 'token': r[1], 'm_closed': r[2], 'm_end': r[3],
         'event_id': r[4], 'e_start': r[5], 'e_end': r[6], 'e_closed': r[7]}
        for r in rows
    ]


def decide_complete(m_closed, end_ts, last_ts, probe_end, final_price, now_ts):
    """完成判定。返回 (complete, reason)。"""
    # 规则 1：最终价已到极端
    if final_price is not None and (final_price >= PRICE_HI or final_price <= PRICE_LO):
        return True, 'price-extreme'
    if end_ts is None:
        return False, None
    grace_ts = end_ts + GRACE_SECONDS
    # 市场是否已结束（closed 或 超过宽限期）
    settled = (m_closed == 1) or (now_ts > grace_ts)
    if not settled:
        return False, None
    # 规则 2a：市场已 closed，且最后价格在宽限期之后（closed 后不会再有新价）
    if (m_closed == 1 and last_ts is not None and last_ts > grace_ts
            and probe_end is not None and probe_end >= last_ts):
        return True, 'closed-with-past-grace-price'
    # 规则 2b：探测已越过宽限期，但最后价格停在宽限期内（之后无新价）
    if (probe_end is not None and probe_end >= grace_ts
            and (last_ts is None or last_ts <= grace_ts)):
        return True, 'settled-no-new-price'
    # 其余情况（如未 closed 但宽限期后仍在交易）：保持增量采集，直到满足上述规则
    return False, None


def process_token(conn, task, state, full, now_ts, request_delay) -> dict:
    """处理单个 token，返回结果摘要 dict。"""
    token = task['token']
    market_id = task['market_id']
    m_end = parse_iso_z(task['m_end']) or parse_iso_z(task['e_end'])
    e_start = parse_iso_z(task['e_start'])
    first_ts = (e_start - START_OFFSET) if e_start else None
    out = {'market_id': market_id, 'token': token, 'inserted': 0,
           'complete': 0, 'reason': None, 'status': 'ok',
           'last_ts': None, 'probe_end': None}

    # ---- 本地状态（state 缺失时从 prices 现算，存量 token 首次入账）----
    last_ts = state['last_ts'] if state else None
    last_probe = state['last_probe_ts'] if state else None
    complete = bool(state['complete']) if state else False
    if last_ts is None:
        row = conn.execute(
            'SELECT MAX(timestamp_unix) FROM prices WHERE token_id = ?', (token,)).fetchone()
        last_ts = row[0] if row else None

    if complete and not full:
        out['status'] = 'skip-complete'
        out['complete'] = 1
        return out

    # 事件还没开盘，没东西可采
    if first_ts is not None and first_ts > now_ts:
        out['status'] = 'skip-future'
        return out

    # ---- 采集窗口 ----
    if full:
        start = first_ts
    elif last_probe is not None:
        start = max(first_ts or 0, last_probe - OVERLAP_SECONDS)
    elif last_ts is not None:
        start = last_ts - OVERLAP_SECONDS
    else:
        start = first_ts

    if start is None:
        out['status'] = 'skip-no-start'
        return out
    if start >= now_ts:
        out['status'] = 'skip-up-to-date'
        out['last_ts'] = last_ts
        out['probe_end'] = last_probe
        return out

    # ---- 按天切块拉取 ----
    points = []
    empty_streak = 0
    cursor = int(start)
    probe_end = cursor
    error = None
    while cursor < now_ts:
        chunk_end = min(cursor + DAY_SECONDS, now_ts)
        try:
            hist = fetch_chunk(token, cursor, chunk_end)
        except RuntimeError as e:
            error = str(e)[:120]
            probe_end = cursor          # 失败段不记账，下次从这重试
            break
        if hist:
            points.extend(hist)
            empty_streak = 0
        else:
            empty_streak += 1
        cursor = chunk_end
        probe_end = cursor
        # 全新 token 连续两天无数据且从未有过价格：提前止损
        if last_ts is None and not points and empty_streak >= 2:
            break
        # 已越过 end+6h 宽限期且本次一个点都没采到：市场已死，完成判定必有结论，停止切块
        # （仍在交易的市场 points 非空，会继续采到 now，不漏数据）
        if m_end is not None and cursor >= m_end + GRACE_SECONDS and not points:
            break
        time.sleep(request_delay)

    inserted = save_prices_bulk(conn, token, market_id, points)
    out['inserted'] = inserted

    # ---- 完成判定 ----
    row = conn.execute(
        'SELECT timestamp_unix, price FROM prices WHERE token_id = ? '
        'ORDER BY timestamp_unix DESC LIMIT 1', (token,)).fetchone()
    new_last_ts, final_price = (row[0], row[1]) if row else (None, None)

    complete, reason = decide_complete(task['m_closed'], m_end, new_last_ts,
                                       probe_end, final_price, now_ts)
    # 全程无数据的死市场：开盘满 24h 仍零数据 → 判完成，不再反复探测
    if not complete and new_last_ts is None:
        eff_first = first_ts or start
        if now_ts > eff_first + DAY_SECONDS:
            complete, reason = True, 'no-data-24h'

    out['complete'] = int(complete)
    out['reason'] = reason
    out['last_ts'] = new_last_ts
    out['probe_end'] = probe_end
    out['status'] = 'error' if error else ('ok' if inserted else 'no-new-data')
    if error:
        out['reason'] = f'partial: {error}'
    return out


def save_state(conn, res: dict, task: dict) -> None:
    conn.execute('''
        INSERT INTO price_sync_state
            (token_id, market_id, last_ts, last_probe_ts, complete, complete_reason, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(token_id) DO UPDATE SET
            market_id = excluded.market_id,
            last_ts = excluded.last_ts,
            last_probe_ts = excluded.last_probe_ts,
            complete = excluded.complete,
            complete_reason = excluded.complete_reason,
            updated_at = excluded.updated_at
    ''', (task['token'], task['market_id'], res['last_ts'], res['probe_end'],
          res['complete'], res['reason'], datetime.now().isoformat()))
    conn.commit()


def fmt_ts(ts):
    if ts is None:
        return '-'
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m-%d %H:%M')


def main():
    parser = argparse.ArgumentParser(description="价格增量同步（state 记账版）")
    parser.add_argument('--full', action='store_true', help='忽略 complete 标记，从事件起点全量重扫')
    parser.add_argument('--dry-run', action='store_true', help='只打印任务清单，不请求')
    parser.add_argument('--limit-markets', type=int, help='限制处理 token 数（调试用）')
    parser.add_argument('--request-delay', type=float, default=0.4)
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--batch-sleep', type=float, default=5.0)
    parser.add_argument('--retry-limit', type=int, default=1)
    parser.add_argument('--db', default=str(DB_PATH), help='数据库路径（测试用）')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    try:
        tasks = build_tasks(conn)
        states = {
            r[0]: {'last_ts': r[1], 'last_probe_ts': r[2], 'complete': r[3]}
            for r in conn.execute(
                'SELECT token_id, last_ts, last_probe_ts, complete FROM price_sync_state')
        }
        print(f'任务集共 {len(tasks)} 个 token（近 {RECENT_DAYS} 天）')
        if args.dry_run:
            done = sum(1 for t in tasks if states.get(t['token'], {}).get('complete'))
            fresh = sum(1 for t in tasks if t['token'] not in states)
            print(f'  已完成（将跳过）: {done}')
            print(f'  未入账（将初始化）: {fresh}')
            print(f'  进行中（增量续采）: {len(tasks) - done - fresh}')
            for t in tasks[:args.limit_markets or 20]:
                st = states.get(t['token'])
                mode = '增量' if st and st['last_probe_ts'] else ('新采' if not st else '跳过(complete)')
                print(f"  [{mode}] 事件 {t['event_id']} 市场 {t['market_id']} "
                      f"end={t['m_end'] or t['e_end']} last_probe={fmt_ts(st['last_probe_ts']) if st else '-'}")
            return 0

        now_ts = int(time.time())
        pending = tasks[:args.limit_markets] if args.limit_markets else tasks

        def run_round(tokens):
            stats = {}
            retry = []
            for idx, t in enumerate(tokens, 1):
                st = states.get(t['token'])
                try:
                    res = process_token(conn, t, st, args.full, now_ts, args.request_delay)
                except Exception as e:
                    print(f"[{idx}/{len(tokens)}] ❌ 市场 {t['market_id']} 异常: {e}")
                    retry.append(t)
                    continue
                save_state(conn, res, t)
                states[t['token']] = {'last_ts': res['last_ts'],
                                      'last_probe_ts': res['probe_end'],
                                      'complete': res['complete']}
                stats[res['status']] = stats.get(res['status'], 0) + 1
                mark = '✅' if res['status'] in ('ok', 'no-new-data', 'skip-complete') else '⚠️'
                print(f"[{idx}/{len(tokens)}] {mark} {res['status']} 市场 {t['market_id']} "
                      f"+{res['inserted']} last={fmt_ts(res['last_ts'])} "
                      f"probe={fmt_ts(res['probe_end'])}"
                      + (f" 完成({res['reason']})" if res['complete'] else ''))
                if res['status'] == 'error':
                    retry.append(t)
                if idx % args.batch_size == 0:
                    print(f"💤 休息 {args.batch_sleep} 秒...")
                    time.sleep(args.batch_sleep)
                else:
                    time.sleep(args.request_delay)
            return stats, retry

        stats, retry = run_round(pending)

        round_n = 1
        while retry and round_n <= args.retry_limit:
            print(f"\n第 {round_n} 次重试，剩余 {len(retry)} 个 token")
            stats2, retry = run_round(retry)
            for k, v in stats2.items():
                stats[k] = stats.get(k, 0) + v
            round_n += 1

        print('\n' + '=' * 60)
        print('🎉 价格同步完成！各状态统计:', stats)
        if retry:
            print(f"⚠️ {len(retry)} 个 token 重试后仍失败（下次运行会自动续采）")
        print('=' * 60)
        return 0
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
