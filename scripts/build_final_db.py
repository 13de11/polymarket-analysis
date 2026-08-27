#!/usr/bin/env python3
"""
构建最终版数据库：elon_tweets_analysis.db
- 只包含 elon-tweets 系列事件的数据
- 四张表：events, markets, price_hourly, tweet_hourly
- 所有表结构按照最终版设计
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, LIGHT_DB_PATH

# 源数据库连接
src_conn = sqlite3.connect(str(DB_PATH))
src_conn.row_factory = sqlite3.Row

# 目标数据库连接（新建）
tgt_conn = sqlite3.connect(str(LIGHT_DB_PATH))
tgt_conn.row_factory = sqlite3.Row

print("=" * 70)
print("🚀 构建最终版数据库: elon_tweets_analysis.db")
print("=" * 70)

# ============================================================
# 1. 获取符合条件的事件 ID
# ============================================================
print("\n📌 步骤 1: 获取符合条件的事件")
events = src_conn.execute("""
    SELECT id, slug, start_date, end_date
    FROM events
    WHERE series_slug = 'elon-tweets'
      AND start_date >= '2026-05-30'
""").fetchall()

if not events:
    print("❌ 没有找到符合条件的事件！")
    src_conn.close()
    tgt_conn.close()
    sys.exit(1)

print(f"   ✅ 找到 {len(events)} 个事件")
event_ids = [e['id'] for e in events]
placeholders = ','.join(['?'] * len(event_ids))

# ============================================================
# 2. 获取这些事件下的所有市场
# ============================================================
print("\n📌 步骤 2: 获取关联市场")

def parse_tweet_range(slug: str) -> tuple:
    """解析 market.slug，返回 (range_start, range_end, is_plus)"""
    try:
        rest = slug.replace('elon-musk-of-tweets-', '')
        parts = rest.split('-')
        last_part = parts[-1]
        if last_part.endswith('plus'):
            range_start = int(last_part.replace('plus', ''))
            return range_start, None, 1
        else:
            return int(parts[-2]), int(parts[-1]), 0
    except:
        return None, None, 0

markets = src_conn.execute(f"""
    SELECT id, event_id, slug, game_start_time
    FROM markets
    WHERE event_id IN ({placeholders})
""", event_ids).fetchall()

print(f"   ✅ 找到 {len(markets)} 个市场")

# 解析推文区间，只保留能解析的
markets_parsed = []
for m in markets:
    range_start, range_end, is_plus = parse_tweet_range(m['slug'])
    if range_start is not None:
        markets_parsed.append({
            'id': m['id'],
            'event_id': m['event_id'],
            'slug': m['slug'],
            'range_start': range_start,
            'range_end': range_end,
            'is_plus': is_plus
        })

print(f"   ✅ 其中 {len(markets_parsed)} 个是推文区间子市场")

if not markets_parsed:
    print("❌ 没有有效的推文区间子市场！")
    src_conn.close()
    tgt_conn.close()
    sys.exit(1)

market_ids = [m['id'] for m in markets_parsed]
market_placeholders = ','.join(['?'] * len(market_ids))

# ============================================================
# 3. 获取每个事件的 game_start_time（从第一个市场）
# ============================================================
print("\n📌 步骤 3: 获取事件的 game_start_time")
event_game_start = {}
for e in events:
    first_market = next((m for m in markets_parsed if m['event_id'] == e['id']), None)
    if first_market:
        # 从原始 markets 表获取 game_start_time
        gst = src_conn.execute(
            "SELECT game_start_time FROM markets WHERE id = ?",
            (first_market['id'],)
        ).fetchone()
        event_game_start[e['id']] = gst['game_start_time'] if gst else None

# ============================================================
# 4. 创建目标表结构
# ============================================================
print("\n📌 步骤 4: 创建表结构")

# 删除旧表（如果存在）
tgt_conn.execute("DROP TABLE IF EXISTS events")
tgt_conn.execute("DROP TABLE IF EXISTS markets")
tgt_conn.execute("DROP TABLE IF EXISTS price_hourly")
tgt_conn.execute("DROP TABLE IF EXISTS tweet_hourly")

# 创建 events 表
tgt_conn.execute("""
    CREATE TABLE events (
        id TEXT PRIMARY KEY,
        slug TEXT,
        game_start_time TEXT,
        start_date TEXT,
        end_date TEXT
    )
""")

# 创建 markets 表
tgt_conn.execute("""
    CREATE TABLE markets (
        id TEXT PRIMARY KEY,
        event_id TEXT,
        slug TEXT,
        range_start INTEGER,
        range_end INTEGER,
        is_plus INTEGER
    )
""")

# 创建 price_hourly 表
tgt_conn.execute("""
    CREATE TABLE price_hourly (
        market_id TEXT,
        hour_start_utc INTEGER,
        price_last REAL,
        price_avg REAL,
        PRIMARY KEY (market_id, hour_start_utc)
    )
