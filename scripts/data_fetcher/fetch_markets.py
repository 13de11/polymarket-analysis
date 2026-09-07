#!/usr/bin/env python3
"""
第三步：拉取市场数据（支持事件筛选和增量/全量更新 + 自动重试失败事件）
功能：根据 events 表中的事件，调用 API 获取每个事件下的具体市场（盘口），
     存入 markets 表。

用法示例:
    # 拉取所有事件的市场（增量：只拉取尚未拉取过市场的事件）
    python scripts/data_fetcher/fetch_markets.py
    # 强制重新拉取所有事件的市场（忽略已存在标记）
    python scripts/data_fetcher/fetch_markets.py --force
    # 只拉取系列 slug 为 'elon-tweets' 的事件
    python scripts/data_fetcher/fetch_markets.py --series-slug elon-tweets
    # 只拉取近7天内开始的事件
    python scripts/data_fetcher/fetch_markets.py --market-start-days-ago 7
    # 拉取单个事件（指定事件ID）
    python scripts/data_fetcher/fetch_markets.py --event-id 490187
    # 拉取单个事件（指定事件slug）
    python scripts/data_fetcher/fetch_markets.py --event-slug elon-musk-of-tweets-may-19-may-26
    # 设置最大重试次数为2（默认1）
    python scripts/data_fetcher/fetch_markets.py --retry-limit 2
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import json
import sqlite3
import time
from datetime import datetime, timedelta

from scripts.data_fetcher.config import DB_PATH, GAMMA_BASE
from scripts.data_fetcher.http_client import get_json


# ========== 核心函数 ==========

def fetch_markets_by_event(event_id: str) -> list[dict]:
    """调用 Gamma API 获取指定事件下的市场数据"""
    url = f"{GAMMA_BASE}/events/{event_id}"
    try:
        data = get_json(url, retries=3, retry_delay=1.0)
        if not data:
            return []
        return data.get("markets", [])
    except Exception as e:
        print(f"  ❌ 获取事件 {event_id} 市场失败: {e}")
        return []


def save_market(market: dict, event_id: str) -> bool:
    """保存市场到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # 获取事件分类
        cursor.execute("SELECT category FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        event_category = row[0] if row else None

        market_id = market.get("id")
        question = market.get("question")
        condition_id = market.get("conditionId")
        slug = market.get("slug")
        outcomes = market.get("outcomes", [])
        if isinstance(outcomes, str):
            try:
                outcomes = json.loads(outcomes)
            except:
                outcomes = []
        raw_tokens = market.get("clobTokenIds", [])
        if isinstance(raw_tokens, str):
            try:
                raw_tokens = json.loads(raw_tokens)
            except:
                raw_tokens = []
        yes_token = raw_tokens[0] if len(raw_tokens) > 0 else None
        no_token = raw_tokens[1] if len(raw_tokens) > 1 else None
        market_tags = market.get("tags", [])
        market_active = 1 if market.get("active") else 0
        market_closed = 1 if market.get("closed") else 0
        market_end_date = market.get("endDate")
        market_start_date = market.get("startDate")
        game_start_time = market.get("gameStartTime")
        market_tags_json = json.dumps(market_tags, ensure_ascii=False)
        now = datetime.now().isoformat()

        cursor.execute('''
            INSERT OR REPLACE INTO markets
            (id, event_id, question, condition_id, slug, outcomes,
             yes_token_id, no_token_id, category, active, closed,
             end_date, start_date, tags, updated_at, game_start_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (market_id, event_id, question, condition_id, slug,
              json.dumps(outcomes, ensure_ascii=False), yes_token, no_token,
              event_category, market_active, market_closed,
              market_end_date, market_start_date, market_tags_json, now, game_start_time))

        conn.commit()
        return True
    except Exception as e:
        print(f"  保存市场失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def event_has_markets(event_id: str) -> bool:
    """检查事件是否已有市场数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM markets WHERE event_id = ? LIMIT 1", (event_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists


def get_events_by_filters(
    tag_id: str = None,
    tag_slug: str = None,
    event_id: str = None,
    event_slug: str = None,
    series_slug: str = None,
    active_only: bool = False,
    closed_only: bool = False,
    market_start_days_ago: int = None,
) -> list[tuple[str, str]]:
    """根据筛选条件获取事件列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    conditions = []
    params = []

    if event_id:
        conditions.append("id = ?")
        params.append(event_id)
    elif event_slug:
        conditions.append("slug = ?")
        params.append(event_slug)
    else:
        if tag_id:
            conditions.append("tags LIKE ?")
            params.append(f'%"id": "{tag_id}"%')
        if tag_slug:
            conditions.append("tags LIKE ?")
            params.append(f'%"slug": "{tag_slug}"%')
        if series_slug:
            conditions.append("series_slug = ?")
            params.append(series_slug)
        if active_only:
            conditions.append("active = 1")
        if closed_only:
            conditions.append("closed = 1")
        if market_start_days_ago is not None and market_start_days_ago > 0:
            cutoff = (datetime.now() - timedelta(days=market_start_days_ago)).isoformat()
            conditions.append("start_date >= ?")
            params.append(cutoff)

    query = "SELECT id, slug FROM events"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows


def process_event(event_id: str, event_slug: str, force: bool, delay: float) -> tuple[int, int, bool]:
    """处理单个事件：拉取市场并保存"""
    if not force and event_has_markets(event_id):
        print(f"⏭️ 跳过事件 {event_id}（市场已存在）")
        return 0, 0, False

    print(f"\n🔍 处理事件 {event_id}: {event_slug[:50] if event_slug else 'N/A'}...")
    markets = fetch_markets_by_event(event_id)
    if not markets:
        print(f"  ⚠️ 该事件无市场数据（可能API无返回或失败）")
        return 0, 0, False

    saved = 0
    failed = 0
    for market in markets:
        if save_market(market, event_id):
            saved += 1
        else:
            failed += 1
        time.sleep(delay / 5)
    print(f"  ✅ 保存了 {saved}/{len(markets)} 个市场，失败 {failed} 个")
    return saved, failed, True


def main():
    parser = argparse.ArgumentParser(description="拉取事件下的市场数据（支持自动重试失败事件）")
    parser.add_argument("--force", action="store_true", help="强制重新拉取（忽略已存在）")
    parser.add_argument("--retry-limit", type=int, default=1, help="失败事件的最大重试次数（默认1）")
    parser.add_argument("--tag-id", help="按标签 ID 筛选")
    parser.add_argument("--tag-slug", help="按标签 slug 筛选")
    parser.add_argument("--event-id", help="只拉取指定事件 ID")
    parser.add_argument("--event-slug", help="只拉取指定事件 slug")
    parser.add_argument("--series-slug", help="按系列 slug 筛选")
    parser.add_argument("--active-only", action="store_true", help="仅拉取活跃事件")
    parser.add_argument("--closed-only", action="store_true", help="仅拉取已关闭事件")
    parser.add_argument("--market-start-days-ago", type=int, help="仅拉取近 N 天内开始的事件")
    parser.add_argument("--request-delay", type=float, default=0.5, help="每个事件后的延迟秒数")
    parser.add_argument("--batch-size", type=int, default=10, help="每处理多少个事件后额外休息")
    parser.add_argument("--batch-sleep", type=float, default=5.0, help="批量休息秒数")

    args = parser.parse_args()

    print("=" * 60)
    print("第三步：拉取市场数据（含自动重试失败事件）")
    print(f"数据库: {DB_PATH}")
    print(f"强制模式: {'是' if args.force else '否（增量）'}")
    print(f"最大重试轮数: {args.retry_limit}")

    events = get_events_by_filters(
        tag_id=args.tag_id,
        tag_slug=args.tag_slug,
        event_id=args.event_id,
        event_slug=args.event_slug,
        series_slug=args.series_slug,
        active_only=args.active_only,
        closed_only=args.closed_only,
        market_start_days_ago=args.market_start_days_ago,
    )

    if not events:
        print("❌ 没有符合条件的事件，请检查筛选条件或先运行 fetch_events.py")
        return

    print(f"✅ 共找到 {len(events)} 个事件")

    pending = events[:]
    retry_round = 0
    total_saved = 0
    total_failed = 0

    while pending and retry_round <= args.retry_limit:
        round_desc = "首次处理" if retry_round == 0 else f"第 {retry_round} 次重试"
        print(f"\n{'='*40} {round_desc}（剩余 {len(pending)} 个事件） {'='*40}")

        next_pending = []
        for idx, (event_id, event_slug) in enumerate(pending, 1):
            saved, failed, success = process_event(
                event_id, event_slug, args.force, args.request_delay
            )
            if success:
                total_saved += saved
                total_failed += failed
            else:
                if not args.force and event_has_markets(event_id):
                    pass
                else:
                    next_pending.append((event_id, event_slug))

            if idx % args.batch_size == 0 and idx < len(pending):
                print(f"💤 已处理 {idx}/{len(pending)}，休息 {args.batch_sleep} 秒...")
                time.sleep(args.batch_sleep)
            else:
                time.sleep(args.request_delay)

        pending = next_pending
        retry_round += 1

    if pending:
        print(f"\n❌ 以下 {len(pending)} 个事件在所有重试后仍然失败：")
        for eid, eslug in pending:
            print(f"  - {eid} ({eslug})")
    else:
        print("\n✅ 所有事件均处理成功！")

    print("\n" + "=" * 60)
    print("📊 执行完成！")
    print(f"  新保存的市场总数: {total_saved}")
    print(f"  保存过程中失败的市场数: {total_failed}")
    print("=" * 60)


if __name__ == "__main__":
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    main()