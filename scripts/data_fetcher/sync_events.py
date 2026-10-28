#!/usr/bin/env python3
"""
事件增量同步（series_id 驱动，state 记账版 v2）

逻辑：
- 每个系列做两次 keyset 查询（都是升序分页，量很小）：
  1) start_date_min = 本地最新事件 start_date - 回看天数（默认 7 天，向前覆盖防缝隙）
  2) end_date_min   = now - 1 天（刷新"进行中/刚结束"事件的状态，如 closed 翻转）
- 库中无该系列记录时（首次），回看 35 天（价格 API 只存近一个月，更早无意义）
- 落库 UPSERT：新事件插入，老事件更新状态字段；local_created_at 保留
- series_id 一并写入 events 表

用法:
    python scripts/data_fetcher/sync_events.py --series-id 10000 --series-id 10816
    python scripts/data_fetcher/sync_events.py --series-id 10000 --lookback-days 10
    python scripts/data_fetcher/sync_events.py --db data/test.db   # 测试库
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


def format_utc_datetime(dt: datetime) -> str:
    """将 datetime 对象格式化为 API 接受的 UTC 时间字符串（带 Z）。"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

# (series_id, series_slug)；slug 仅在库中无 series_id 记录时用于兜底定位
SERIES = [
    (10000, 'elon-tweets'),
    (10816, 'elon-tweets-48h'),
]
FIRST_LOOKBACK_DAYS = 35   # 首次拉取的回看窗口
REFRESH_END_DAYS = 1       # 状态刷新窗口：end_date 在 now-1d 之后的事件全部重拉


def fetch_events_keyset(base_params: dict, request_delay: float) -> list[dict]:
    """keyset 升序分页拉事件，失败抛 RuntimeError。"""
    events = []
    after = None
    while True:
        params = {'limit': 500, 'order': 'startDate', 'ascending': 'true', **base_params}
        if after:
            params['after_cursor'] = after
        data = get_json(f"{GAMMA_BASE}/events/keyset", params, retries=4, retry_delay=2.0)
        batch = data.get('events', []) if isinstance(data, dict) else []
        if not batch:
            break
        events.extend(batch)
        print(f"  已获取 {len(events)} 个事件...")
        after = data.get('next_cursor')
        if not after:
            break
        time.sleep(request_delay)
    return events


def category_of(event: dict):
    """取 id 最小的 tag slug 作为 category（与旧 fetch_events 逻辑一致）。"""
    tags = event.get('tags', [])
    category = None
    min_id = None
    for tag in tags:
        tag_id = tag.get('id')
        if tag_id is not None:
            try:
                tid = int(tag_id)
            except (ValueError, TypeError):
                continue
            if min_id is None or tid < min_id:
                min_id = tid
                category = tag.get('slug')
    if category is None and tags:
        category = tags[0].get('slug')
    return category


def parse_iso(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except ValueError:
        return None


def upsert_events(conn: sqlite3.Connection, events: dict[str, dict], series_id: int) -> tuple[int, int]:
    """批量 UPSERT 事件，返回 (新增数, 更新数)。"""
    if not events:
        return 0, 0
    ids = list(events.keys())
    placeholders = ','.join(['?'] * len(ids))
    existing = {
        r[0] for r in conn.execute(
            f"SELECT id FROM events WHERE id IN ({placeholders})", ids
        ).fetchall()
    }
    now = datetime.now().isoformat()
    rows = []
    for ev in events.values():
        rows.append((
            ev.get('id'), ev.get('slug'), ev.get('title'),
            ev.get('startDate'), ev.get('endDate'),
            1 if ev.get('active') else 0,
            1 if ev.get('closed') else 0,
            ev.get('seriesSlug'), series_id, category_of(ev),
            json.dumps(ev.get('tags', []), ensure_ascii=False),
            ev.get('createdAt'), ev.get('updatedAt'), now, now,
        ))
    conn.executemany('''
        INSERT INTO events
            (id, slug, title, start_date, end_date, active, closed,
             series_slug, series_id, category, tags,
             api_created_at, api_updated_at, local_created_at, local_updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            slug = excluded.slug,
            title = excluded.title,
            start_date = excluded.start_date,
            end_date = excluded.end_date,
            active = excluded.active,
            closed = excluded.closed,
            series_slug = excluded.series_slug,
            series_id = COALESCE(excluded.series_id, events.series_id),
            category = excluded.category,
            tags = excluded.tags,
            api_created_at = excluded.api_created_at,
            api_updated_at = excluded.api_updated_at,
            local_updated_at = excluded.local_updated_at
    ''', rows)
    conn.commit()
    new_count = len([i for i in ids if i not in existing])
    return new_count, len(ids) - new_count


def main():
    parser = argparse.ArgumentParser(description="事件增量同步（series_id 驱动）")
    parser.add_argument('--series-id', type=int, action='append', default=[],
                        help='系列 ID，可多次传入')
    parser.add_argument('--lookback-days', type=int, default=7,
                        help='增量回看天数（向前覆盖防缝隙，默认 7）')
    parser.add_argument('--request-delay', type=float, default=0.3)
    parser.add_argument('--db', default=str(DB_PATH), help='数据库路径（测试用）')
    args = parser.parse_args()

    series_list = [(sid, slug) for sid, slug in SERIES if not args.series_id or sid in args.series_id]
    if not series_list:
        print('❌ 未匹配到任何系列，检查 --series-id 参数')
        return 1

    now = datetime.now(timezone.utc)
    conn = sqlite3.connect(args.db)
    ok = True
    try:
        for sid, slug in series_list:
            print(f"\n===== 系列 {sid} ({slug}) =====")
            # 本地最新事件起点（series_id 优先，老数据用 slug 兜底）
            row = conn.execute(
                "SELECT MAX(start_date) FROM events "
                "WHERE series_id = ? OR (series_id IS NULL AND series_slug = ?)",
                (sid, slug),
            ).fetchone()
            local_max = row[0] if row else None

            if local_max:
                dt = parse_iso(local_max)
                if dt is None:
                    print(f"  ⚠️ 本地 start_date 无法解析: {local_max}，按首次拉取处理")
                start_min = format_utc_datetime(dt - timedelta(days=args.lookback_days))
                print(f"  增量模式：start_date >= {start_min}（回看 {args.lookback_days} 天）")
            else:
                start_min = format_utc_datetime(now - timedelta(days=FIRST_LOOKBACK_DAYS))
                print(f"  首次拉取：start_date >= {start_min}（回看 {FIRST_LOOKBACK_DAYS} 天）")

            # 窗口 1：新增 + 近期事件状态
            end_min = format_utc_datetime(now - timedelta(days=REFRESH_END_DAYS))
            print(f"  状态刷新：end_date >= {end_min}")

            try:
                ev_new = fetch_events_keyset({'series_id': sid, 'start_date_min': start_min},
                                             args.request_delay)
                ev_refresh = fetch_events_keyset({'series_id': sid, 'end_date_min': end_min},
                                                 args.request_delay)
            except RuntimeError as e:
                print(f"  ❌ 拉取失败，跳过系列 {sid}: {e}")
                ok = False
                continue

            merged = {e['id']: e for e in ev_new}
            for e in ev_refresh:
                merged[e['id']] = e
            print(f"  合并后待处理 {len(merged)} 个事件（新增窗口 {len(ev_new)}，状态刷新窗口 {len(ev_refresh)}）")

            new_count, upd_count = upsert_events(conn, merged, sid)
            print(f"  ✅ 新增 {new_count}，更新 {upd_count}")
    finally:
        conn.close()

    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
