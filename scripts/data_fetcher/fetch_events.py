#!/usr/bin/env python3
"""
第二步：拉取事件数据（支持增量/全量，支持丰富的筛选条件，使用 keyset 游标分页）

用法示例：
    # 按标签抓取
    python scripts/data_fetcher/fetch_events.py --tag tweets-markets
    # 按系列 ID 抓取
    python scripts/data_fetcher/fetch_events.py --series-id 10000
    # 按事件 slug 精确抓取
    python scripts/data_fetcher/fetch_events.py --slug nba-cle-nyk-2026-05-19
    # 按日期范围（最近7天）
    python scripts/data_fetcher/fetch_events.py --days-limit 7
    # 强制全量拉取
    python scripts/data_fetcher/fetch_events.py --full
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from scripts.data_fetcher.config import DB_PATH, GAMMA_BASE
from scripts.data_fetcher.http_client import get_json
from scripts.data_fetcher.tag_utils import resolve_tag

# ========== 数据库操作 ==========

def get_last_start_date_for_tag(tag_id: str) -> str | None:
    """从 events 表中查询该 tag 下的最大 start_date（用于增量）。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT MAX(start_date) FROM events
        WHERE tags LIKE ?
    ''', (f'%"id": "{tag_id}"%',))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def save_event(event: dict) -> None:
    """保存事件到 events 表。"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    tags = event.get("tags", [])
    # 找出 id 最小的标签，取其 slug 作为 category
    category = None
    min_id = None
    for tag in tags:
        tag_id = tag.get("id")
        if tag_id is not None:
            try:
                tid = int(tag_id)
                if min_id is None or tid < min_id:
                    min_id = tid
                    category = tag.get("slug")
            except (ValueError, TypeError):
                continue
    if category is None and tags:
        category = tags[0].get("slug")

    event_id = event.get("id")
    slug = event.get("slug")
    title = event.get("title")
    start_date = event.get("startDate")
    end_date = event.get("endDate")
    active = 1 if event.get("active") else 0
    closed = 1 if event.get("closed") else 0
    series_slug = event.get("seriesSlug")
    tags_json = json.dumps(tags, ensure_ascii=False)
    api_created_at = event.get("createdAt")
    api_updated_at = event.get("updatedAt")
    now = datetime.now().isoformat()

    # 获取已有的 local_created_at
    cursor.execute("SELECT local_created_at FROM events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    if row and row[0]:
        local_created_at = row[0]
    else:
        local_created_at = now

    local_updated_at = now

    cursor.execute('''
        INSERT OR REPLACE INTO events
        (id, slug, title, start_date, end_date, active, closed,
         series_slug, category, tags,
         api_created_at, api_updated_at, local_created_at, local_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event_id, slug, title, start_date, end_date, active, closed,
        series_slug, category, tags_json,
        api_created_at, api_updated_at, local_created_at, local_updated_at
    ))

    conn.commit()
    conn.close()


