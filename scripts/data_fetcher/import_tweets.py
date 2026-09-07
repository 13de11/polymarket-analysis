#!/usr/bin/env python3
"""
重构版：从宽表导入推文数据到数据库，使用四列结构
- original_time: 原始时间（日期+小时）
- utc_time: 原始时间 + 4 小时（UTC），ISO 格式含时区信息
- timestamp_unix_utc: UTC 时间的 10 位秒级时间戳
- tweet_count: 推文数量
- 过滤掉异常值：tweet_count == 805（2026/1/11 2:00:00 的异常数据）

Excel 宽表路径：data/tweet_hourly_wide.xlsx
输出 Excel 备份：data/tweet_counts_long.xlsx
"""

import sys
from pathlib import Path

# 将项目根目录添加到 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import sqlite3
import pandas as pd
from datetime import datetime, timedelta, timezone

# 从新项目 config 导入路径配置
from scripts.data_fetcher.config import DB_PATH, DATA_DIR

EXCEL_PATH = DATA_DIR / "tweet_hourly_wide.xlsx"
OUTPUT_EXCEL = DATA_DIR / "tweet_counts_long.xlsx"
TABLE_NAME = "tweet_counts"

# 异常值过滤条件
ABNORMAL_TWEET_COUNT = 805


def main():
    if not EXCEL_PATH.exists():
        print(f"❌ 文件不存在: {EXCEL_PATH}")
        print("   请确认文件路径是否正确，或修改脚本中的 EXCEL_PATH")
        return

    print(f"📂 读取宽表: {EXCEL_PATH}")
    df_raw = pd.read_excel(EXCEL_PATH, header=None)

    # 定位数据
    date_row = df_raw.iloc[1, 1:].values       # 第1行日期
    hour_col = df_raw.iloc[2:, 0].values       # 第2行起小时
    data_matrix = df_raw.iloc[2:, 1:].values   # 数据区域

    records = []

    # 遍历日期列
    for col_idx, date_val in enumerate(date_row):
        if pd.isna(date_val):
            continue

        # 解析日期
        if isinstance(date_val, datetime):
            date_obj = date_val
        elif isinstance(date_val, pd.Timestamp):
            date_obj = date_val.to_pydatetime()
        else:
            print(f"⚠️ 跳过无法识别的日期: {date_val}")
            continue

        if date_obj.year != 2026:
            date_obj = date_obj.replace(year=2026)

        # 遍历小时行
        for row_idx, hour_val in enumerate(hour_col):
            if row_idx >= data_matrix.shape[0]:
                break

            tweet_count = data_matrix[row_idx, col_idx]
            if pd.isna(tweet_count):
                tweet_count = 0
            else:
                try:
                    tweet_count = int(tweet_count)
                except:
                    tweet_count = 0

            # 🔥 过滤异常值
            if tweet_count == ABNORMAL_TWEET_COUNT:
                print(f"⚠️ 跳过异常值: 日期 {date_obj.strftime('%Y-%m-%d')} 小时 {hour_val} 推文数 {tweet_count}")
                continue

            # 解析小时
            if isinstance(hour_val, datetime):
                hour = hour_val.hour
            elif isinstance(hour_val, pd.Timestamp):
                hour = hour_val.hour
            elif hasattr(hour_val, 'hour'):
                hour = hour_val.hour
            elif isinstance(hour_val, str) and ':' in hour_val:
                hour = int(hour_val.split(':')[0])
            else:
                try:
                    hour = int(hour_val)
                except:
                    continue

            # ========== 关键修复：明确指定原始时区为 ET（UTC-4） ==========
            # 原始时间明确为 ET（UTC-4）
            dt_source = date_obj.replace(hour=hour, minute=0, second=0, microsecond=0,
                                         tzinfo=timezone(timedelta(hours=-4)))
            # 转换为 UTC
            dt_utc = dt_source.astimezone(timezone.utc)

            # 格式化字符串（ISO 格式，含时区信息）
            original_time_str = dt_source.strftime('%Y-%m-%d %H:%M')
            utc_time_str = dt_utc.isoformat(timespec='seconds')  # 例: 2026-01-06T04:00:00+00:00

            # 时间戳（直接从 aware datetime 获取）
            timestamp_unix_utc = int(dt_utc.timestamp())

            records.append({
                'original_time': original_time_str,
                'utc_time': utc_time_str,
                'timestamp_unix_utc': timestamp_unix_utc,
                'tweet_count': tweet_count,
            })

    if not records:
        print("❌ 没有提取到任何数据")
        return

    df_long = pd.DataFrame(records)
    print(f"📊 提取到 {len(df_long)} 条记录（已过滤异常值）")

    # 打印样例验证
    print("\n🔍 样例记录（前5条）:")
    for i in range(min(5, len(df_long))):
        row = df_long.iloc[i]
        print(f"  原始: {row['original_time']} → UTC: {row['utc_time']} → 时间戳: {row['timestamp_unix_utc']} → 推文: {row['tweet_count']}")

    # ---------- 导出 Excel 备份 ----------
    df_long.to_excel(OUTPUT_EXCEL, index=False)
    print(f"\n✅ Excel 备份已保存: {OUTPUT_EXCEL}")

    # ---------- 创建数据库表并导入 ----------
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 删除旧表，新建
    cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
    cursor.execute(f'''
        CREATE TABLE {TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_time TEXT NOT NULL,
            utc_time TEXT NOT NULL,
            timestamp_unix_utc INTEGER NOT NULL,
            tweet_count INTEGER NOT NULL,
            UNIQUE(original_time)
        )
    ''')
    cursor.execute(f"CREATE INDEX idx_{TABLE_NAME}_unix ON {TABLE_NAME}(timestamp_unix_utc)")
    cursor.execute(f"CREATE INDEX idx_{TABLE_NAME}_utc_time ON {TABLE_NAME}(utc_time)")

    # 批量插入
    inserted = 0
    for _, row in df_long.iterrows():
        cursor.execute(f'''
            INSERT INTO {TABLE_NAME}
            (original_time, utc_time, timestamp_unix_utc, tweet_count)
            VALUES (?, ?, ?, ?)
        ''', (row['original_time'], row['utc_time'], row['timestamp_unix_utc'], row['tweet_count']))
        inserted += 1

    conn.commit()

    # 验证
    total = cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
    sample = cursor.execute(f"SELECT original_time, utc_time, tweet_count FROM {TABLE_NAME} LIMIT 5").fetchall()
    conn.close()

    print(f"\n✅ 数据库表 '{TABLE_NAME}' 创建完成")
    print(f"   总记录数: {total}")
    print("\n📋 数据库样例记录:")
    for row in sample:
        print(f"  {row[0]} → {row[1]} → {row[2]} 条推文")


if __name__ == "__main__":
    main()