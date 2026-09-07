#!/usr/bin/env python3
"""
聚合小时级价格与推文数据
- 价格从 prices 表读取，按小时聚合（last、avg、std、max、min）
- 推文从 tweet_counts 表匹配（按小时）
- 支持增量模式和全量重建

用法：
    # 增量更新所有事件
    python scripts/data_fetcher/aggregate_prices_tweets.py
    # 强制重建表（全量重新聚合）
    python scripts/data_fetcher/aggregate_prices_tweets.py --force
    # 只处理指定事件
    python scripts/data_fetcher/aggregate_prices_tweets.py --event-slug elon-musk-of-tweets-june-23-june-30
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import argparse
import sqlite3
import pandas as pd
import numpy as np
import re
import time
from datetime import datetime, timezone

from scripts.data_fetcher.config import DB_PATH, DATA_DIR

TABLE_NAME = "price_hourly_with_tweets"
MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12
}


def parse_event_period_from_question(question: str):
    """从市场问题中解析统计周期（用于推文匹配）"""
    pattern = r'from\s+([A-Za-z]+)\s+(\d{1,2})\s+to\s+([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})'
    match = re.search(pattern, question, re.IGNORECASE)
    if not match:
        return None, None

    start_month = match.group(1).lower()
    start_day = int(match.group(2))
    end_month = match.group(3).lower()
    end_day = int(match.group(4))
    year = int(match.group(5))

    start_month_num = MONTH_MAP.get(start_month)
    end_month_num = MONTH_MAP.get(end_month)

    if not start_month_num or not end_month_num:
        return None, None

    start_dt = datetime(year, start_month_num, start_day, 16, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(year, end_month_num, end_day, 16, 0, 0, tzinfo=timezone.utc)

    return int(start_dt.timestamp()), int(end_dt.timestamp())


def get_events(conn, event_slug=None, event_ids=None):
    """获取需要处理的事件列表"""
    query = """
        SELECT id, slug
        FROM events
        WHERE series_slug = 'elon-tweets'
          AND closed = 1
          AND start_date >= '2025-11-29'
    """
    params = []

    if event_slug:
        query += " AND slug = ?"
        params.append(event_slug)

    if event_ids:
        placeholders = ','.join(['?'] * len(event_ids))
        query += f" AND id IN ({placeholders})"
        params.extend(event_ids)

    query += " ORDER BY start_date ASC"

    return pd.read_sql_query(query, conn, params=params)


def main():
    parser = argparse.ArgumentParser(description="聚合小时级价格与推文数据")
    parser.add_argument("--force", action="store_true", help="强制重建表（删除已有数据）")
    parser.add_argument("--event-slug", help="只聚合指定事件 slug")
    parser.add_argument("--event-ids", help="只聚合指定事件 ID（逗号分隔）")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------- 加载推文数据 ----------
    print("📂 加载推文数据到内存...")
    tweet_df = pd.read_sql_query(
        "SELECT timestamp_unix_utc, tweet_count FROM tweet_counts",
        conn
    )
    tweet_dict = dict(zip(tweet_df['timestamp_unix_utc'], tweet_df['tweet_count']))
    print(f"   加载 {len(tweet_dict)} 小时推文数据")

    # ---------- 创建输出表 ----------
    if args.force:
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
        print(f"🗑️ 已强制删除旧表 {TABLE_NAME}")

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_slug TEXT NOT NULL,
            market_id TEXT NOT NULL,
            hour_start_utc INTEGER NOT NULL,
            tweet_count INTEGER,
            price_last REAL,
            price_avg REAL,
            price_std REAL,
            price_max REAL,
            price_min REAL,
            UNIQUE(market_id, hour_start_utc)
        )
    ''')
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_event ON {TABLE_NAME}(event_slug)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_market ON {TABLE_NAME}(market_id)")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_hour ON {TABLE_NAME}(hour_start_utc)")
    conn.commit()
    print(f"✅ 表 {TABLE_NAME} 已就绪\n")

    # ---------- 获取事件列表 ----------
    event_ids = None
    if args.event_ids:
        event_ids = [e.strip() for e in args.event_ids.split(',') if e.strip()]

    events_df = get_events(conn, event_slug=args.event_slug, event_ids=event_ids)

    if events_df.empty:
        print("❌ 没有符合条件的事件")
        conn.close()
        return

    print(f"📋 找到 {len(events_df)} 个已关闭事件\n")

    total_records = 0

    # ---------- 循环处理每个事件 ----------
    for idx, event_row in events_df.iterrows():
        event_id = event_row['id']
        event_slug = event_row['slug']

        print(f"[{idx+1}/{len(events_df)}] 处理事件: {event_slug}")

        # 查询该事件已有数据的最大小时时间戳（用于增量）
        cursor.execute(
            f"SELECT MAX(hour_start_utc) FROM {TABLE_NAME} WHERE event_slug = ?",
            (event_slug,)
        )
        max_existing_hour = cursor.fetchone()[0]

        # 解析统计周期（用于推文匹配）
        sample_question = cursor.execute(
            "SELECT question FROM markets WHERE event_id = ? AND yes_token_id IS NOT NULL LIMIT 1",
            (event_id,)
        ).fetchone()
        if not sample_question:
            print("  ⚠️ 无市场，跳过")
            continue

        tweet_start_ts, tweet_end_ts = parse_event_period_from_question(sample_question[0])
        if tweet_start_ts is None:
            print("  ⚠️ 无法解析统计周期，跳过")
            continue

        # 批量获取价格数据（只取新增部分）
        price_query = """
            SELECT
                m.id AS market_id,
                p.timestamp_unix,
                p.price
            FROM prices p
            JOIN markets m ON p.market_id = m.id
            WHERE m.event_id = ?
              AND p.token_id = m.yes_token_id
        """
        params = [event_id]
        if max_existing_hour is not None:
            price_query += " AND p.timestamp_unix > ?"
            params.append(max_existing_hour)
            print(f"  增量补充模式：只取 timestamp_unix > {max_existing_hour} 的新数据")
        else:
            print("  全量模式（新事件）：取全部价格数据")

        df_prices = pd.read_sql_query(price_query, conn, params=params)

        if df_prices.empty:
            print("  ⚠️ 该事件无新增价格数据，跳过")
            continue

        df_prices['price'] = pd.to_numeric(df_prices['price'], errors='coerce')
        df_prices = df_prices.dropna(subset=['price'])

        if df_prices.empty:
            print("  ⚠️ 新增价格数据全部无效，跳过")
            continue

        print(f"  新增原始价格记录数: {len(df_prices)}")
        print(f"  价格范围: {df_prices['price'].min():.4f} ~ {df_prices['price'].max():.4f}")

        # 计算小时起始时间戳
        df_prices['hour_start_utc'] = (df_prices['timestamp_unix'] // 3600) * 3600

        # 分组聚合
        df_grouped = df_prices.groupby(['market_id', 'hour_start_utc']).agg(
            price_last=('price', 'last'),
            price_avg=('price', 'mean'),
            price_std=('price', 'std'),
            price_max=('price', 'max'),
            price_min=('price', 'min')
        ).reset_index()

        df_grouped['price_std'] = df_grouped['price_std'].fillna(0)

        # 关联推文数（只匹配统计周期内的小时）
        df_grouped['tweet_count'] = df_grouped['hour_start_utc'].map(
            lambda x: tweet_dict.get(x) if tweet_start_ts <= x < tweet_end_ts else None
        )

        df_grouped['event_slug'] = event_slug

        cols = ['event_slug', 'market_id', 'hour_start_utc', 'tweet_count',
                'price_last', 'price_avg', 'price_std', 'price_max', 'price_min']
        df_grouped = df_grouped[cols]

        print(f"  聚合后新增小时记录数: {len(df_grouped)}")

        matched = df_grouped['tweet_count'].notna().sum()
        print(f"  匹配到推文的小时数: {matched} / {len(df_grouped)}")

        # 批量插入
        data_tuples = df_grouped.to_records(index=False).tolist()
        cursor.executemany(f'''
            INSERT OR IGNORE INTO {TABLE_NAME}
            (event_slug, market_id, hour_start_utc, tweet_count, price_last, price_avg, price_std, price_max, price_min)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', data_tuples)
        conn.commit()
        inserted = cursor.rowcount
        total_records += inserted
        print(f"  插入 {inserted} 条新记录（跳过重复）")

        time.sleep(0.1)

    conn.close()
    print(f"\n✅ 聚合完成！本次新增记录数: {total_records}")


if __name__ == "__main__":
    main()