def format_utc_datetime(dt: datetime) -> str:
    """将 datetime 对象格式化为 API 接受的 UTC 时间字符串（带 Z）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ========== API 拉取 ==========

def fetch_events_by_keyset(
    tag_id: str = None,
    series_id: int = None,
    slug: str = None,
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
    request_delay: float = 0.3,
) -> list[dict]:
    """使用 /events/keyset 游标分页获取事件。"""
    all_events = []
    after_cursor = None
    limit = 500

    while True:
        params = {
            "limit": limit,
            "order": "startDate",
            "ascending": "true"
        }
        if tag_id:
            params["tag_id"] = tag_id
        if series_id is not None:
            params["series_id"] = series_id
        if slug:
            params["slug"] = slug
        if title_search:
            params["title_search"] = title_search
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if start_date_min:
            params["start_date_min"] = start_date_min
        if start_date_max:
            params["start_date_max"] = start_date_max
        if end_date_min:
            params["end_date_min"] = end_date_min
        if end_date_max:
            params["end_date_max"] = end_date_max
        if liquidity_min is not None:
            params["liquidity_min"] = str(liquidity_min)
        if liquidity_max is not None:
            params["liquidity_max"] = str(liquidity_max)
        if volume_min is not None:
            params["volume_min"] = str(volume_min)
        if volume_max is not None:
            params["volume_max"] = str(volume_max)
        if after_cursor:
            params["after_cursor"] = after_cursor

        try:
            data = get_json(f"{GAMMA_BASE}/events/keyset", params)
        except RuntimeError as e:
            print(f"  keyset 请求失败: {e}")
            break

        if not data:
            break

        events_batch = data.get("events", [])
        if not events_batch:
            break

        all_events.extend(events_batch)
        print(f"  已获取 {len(all_events)} 个事件...")

        next_cursor = data.get("next_cursor")
        if not next_cursor:
            break
        after_cursor = next_cursor
        time.sleep(request_delay)

    return all_events


# ========== 主函数 ==========

def main():
    parser = argparse.ArgumentParser(description="拉取 Polymarket 事件数据（支持丰富筛选和 keyset 分页）")
    parser.add_argument("--tag", help="Tag slug 或 label（如 tweets-markets, NBA）")
    parser.add_argument("--tag-id", help="直接指定 tag ID")
    parser.add_argument("--active-only", action="store_true", help="仅获取活跃事件")
    parser.add_argument("--closed-only", action="store_true", help="仅获取已结束事件")
    parser.add_argument("--full", action="store_true", help="强制全量拉取（忽略增量记录）")
    parser.add_argument("--days-limit", type=int, help="限制拉取近 N 天内开始的事件")
    parser.add_argument("--request-delay", type=float, default=0.3, help="请求间隔秒数")
    parser.add_argument("--series-id", type=int, help="按系列 ID 筛选")
    parser.add_argument("--slug", help="按事件 slug 精确筛选")
    parser.add_argument("--title-search", help="按标题关键词搜索")
    parser.add_argument("--start-date-min", help="开始日期最小值 (ISO 格式)")#--start-date-min 2026-09-01T00:00:00Z
    parser.add_argument("--start-date-max", help="开始日期最大值")
    parser.add_argument("--end-date-min", help="结束日期最小值")
    parser.add_argument("--end-date-max", help="结束日期最大值")
    parser.add_argument("--liquidity-min", type=float, help="最小流动性（美元）")
    parser.add_argument("--liquidity-max", type=float, help="最大流动性（美元）")
    parser.add_argument("--volume-min", type=float, help="最小交易量")
    parser.add_argument("--volume-max", type=float, help="最大交易量")

    args = parser.parse_args()

    # 初始化 tag_id
    tag_id = None

    if args.tag_id:
        tag_id = args.tag_id
    elif args.tag:
        tag_info = resolve_tag(args.tag)
        if tag_info and tag_info.get("id"):
            tag_id = tag_info["id"]
            print(f"解析 tag: {args.tag} -> ID={tag_id}")
        else:
            print(f"⚠️ 未找到 tag: {args.tag}")

    # 决定开始日期范围
    start_date_str = None
    end_date_str = None
    if args.days_limit:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=args.days_limit)
        start_date_str = format_utc_datetime(start_time)
        end_date_str = format_utc_datetime(end_time)
        print(f"日期范围限制：{start_date_str} 至 {end_date_str}")
    elif not args.full and tag_id:
        last_date = get_last_start_date_for_tag(tag_id)
        if last_date:
            if last_date.endswith('Z'):
                last_dt = datetime.fromisoformat(last_date.replace('Z', '+00:00'))
            else:
                last_dt = datetime.fromisoformat(last_date)
            start_dt = last_dt - timedelta(days=1)
            start_date_str = format_utc_datetime(start_dt)
            print(f"增量模式：只拉取 {start_date_str} 之后的事件")
        else:
            print("全量模式（数据库中无该 tag 事件）")
    elif not args.full:
        print("未指定 tag 且非全量模式，将执行全量拉取（无时间限制）")
    else:
        print("强制全量模式")

    if args.start_date_min:
        start_date_str = args.start_date_min
    if args.start_date_max:
        end_date_str = args.start_date_max

    # 处理 active/closed
    active = None
    closed = None
    if args.active_only:
        active = True
        closed = False
    elif args.closed_only:
        active = False
        closed = True

    print("开始获取事件列表...")
    events = fetch_events_by_keyset(
        tag_id=tag_id,
        series_id=args.series_id,
        slug=args.slug,
        title_search=args.title_search,
        active=active,
        closed=closed,
        start_date_min=start_date_str,
        start_date_max=end_date_str,
        end_date_min=args.end_date_min,
        end_date_max=args.end_date_max,
        liquidity_min=args.liquidity_min,
        liquidity_max=args.liquidity_max,
        volume_min=args.volume_min,
        volume_max=args.volume_max,
        request_delay=args.request_delay,
    )
    print(f"共获取到 {len(events)} 个事件，开始存入数据库...")
    for idx, ev in enumerate(events, 1):
        save_event(ev)
        if idx % 50 == 0:
            print(f"  已处理 {idx}/{len(events)}")
    print("全部事件处理完成。")


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    main()