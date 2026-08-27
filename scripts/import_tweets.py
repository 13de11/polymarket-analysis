#!/usr/bin/env python3
"""
从宽表导入推文数据到数据库（极简版）
- 宽表第一列：0:00-23:00（美东时间 ET，UTC-4）
- 后续列：日期
- 输出表：timestamp_unix_utc (INTEGER, PRIMARY KEY), tweet_count (INTEGER)
- 过滤异常值：tweet_count == 805
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# 将项目根目录加入 Python 路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import DB_PATH, TWEET_WIDE_EXCEL

# 常量
TABLE_NAME = "tweet_counts"
ABNORMAL_TWEET_COUNT = 805
ET_OFFSET = -4  # EDT (UTC-4)


def main():
    print("=" * 70)
    print("📊 导入推文数据（宽表→长表）")
    print("=" * 70)

    # 检查文件是否存在
    if not TWEET_WIDE_EXCEL.exists():
        print(f"❌ 文件不存在: {TWEET_WIDE_EXCEL}")
        return

    import pandas as pd

    # 读取宽表
    print(f"📂 读取: {TWEET_WIDE_EXCEL}")
    df_raw = pd.read_excel(TWEET_WIDE_EXCEL, header=None)

    # 定位数据
    date_row = df_raw.iloc[1, 1:].values
    hour_col = df_raw.iloc[2:, 0].values
    data_matrix = df_raw.iloc[2:, 1:].values

    records = []
    skipped_abnormal = 0

    # 遍历日期列
    for col_idx, date_val in enumerate(date_row):
        if pd.isna(date_val):
            continue

        # 解析日期
        if isinstance(date_val, (datetime, pd.Timestamp)):
            date_obj = date_val
            if hasattr(date_obj, 'to_pydatetime'):
                date_obj = date_obj.to_pydatetime()
        else:
            print(f"⚠️ 跳过无法识别的日期: {date_val}")
            continue

        # 确保年份为 2026
        if date_obj.year != 2026:
            date_obj = date_obj.replace(year=2026)

        # 遍历小时行
        for row_idx, hour_val in enumerate(hour_col):
            if row_idx >= data_matrix.shape[0]:
                break

            tweet_count = data_matrix[row_idx, col_idx]
            if pd.isna(tweet_count):
                continue
            try:
                tweet_count = int(tweet_count)
            except:
                continue

            # 过滤异常值
            if tweet_count == ABNORMAL_TWEET_COUNT:
                skipped_abnormal += 1
                continue

            if tweet_count == 0:
                continue

            # ---- 解析小时（兼容多种类型） ----
            if hasattr(hour_val, 'hour'):
                hour = hour_val.hour
            elif isinstance(hour_val, str) and ':' in hour_val:
                try:
                    hour = int(hour_val.split(':')[0])
                except:
                    continue
            else:
                try:
                    hour = int(hour_val)
                except:
                    continue

            # 构建 ET 时间 → 转换为 UTC
            dt_et = date_obj.replace(
                hour=hour,
                minute=0,
                second=0,
                microsecond=0,
                tzinfo=timezone(timedelta(hours=ET_OFFSET))
            )
            dt_utc = dt_et.astimezone(timezone.utc)
            timestamp_unix = int(dt_utc.timestamp())

            records.append({
                'timestamp_unix_utc': timestamp_unix,
                'tweet_count': tweet_count
            })

    print(f"📊 提取到 {len(records)} 条有效记录")
    if skipped_abnormal > 0:
        print(f"⚠️ 已过滤 {skipped_abnormal} 条异常值 (tweet_count={ABNORMAL_TWEET_COUNT})")

    if not records:
        print("❌ 没有数据可导入")
        return

    # 写入数据库
    print(f"💾 写入数据库: {DB_PATH} -> 表 {TABLE_NAME}")
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    cursor.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            timestamp_unix_utc INTEGER PRIMARY KEY,
            tweet_count INTEGER NOT NULL
        )
    """)
    cursor.execute(f"CREATE INDEX idx_tweet_unix ON {TABLE_NAME}(timestamp_unix_utc)")

    inserted = 0
    for record in records:
        cursor.execute(
            "INSERT OR IGNORE INTO tweet_counts VALUES (?, ?)",
            (record['timestamp_unix_utc'], record['tweet_count'])
        )
        inserted += 1

    conn.commit()

    total = cursor.execute("SELECT COUNT(*) FROM tweet_counts").fetchone()[0]
    sample = cursor.execute("SELECT * FROM tweet_counts LIMIT 5").fetchall()
    conn.close()

    print(f"\n✅ 导入完成！")
    print(f"   • 总记录数: {total}")
    if sample:
        first_ts = datetime.fromtimestamp(sample[0][0], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        last_ts = datetime.fromtimestamp(sample[-1][0], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        print(f"   • 时间范围: {first_ts} ~ {last_ts}")
        print("\n📋 样例记录 (timestamp, tweet_count):")
        for row in sample[:3]:
            dt = datetime.fromtimestamp(row[0], tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"   {dt} → {row[1]} 条推文")


if __name__ == "__main__":
    main()