#!/usr/bin/env python3
"""
数据健康检查 - 一键打印两个库的关键指标
用法: python scripts/check_db.py
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from config import DB_PATH, LIGHT_DB_PATH


def fmt_size(p):
    if not p.exists():
        return "N/A"
    return f"{p.stat().st_size / 1024 / 1024:.2f} MB"


def check_src_db():
    print("\n" + "=" * 70)
    print(f"📦 源库: {DB_PATH}")
    print("=" * 70)
    if not DB_PATH.exists():
        print("❌ 不存在")
        return

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    tables = [r[0] for r in cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )]
    print(f"表: {', '.join(tables)}\n")

    for t in ['events', 'markets', 'prices', 'tweet_counts', 'price_hourly_with_tweets']:
        if t in tables:
            n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  • {t}: {n:,} 条")

    # 事件系列分布
    try:
        print("\n📊 事件系列分布:")
        rows = cur.execute("""
            SELECT series_slug, COUNT(*) FROM events
            WHERE series_slug IS NOT NULL
            GROUP BY series_slug ORDER BY COUNT(*) DESC
        """).fetchall()
        for slug, n in rows:
            print(f"  • {slug}: {n}")

        # 时间范围
        row = cur.execute("SELECT MIN(start_date), MAX(end_date) FROM events").fetchone()
        if row[0]:
            print(f"\n📅 事件时间范围: {row[0]} ~ {row[1]}")
    except Exception as e:
        print(f"⚠️ 查询失败: {e}")

    # 推文范围
    if 'tweet_counts' in tables:
        row = cur.execute(
            "SELECT COUNT(*), MIN(tweet_count), MAX(tweet_count), "
            "MIN(timestamp_unix_utc), MAX(timestamp_unix_utc) FROM tweet_counts"
        ).fetchone()
        print(f"\n🐦 推文: {row[0]:,} 条, 单小时范围 {row[1]} ~ {row[2]}")

    conn.close()
    print(f"\n📁 文件大小: {fmt_size(DB_PATH)}")


def check_light_db():
    print("\n" + "=" * 70)
    print(f"📦 精简库: {LIGHT_DB_PATH}")
    print("=" * 70)
    if not LIGHT_DB_PATH.exists():
        print("❌ 不存在")
        return

    conn = sqlite3.connect(str(LIGHT_DB_PATH))
    cur = conn.cursor()

    for t in ['events', 'markets', 'price_hourly', 'tweet_hourly']:
        try:
            n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  • {t}: {n:,} 条")
        except Exception:
            print(f"  • {t}: (不存在)")

    # 事件系列分布（通过解析 slug 日期跨度判断）
    try:
        import re
        from datetime import datetime

        def parse_days(slug):
            pattern = r'elon-musk-of-tweets-([a-z]+)-(\d{1,2})-([a-z]+)-(\d{1,2})(?:-(\d{4}))?'
            m = re.search(pattern, slug)
            if not m:
                return None
            month_map = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            sm = month_map.get(m.group(1).lower())
            sd = int(m.group(2))
            em = month_map.get(m.group(3).lower())
            ed = int(m.group(4))
            year = int(m.group(5)) if m.group(5) else 2026
            if not sm or not em:
                return None
            start = datetime(year, sm, sd)
            end = datetime(year, em, ed)
            return (end - start).days

        rows = cur.execute("SELECT slug FROM events").fetchall()
        counter = {'7d': 0, '48h': 0, 'unknown': 0}
        for (slug,) in rows:
            days = parse_days(slug)
            if days == 7:
                counter['7d'] += 1
            elif days == 2:
                counter['48h'] += 1
            else:
                counter['unknown'] += 1

        print("\n📊 事件系列分布:")
        for k, v in counter.items():
            print(f"  • {k}: {v}")
    except Exception as e:
        print(f"⚠️ 查询失败: {e}")

    # 价格时间范围
    try:
        row = cur.execute(
            "SELECT MIN(hour_start_utc), MAX(hour_start_utc) FROM price_hourly"
        ).fetchone()
        if row[0]:
            from datetime import datetime, timezone
            mn = datetime.fromtimestamp(row[0], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            mx = datetime.fromtimestamp(row[1], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            print(f"\n📅 价格时间范围: {mn} ~ {mx} (UTC)")
    except Exception as e:
        print(f"⚠️ 查询失败: {e}")

    # 推文时间范围
    try:
        row = cur.execute(
            "SELECT MIN(timestamp_unix_utc), MAX(timestamp_unix_utc) FROM tweet_hourly"
        ).fetchone()
        if row[0]:
            from datetime import datetime, timezone
            mn = datetime.fromtimestamp(row[0], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            mx = datetime.fromtimestamp(row[1], tz=timezone.utc).strftime('%Y-%m-%d %H:%M')
            print(f"🐦 推文时间范围: {mn} ~ {mx} (UTC)")
    except Exception as e:
        print(f"⚠️ 查询失败: {e}")

    conn.close()
    print(f"\n📁 文件大小: {fmt_size(LIGHT_DB_PATH)}")


def main():
    print("=" * 70)
    print("🔍 数据健康检查")
    print("=" * 70)
    check_src_db()
    check_light_db()
    print("\n" + "=" * 70)
    print("✅ 检查完成")
    print("=" * 70)


if __name__ == "__main__":
    main()