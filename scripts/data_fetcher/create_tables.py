#!/usr/bin/env python3
"""
数据库建表/迁移脚本（幂等，可重复运行）
- 三张核心表：events / markets / prices
- events 表补 series_id 列（存量行按 series_slug 映射回填）
- 新增 price_sync_state 价格同步状态表（增量记账）

用法:
    python scripts/data_fetcher/create_tables.py
    python scripts/data_fetcher/create_tables.py --db data/test.db   # 指定库（测试用）
"""

import sys
import argparse
import sqlite3
import os
from pathlib import Path

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data_fetcher.config import DB_PATH

# 系列 slug -> series_id 映射（用于回填存量数据）
SERIES_ID_BY_SLUG = {
    'elon-tweets': 10000,
    'elon-tweets-48h': 10816,
}


def ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> bool:
    """表缺少某列时补上（幂等）。"""
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {r[1] for r in cur.fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        print(f"  ✅ {table}.{column} 列已添加")
        return True
    return False


def create_tables(conn: sqlite3.Connection) -> None:
    """创建核心表（全新库用；老库 IF NOT EXISTS 会跳过）。"""
    conn.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE,
            title TEXT,
            start_date TEXT,
            end_date TEXT,
            active INTEGER,
            closed INTEGER,
            series_slug TEXT,
            series_id INTEGER,
            category TEXT,
            tags TEXT,
            api_created_at TEXT,
            api_updated_at TEXT,
            local_created_at TEXT DEFAULT (datetime('now')),
            local_updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    # 老库可能没有 series_id 列（CREATE IF NOT EXISTS 不会补），先补列再建索引
    ensure_column(conn, 'events', 'series_id', 'INTEGER')
    conn.commit()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS markets (
            id TEXT PRIMARY KEY,
            event_id TEXT,
            question TEXT,
            condition_id TEXT,
            slug TEXT,
            outcomes TEXT,
            yes_token_id TEXT,
            no_token_id TEXT,
            category TEXT,
            active INTEGER,
            closed INTEGER,
            end_date TEXT,
            start_date TEXT,
            tags TEXT,
            game_start_time TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_id TEXT NOT NULL,
            market_id TEXT,
            price REAL NOT NULL,
            timestamp_unix INTEGER NOT NULL,
            timestamp_utc TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(token_id, timestamp_unix)
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS price_sync_state (
            token_id TEXT PRIMARY KEY,
            market_id TEXT,
            last_ts INTEGER,
            last_probe_ts INTEGER,
            complete INTEGER NOT NULL DEFAULT 0,
            complete_reason TEXT,
            updated_at TEXT
        )
    ''')

    # 索引
    conn.execute('CREATE INDEX IF NOT EXISTS idx_prices_token_time ON prices (token_id, timestamp_unix)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_prices_market_time ON prices (market_id, timestamp_unix)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_markets_event ON markets (event_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_events_series ON events (series_slug)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_events_series_id ON events (series_id)')


def migrate(conn: sqlite3.Connection) -> None:
    """老库迁移：补列 + 回填 series_id。幂等。"""
    ensure_column(conn, 'events', 'series_id', 'INTEGER')

    # 回填存量事件的 series_id（slug -> id 映射）
    for slug, sid in SERIES_ID_BY_SLUG.items():
        cur = conn.execute(
            "UPDATE events SET series_id = ? WHERE series_slug = ? AND series_id IS NULL",
            (sid, slug),
        )
        if cur.rowcount:
            print(f"  ✅ series_slug={slug} 回填 series_id={sid}，共 {cur.rowcount} 行")

    conn.commit()


def main(db_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_tables(conn)
        migrate(conn)
        conn.commit()
    finally:
        conn.close()
    print(f"✅ 表结构就绪！数据库位置: {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="建表/迁移（幂等）")
    parser.add_argument("--db", default=str(DB_PATH), help="数据库路径（默认取 config）")
    args = parser.parse_args()
    main(args.db)
