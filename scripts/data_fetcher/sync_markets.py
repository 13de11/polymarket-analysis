#!/usr/bin/env python3
"""
市场增量同步（state 记账版 v2）

逻辑：
- 需要拉市场的事件 = 两系列中满足任一条件者：
  1) end_date >= now - 7 天（进行中/刚结束，可能有新市场或状态翻转）
  2) 事件下还没有任何市场（近 35 天内开始的新事件）
- 每个事件一次 GET /events/{id}，UPSERT 到 markets：
  yes/no_token_id 用 COALESCE 保留旧值，防止 API 摘掉 clobTokenIds 把
  已采到价格的市场变成孤儿
- 不碰 7 天以前的老事件（历史冻结）

用法:
    python scripts/data_fetcher/sync_markets.py
    python scripts/data_fetcher/sync_markets.py --db data/test.db   # 测试库
"""

import sys
import argparse
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_fetcher.config import DB_PATH, GAMMA_BASE
from scripts.data_fetcher.http_client import get_json

SERIES_IDS = (10000, 10816)
SERIES_SLUGS = ('elon-tweets', 'elon-tweets-48h')
RECENT_END_DAYS = 7      # end_date 在此窗口内的事件重拉市场（状态刷新）
FIRST_START_DAYS = 35    # 无市场事件的查找范围（近 35 天开始）


def fetch_markets_by_event(event_id: str) -> list[dict]:
    """拉单个事件的全部市场，失败抛 RuntimeError。"""
    data = get_json(f"{GAMMA_BASE}/events/{event_id}", retries=3, retry_delay=2.0)
    if not isinstance(data, dict):
        return []
    return data.get('markets', []) or []


def parse_outcomes(market: dict) -> tuple[list, str | None, str | None]:
    """解析 outcomes 与 clobTokenIds。"""
    outcomes = market.get('outcomes', [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except json.JSONDecodeError:
            outcomes = []
    raw_tokens = market.get('clobTokenIds', [])
    if isinstance(raw_tokens, str):
        try:
            raw_tokens = json.loads(raw_tokens)
        except json.JSONDecodeError:
            raw_tokens = []
    yes_token = raw_tokens[0] if len(raw_tokens) > 0 else None
    no_token = raw_tokens[1] if len(raw_tokens) > 1 else None
    return outcomes, yes_token, no_token


def upsert_markets(conn: sqlite3.Connection, event_id: str, markets: list[dict]) -> int:
    """批量 UPSERT 一个事件的市场，返回保存条数。"""
    now = datetime.now().isoformat()
    rows = []
    for m in markets:
        outcomes, yes_token, no_token = parse_outcomes(m)
        rows.append((
            m.get('id'), event_id, m.get('question'), m.get('conditionId'), m.get('slug'),
            json.dumps(outcomes, ensure_ascii=False), yes_token, no_token,
            m.get('active') and 1 or 0, m.get('closed') and 1 or 0,
            m.get('endDate'), m.get('startDate'),
            json.dumps(m.get('tags', []), ensure_ascii=False),
            m.get('gameStartTime'), now,
        ))
    if not rows:
        return 0
    conn.executemany('''
        INSERT INTO markets
            (id, event_id, question, condition_id, slug, outcomes,
             yes_token_id, no_token_id, active, closed,
             end_date, start_date, tags, game_start_time, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            event_id = excluded.event_id,
            question = excluded.question,
            condition_id = excluded.condition_id,
            slug = excluded.slug,
            outcomes = excluded.outcomes,
            yes_token_id = COALESCE(excluded.yes_token_id, markets.yes_token_id),
            no_token_id = COALESCE(excluded.no_token_id, markets.no_token_id),
            active = excluded.active,
            closed = excluded.closed,
            end_date = excluded.end_date,
            start_date = excluded.start_date,
            tags = excluded.tags,
            game_start_time = COALESCE(excluded.game_start_time, markets.game_start_time),
            updated_at = excluded.updated_at
    ''', rows)
    conn.commit()
    return len(rows)


def events_to_fetch(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """筛选需要拉市场的事件：近 7 天结束/未结束 + 无市场的近 35 天事件。"""
    cutoff_end = (datetime.now(timezone.utc) - timedelta(days=RECENT_END_DAYS)) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')
    cutoff_start = (datetime.now(timezone.utc) - timedelta(days=FIRST_START_DAYS)) \
        .strftime('%Y-%m-%dT%H:%M:%SZ')
    return conn.execute('''
        SELECT e.id, e.slug
        FROM events e
        WHERE (e.series_id IN (?, ?) OR e.series_slug IN (?, ?))
          AND (
                e.end_date IS NULL
                OR e.end_date >= ?
                OR (e.start_date >= ? AND NOT EXISTS (
                        SELECT 1 FROM markets m WHERE m.event_id = e.id))
              )
        ORDER BY e.start_date
    ''', (*SERIES_IDS, *SERIES_SLUGS, cutoff_end, cutoff_start)).fetchall()


def main():
    parser = argparse.ArgumentParser(description="市场增量同步")
    parser.add_argument('--request-delay', type=float, default=0.4)
    parser.add_argument('--batch-size', type=int, default=20, help='每处理多少个事件休息一次')
    parser.add_argument('--batch-sleep', type=float, default=5.0)
    parser.add_argument('--db', default=str(DB_PATH), help='数据库路径（测试用）')
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    failed = []
    total_saved = 0
    try:
        events = events_to_fetch(conn)
        print(f"共 {len(events)} 个事件需要拉取市场")
        if not events:
            return 0

        for idx, (event_id, event_slug) in enumerate(events, 1):
            short = (event_slug or '')[:60]
            try:
                markets = fetch_markets_by_event(event_id)
            except RuntimeError as e:
                print(f"[{idx}/{len(events)}] ❌ {event_id} ({short}) 拉取失败: {e}")
                failed.append((event_id, event_slug))
                time.sleep(args.request_delay)
                continue

            if not markets:
                print(f"[{idx}/{len(events)}] ⚠️ {event_id} ({short}) 无市场数据")
                failed.append((event_id, event_slug))
            else:
                saved = upsert_markets(conn, event_id, markets)
                total_saved += saved
                print(f"[{idx}/{len(events)}] ✅ {event_id} ({short}) 保存 {saved} 个市场")

            if idx % args.batch_size == 0:
                print(f"💤 休息 {args.batch_sleep} 秒...")
                time.sleep(args.batch_sleep)
            else:
                time.sleep(args.request_delay)

        # 失败事件重试一轮
        if failed:
            print(f"\n重试 {len(failed)} 个失败事件...")
            still_failed = []
            for event_id, event_slug in failed:
                try:
                    markets = fetch_markets_by_event(event_id)
                    if markets:
                        total_saved += upsert_markets(conn, event_id, markets)
                        print(f"  ✅ 重试成功 {event_id}")
                    else:
                        still_failed.append((event_id, event_slug))
                except RuntimeError as e:
                    print(f"  ❌ 重试失败 {event_id}: {e}")
                    still_failed.append((event_id, event_slug))
                time.sleep(args.request_delay)
            failed = still_failed

        print("\n" + "=" * 60)
        print(f"📊 完成！共保存 {total_saved} 条市场记录")
        if failed:
            print(f"⚠️ {len(failed)} 个事件重试后仍失败：")
            for eid, eslug in failed:
                print(f"  - {eid} ({eslug})")
    finally:
        conn.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
