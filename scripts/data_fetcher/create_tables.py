#!/usr/bin/env python3
"""
数据库建表脚本（精简版）
只保留 events、markets、prices 三张表
用法: python scripts/data_fetcher/create_tables.py
"""

import sys
from pathlib import Path

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
import os

from scripts.data_fetcher.config import DB_PATH


def create_tables():
    """创建三张核心表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------- 1. events ----------
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            slug TEXT UNIQUE,
            title TEXT,
            start_date TEXT,
            end_date TEXT,
            active INTEGER,
            closed INTEGER,
            series_slug TEXT,
            category TEXT,
            tags TEXT,
            api_created_at TEXT,
            api_updated_at TEXT,
            local_created_at TEXT DEFAULT (datetime('now')),
            local_updated_at TEXT DEFAULT (datetime('now'))
        )
    ''')

    # ---------- 2. markets ----------
    cursor.execute('''
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

    # ---------- 3. prices ----------
    cursor.execute('''
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

    # 索引（提升查询性能）
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_token_time ON prices (token_id, timestamp_unix)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_prices_market_time ON prices (market_id, timestamp_unix)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_markets_event ON markets (event_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_series ON events (series_slug)')

    conn.commit()
    conn.close()
    print(f"✅ 三张核心表创建成功！数据库位置: {DB_PATH}")


if __name__ == "__main__":
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    create_tables()