""")

# 创建 tweet_hourly 表
tgt_conn.execute("""
    CREATE TABLE tweet_hourly (
        timestamp_unix_utc INTEGER PRIMARY KEY,
        tweet_count INTEGER
    )
""")

print("   ✅ 表结构创建完成")

# ============================================================
# 5. 写入 events 数据
# ============================================================
print("\n📌 步骤 5: 写入 events 数据")
for e in events:
    tgt_conn.execute("""
        INSERT INTO events (id, slug, game_start_time, start_date, end_date)
        VALUES (?, ?, ?, ?, ?)
    """, (
        e['id'],
        e['slug'],
        event_game_start.get(e['id']),
        e['start_date'],
        e['end_date']
    ))
print(f"   ✅ 写入 {len(events)} 条事件记录")

# ============================================================
# 6. 写入 markets 数据
# ============================================================
print("\n📌 步骤 6: 写入 markets 数据")
for m in markets_parsed:
    tgt_conn.execute("""
        INSERT INTO markets (id, event_id, slug, range_start, range_end, is_plus)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        m['id'],
        m['event_id'],
        m['slug'],
        m['range_start'],
        m['range_end'],
        m['is_plus']
    ))
print(f"   ✅ 写入 {len(markets_parsed)} 条市场记录")

# ============================================================
# 7. 写入 price_hourly 数据
# ============================================================
print("\n📌 步骤 7: 写入 price_hourly 数据")
price_data = src_conn.execute(f"""
    SELECT market_id, hour_start_utc, price_last, price_avg
    FROM price_hourly_with_tweets
    WHERE market_id IN ({market_placeholders})
    ORDER BY market_id, hour_start_utc
""", market_ids).fetchall()

print(f"   📊 从 price_hourly_with_tweets 获取到 {len(price_data)} 条记录")

# 批量插入
inserted = 0
for p in price_data:
    tgt_conn.execute("""
        INSERT OR IGNORE INTO price_hourly (market_id, hour_start_utc, price_last, price_avg)
        VALUES (?, ?, ?, ?)
    """, (p['market_id'], p['hour_start_utc'], p['price_last'], p['price_avg']))
    inserted += 1

print(f"   ✅ 写入 {inserted} 条价格记录")

# 创建索引
tgt_conn.execute("CREATE INDEX idx_price_market ON price_hourly(market_id)")
tgt_conn.execute("CREATE INDEX idx_price_hour ON price_hourly(hour_start_utc)")
print("   ✅ 创建 price_hourly 索引")

# ============================================================
# 8. 写入 tweet_hourly 数据
# ============================================================
print("\n📌 步骤 8: 写入 tweet_hourly 数据")
tweet_data = src_conn.execute("""
    SELECT timestamp_unix_utc, tweet_count
    FROM tweet_counts
    ORDER BY timestamp_unix_utc
""").fetchall()

print(f"   📊 从 tweet_counts 获取到 {len(tweet_data)} 条记录")

for t in tweet_data:
    tgt_conn.execute("""
        INSERT OR IGNORE INTO tweet_hourly (timestamp_unix_utc, tweet_count)
        VALUES (?, ?)
    """, (t['timestamp_unix_utc'], t['tweet_count']))

print(f"   ✅ 写入 {len(tweet_data)} 条推文记录")
tgt_conn.execute("CREATE INDEX idx_tweet_hour ON tweet_hourly(timestamp_unix_utc)")
print("   ✅ 创建 tweet_hourly 索引")

# ============================================================
# 9. 提交并关闭
# ============================================================
tgt_conn.commit()
src_conn.close()
tgt_conn.close()

# ============================================================
# 10. 统计信息
# ============================================================
print("\n" + "=" * 70)
print("✅ 最终版数据库构建完成！")
print("=" * 70)

# 重新打开目标数据库查看统计
conn = sqlite3.connect(str(LIGHT_DB_PATH))
stats = conn.execute("""
    SELECT 
        (SELECT COUNT(*) FROM events) as events_count,
        (SELECT COUNT(*) FROM markets) as markets_count,
        (SELECT COUNT(*) FROM price_hourly) as price_count,
        (SELECT COUNT(*) FROM tweet_hourly) as tweet_count
""").fetchone()
conn.close()

print(f"\n📊 数据库统计:")
print(f"   • Events: {stats[0]}")
print(f"   • Markets: {stats[1]}")
print(f"   • Price Records: {stats[2]:,}")
print(f"   • Tweet Records: {stats[3]:,}")

# 文件大小
from config import LIGHT_DB_PATH
size_mb = LIGHT_DB_PATH.stat().st_size / 1024 / 1024
print(f"\n📁 文件大小: {size_mb:.2f} MB")

print(f"\n📂 数据库路径: {LIGHT_DB_PATH}")
print("=" * 70)