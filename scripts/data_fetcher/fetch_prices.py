#!/usr/bin/env python3
"""
第四步：拉取历史价格（1分钟粒度，按天分段）
每个市场只拉取 yes_token，支持增量/全量拉取。

用法:
    # 增量拉取所有市场的价格
    python scripts/data_fetcher/fetch_prices.py
    # 只拉取 elon-tweets 系列
    python scripts/data_fetcher/fetch_prices.py --series-slug elon-tweets
    # 拉取近30天的价格
    python scripts/data_fetcher/fetch_prices.py --days-back 30
    # 全量拉取
    python scripts/data_fetcher/fetch_prices.py --full
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import sqlite3
import time
from datetime import datetime, timezone, timedelta

from scripts.data_fetcher.config import DB_PATH, CLOB_BASE
from scripts.data_fetcher.http_client import get_json
from scripts.data_fetcher.tag_utils import resolve_tag

# 全局缓存：token_id -> 最早时间戳
_EARLIEST_CACHE = {}


# ========== 数据库操作 ==========

def get_tokens_to_fetch(
    market_id: str = None,
    token_id: str = None,
    tag_id: str = None,
    tag_slug: str = None,
    event_id: str = None,
    event_ids: list[str] = None,
    event_slug: str = None,
    series_slug: str = None,
    series_id: int = None,
    market_slug: str = None,
    market_ids: list[str] = None,
    title_search: str = None,
    active: bool = None,
    closed: bool = None,
    start_date_min: str = None,
    start_date_max: str = None,
    end_date_min: str = None,
    end_date_max: str = None,
    liquidity_min: float = None,
    liquidity_max: float = None,
    volume_min: float = None,
    volume_max: float = None,
    market_start_days_ago: int = None,
    limit_markets: int = None,
    event_start_date_min: str = None,
) -> list[tuple[str, str]]:
    """获取需要拉取价格的 token 列表 [(market_id, token_id), ...]"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    base_query = """
        SELECT m.id, m.yes_token_id
        FROM markets m
        LEFT JOIN events e ON m.event_id = e.id
        WHERE m.yes_token_id IS NOT NULL
    """
    conditions = []
    params = []

    if event_id:
        conditions.append("m.event_id = ?")
        params.append(event_id)
    if event_ids:
        placeholders = ','.join(['?'] * len(event_ids))
        conditions.append(f"m.event_id IN ({placeholders})")
        params.extend(event_ids)
    if event_slug:
        conditions.append("e.slug = ?")
        params.append(event_slug)
    if series_slug:
        conditions.append("e.series_slug = ?")
        params.append(series_slug)
    if series_id is not None:
        conditions.append("e.series_id = ?")
        params.append(series_id)
    if title_search:
        conditions.append("e.title LIKE ?")
        params.append(f"%{title_search}%")
    if active is not None:
        conditions.append("e.active = ?")
        params.append(1 if active else 0)
    if closed is not None:
        conditions.append("e.closed = ?")
        params.append(1 if closed else 0)
    if start_date_min:
        conditions.append("e.start_date >= ?")
        params.append(start_date_min)
    if start_date_max:
        conditions.append("e.start_date <= ?")
        params.append(start_date_max)
    if end_date_min:
        conditions.append("e.end_date >= ?")
        params.append(end_date_min)
    if end_date_max:
        conditions.append("e.end_date <= ?")
        params.append(end_date_max)
    if tag_id:
        conditions.append("e.tags LIKE ?")
        params.append(f'%"id": "{tag_id}"%')
    if tag_slug:
        conditions.append("e.tags LIKE ?")
        params.append(f'%"slug": "{tag_slug}"%')
    if market_id:
        conditions.append("m.id = ?")
        params.append(market_id)
    if market_ids:
        placeholders = ','.join(['?'] * len(market_ids))
        conditions.append(f"m.id IN ({placeholders})")
        params.extend(market_ids)
    if market_slug:
        conditions.append("m.slug = ?")
        params.append(market_slug)
    if token_id:
        conditions.append("m.yes_token_id = ?")
        params.append(token_id)
    if liquidity_min is not None:
        conditions.append("m.liquidity >= ?")
        params.append(liquidity_min)
    if liquidity_max is not None:
        conditions.append("m.liquidity <= ?")
        params.append(liquidity_max)
    if volume_min is not None:
        conditions.append("m.volume >= ?")
        params.append(volume_min)
    if volume_max is not None:
        conditions.append("m.volume <= ?")
        params.append(volume_max)
    if market_start_days_ago is not None and market_start_days_ago > 0:
        cutoff_date = (datetime.now() - timedelta(days=market_start_days_ago)).isoformat()
        conditions.append("e.start_date >= ?")
        params.append(cutoff_date)
    if event_start_date_min:
        conditions.append("e.start_date >= ?")
        params.append(event_start_date_min)

    if conditions:
        base_query += " AND " + " AND ".join(conditions)
    if limit_markets:
        base_query += f" LIMIT {limit_markets}"

    cursor.execute(base_query, params)
    rows = cursor.fetchall()
    conn.close()
    return [(market_id, yes_token) for market_id, yes_token in rows if yes_token]


def get_last_timestamp(token_id: str) -> int | None:
    """获取该 token 已有数据的最大时间戳"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(timestamp_unix) FROM prices WHERE token_id = ?", (token_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def save_prices_bulk(token_id: str, market_id: str, history: list[dict]) -> int:
    """批量插入价格数据"""
    if not history:
        return 0

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    data = []
    for point in history:
        ts = point.get("t")
        price = point.get("p")
        if ts is None or price is None:
            continue
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        data.append((token_id, market_id, float(price), int(ts), dt_utc))

    if not data:
        return 0

    try:
        cursor.executemany(
            "INSERT OR IGNORE INTO prices (token_id, market_id, price, timestamp_unix, timestamp_utc) VALUES (?, ?, ?, ?, ?)",
            data,
        )
        inserted = cursor.rowcount
        conn.commit()
        return inserted
    except Exception as e:
        print(f"      批量插入失败: {e}")
        return 0
    finally:
        conn.close()


# ========== API 拉取 ==========

def fetch_prices_history(
    token_id: str,
    fidelity: int = 1,
    interval: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
) -> list[dict]:
    """调用 /prices-history API"""
    url = f"{CLOB_BASE}/prices-history"
    params = {"market": token_id, "fidelity": fidelity}
    if interval is not None:
        params["interval"] = interval
    if start_ts is not None:
        params["startTs"] = start_ts
    if end_ts is not None:
        params["endTs"] = end_ts
    try:
        data = get_json(url, params, max_retries=5, base_delay=1.0, timeout=30)
        if data and isinstance(data, dict):
            return data.get("history", [])
        return []
    except RuntimeError as e:
        print(f"      请求失败: {e}")
        return []


def get_actual_first_timestamp(token_id: str, approx_first_ts: int) -> int:
    """获取真实的最早时间戳"""
    chunk = fetch_prices_history(token_id, fidelity=1, start_ts=approx_first_ts, end_ts=approx_first_ts + 86400)
    if not chunk:
        return approx_first_ts
    timestamps = [p.get("t") for p in chunk if p.get("t") is not None]
    if not timestamps:
        return approx_first_ts
    return min(timestamps)


def detect_earliest_timestamp(token_id: str) -> int | None:
    """探测最早时间"""
    if token_id in _EARLIEST_CACHE:
        return _EARLIEST_CACHE[token_id]

    coarse = fetch_prices_history(token_id, interval="max")
    if not coarse:
        _EARLIEST_CACHE[token_id] = None
        return None
    timestamps = [p.get("t") for p in coarse if p.get("t") is not None]
    if not timestamps:
        _EARLIEST_CACHE[token_id] = None
        return None
    coarse_first = min(timestamps)
    actual_first = get_actual_first_timestamp(token_id, coarse_first)
    result = actual_first - 60
    _EARLIEST_CACHE[token_id] = result
    return result


def fetch_all_minute_prices(
    token_id: str,
    start_from_ts: int | None = None,
    end_ts: int | None = None,
    request_delay: float = 0.3,
) -> list[dict]:
    """按天分段获取1分钟粒度历史价格"""
    now_ts = int(time.time())
    if end_ts is None:
        end_ts = now_ts

    if start_from_ts is None:
        start_from_ts = detect_earliest_timestamp(token_id)
        if start_from_ts is None:
            print("    无法探测最早时间，跳过此 token")
            return []

    if start_from_ts >= end_ts:
        return []

    all_history = []
    seen_timestamps = set()
    day_seconds = 86400
    cursor = start_from_ts
    consecutive_empty_days = 0

    while cursor < end_ts:
        chunk_end = min(cursor + day_seconds, end_ts)
        print(f"      请求 {datetime.fromtimestamp(cursor)} 至 {datetime.fromtimestamp(chunk_end)}...")
        chunk = fetch_prices_history(token_id, fidelity=1, start_ts=cursor, end_ts=chunk_end)

        if chunk:
            new_points = 0
            for point in chunk:
                t = point.get("t")
                if t not in seen_timestamps:
                    seen_timestamps.add(t)
                    all_history.append(point)
                    new_points += 1
            print(f"        获取 {len(chunk)} 条，新增 {new_points} 条")
            consecutive_empty_days = 0
        else:
            print("        无数据")
            is_full_day = (chunk_end - cursor) == day_seconds
            is_past = chunk_end <= now_ts
            if is_full_day and is_past:
                consecutive_empty_days += 1
                if consecutive_empty_days >= 2:
                    print(f"        连续 {consecutive_empty_days} 天无数据，停止请求")
                    break

        cursor = chunk_end
        time.sleep(request_delay)

    all_history.sort(key=lambda x: x.get("t", 0))
    return all_history


# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(description="拉取历史价格（1分钟粒度）")
    parser.add_argument("--market-id", help="只拉取指定市场 ID")
    parser.add_argument("--market-ids", help="只拉取多个市场 ID（逗号分隔）")
    parser.add_argument("--market-slug", help="按市场 slug 精确筛选")
    parser.add_argument("--token-id", help="只拉取指定 token ID")
    parser.add_argument("--event-id", help="按事件 ID 筛选")
    parser.add_argument("--event-ids", help="按多个事件 ID 筛选（逗号分隔）")
    parser.add_argument("--event-slug", help="按事件 slug 筛选")
    parser.add_argument("--title-search", help="按事件标题关键词搜索")
    parser.add_argument("--series-slug", help="按系列 slug 筛选")
    parser.add_argument("--series-id", type=int, help="按系列 ID 筛选")
    parser.add_argument("--tag", help="按标签 slug 或 label 筛选")
    parser.add_argument("--tag-id", help="按标签 ID 筛选")
    parser.add_argument("--active-only", action="store_true", help="仅拉取活跃事件")
    parser.add_argument("--closed-only", action="store_true", help="仅拉取已关闭事件")
    parser.add_argument("--start-date-min", help="事件开始日期最小值")
    parser.add_argument("--start-date-max", help="事件开始日期最大值")
    parser.add_argument("--end-date-min", help="事件结束日期最小值")
    parser.add_argument("--end-date-max", help="事件结束日期最大值")
    parser.add_argument("--liquidity-min", type=float, help="最小流动性")
    parser.add_argument("--liquidity-max", type=float, help="最大流动性")
    parser.add_argument("--volume-min", type=float, help="最小交易量")
    parser.add_argument("--volume-max", type=float, help="最大交易量")
    parser.add_argument("--market-start-days-ago", type=int, help="只拉取 start_date 在近 N 天内的市场")
    parser.add_argument("--event-start-date-min", help="只拉取该日期之后开始的事件对应的市场")
    parser.add_argument("--full", action="store_true", help="全量拉取")
    parser.add_argument("--days-back", type=int, help="拉取近 N 天的价格历史")
    parser.add_argument("--request-delay", type=float, default=0.5, help="每次请求后的延迟秒数")
    parser.add_argument("--limit-markets", type=int, help="限制处理的市场数量")
    parser.add_argument("--batch-size", type=int, default=10, help="每处理多少个 token 后额外休息")
    parser.add_argument("--batch-sleep", type=float, default=8.0, help="批量休息秒数")
    parser.add_argument("--retry-limit", type=int, default=1, help="失败 token 的最大重试次数")

    args = parser.parse_args()

    # 处理 tag
    tag_id = args.tag_id
    tag_slug = None
    if args.tag and not tag_id:
        tag_info = resolve_tag(args.tag)
        tag_id = tag_info.get("id")
        print(f"解析 tag '{args.tag}' -> ID {tag_id}")

    event_ids = args.event_ids.split(',') if args.event_ids else None
    market_ids = args.market_ids.split(',') if args.market_ids else None

    active = None
    closed = None
    if args.active_only:
        active = True
        closed = False
    elif args.closed_only:
        active = False
        closed = True

    tokens = get_tokens_to_fetch(
        market_id=args.market_id,
        token_id=args.token_id,
        tag_id=tag_id,
        tag_slug=tag_slug,
        event_id=args.event_id,
        event_ids=event_ids,
        event_slug=args.event_slug,
        series_slug=args.series_slug,
        series_id=args.series_id,
        market_slug=args.market_slug,
        market_ids=market_ids,
        title_search=args.title_search,
        active=active,
        closed=closed,
        start_date_min=args.start_date_min,
        start_date_max=args.start_date_max,
        end_date_min=args.end_date_min,
        end_date_max=args.end_date_max,
        liquidity_min=args.liquidity_min,
        liquidity_max=args.liquidity_max,
        volume_min=args.volume_min,
        volume_max=args.volume_max,
        market_start_days_ago=args.market_start_days_ago,
        limit_markets=args.limit_markets,
        event_start_date_min=args.event_start_date_min,
    )

    if not tokens:
        print("没有找到需要处理的市场或 token")
        return

    print(f"共 {len(tokens)} 个 token 需要处理")

    total_inserted = 0
    processed = 0
    failed_tokens = []

    # 第一轮处理
    for idx, (market_id, token_id) in enumerate(tokens, 1):
        print(f"\n[{idx}/{len(tokens)}] 市场 {market_id} - token: {token_id[:20]}...")

        if args.days_back:
            end_ts = int(datetime.now().timestamp())
            start_ts = end_ts - args.days_back * 86400
            print(f"  拉取近 {args.days_back} 天")
            history = fetch_all_minute_prices(token_id, start_ts, end_ts, args.request_delay)
        elif not args.full:
            last_ts = get_last_timestamp(token_id)
            if last_ts:
                start_ts = last_ts - 3600
                print(f"  增量模式：从 {datetime.fromtimestamp(start_ts)} 开始")
                history = fetch_all_minute_prices(token_id, start_ts, None, args.request_delay)
            else:
                print("  增量模式：无历史数据，全量拉取")
                history = fetch_all_minute_prices(token_id, None, None, args.request_delay)
        else:
            print("  全量模式")
            history = fetch_all_minute_prices(token_id, None, None, args.request_delay)

        if not history:
            print("  无新价格数据，标记为失败")
            failed_tokens.append((market_id, token_id))
        else:
            inserted = save_prices_bulk(token_id, market_id, history)
            total_inserted += inserted
            print(f"  成功插入 {inserted} 条新记录")

        processed += 1
        if processed % args.batch_size == 0:
            print(f"休息 {args.batch_sleep} 秒...")
            time.sleep(args.batch_sleep)
        else:
            time.sleep(args.request_delay)

    # 重试
    retry_round = 1
    while failed_tokens and retry_round <= args.retry_limit:
        print(f"\n第 {retry_round} 次重试，剩余 {len(failed_tokens)} 个 token")
        next_round_failed = []
        for idx, (market_id, token_id) in enumerate(failed_tokens, 1):
            print(f"\n[重试 {retry_round}] 市场 {market_id}")
            if args.days_back:
                end_ts = int(datetime.now().timestamp())
                start_ts = end_ts - args.days_back * 86400
                history = fetch_all_minute_prices(token_id, start_ts, end_ts, args.request_delay)
            elif not args.full:
                last_ts = get_last_timestamp(token_id)
                start_ts = last_ts - 3600 if last_ts else None
                history = fetch_all_minute_prices(token_id, start_ts, None, args.request_delay)
            else:
                history = fetch_all_minute_prices(token_id, None, None, args.request_delay)

            if not history:
                next_round_failed.append((market_id, token_id))
            else:
                inserted = save_prices_bulk(token_id, market_id, history)
                total_inserted += inserted
                print(f"  重试成功，插入 {inserted} 条新记录")

            if idx % args.batch_size == 0:
                print(f"休息 {args.batch_sleep} 秒...")
                time.sleep(args.batch_sleep)
            else:
                time.sleep(args.request_delay)

        failed_tokens = next_round_failed
        retry_round += 1

    print("\n" + "=" * 60)
    print(f"🎉 完成！总共新增价格记录: {total_inserted}")
    if failed_tokens:
        print(f"⚠️ {len(failed_tokens)} 个 token 在所有重试后仍然失败")
    else:
        print("✅ 所有 token 处理成功")
    print("=" * 60)


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    main()