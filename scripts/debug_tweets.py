#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import TWEET_WIDE_EXCEL
import pandas as pd

print("=" * 70)
print("🔍 推文宽表调试脚本")
print("=" * 70)

print(f"\n📂 读取文件: {TWEET_WIDE_EXCEL}")
df_raw = pd.read_excel(TWEET_WIDE_EXCEL, header=None)

print(f"\n📋 整个数据框的形状: {df_raw.shape}  (行, 列)")
print(f"\n📋 前 5 行预览:")
print(df_raw.head(5).to_string())

print("\n" + "=" * 70)

# 定位数据
date_row = df_raw.iloc[1, 1:].values
hour_col = df_raw.iloc[2:, 0].values
data_matrix = df_raw.iloc[2:, 1:].values

print(f"\n📋 日期行 (date_row):")
print(f"   • 长度: {len(date_row)}")
print(f"   • 内容: {date_row[:5]}...")
print(f"   • 数据类型: {[type(x) for x in date_row[:3]]}")

print(f"\n📋 小时列 (hour_col):")
print(f"   • 长度: {len(hour_col)}")
print(f"   • 前5个: {hour_col[:5]}")
print(f"   • 后5个: {hour_col[-5:]}")
print(f"   • 数据类型: {[type(x) for x in hour_col[:3]]}")

print(f"\n📋 数据矩阵 (data_matrix):")
print(f"   • 形状: {data_matrix.shape}  (行, 列)")
print(f"   • 左上角 5x5 数据:")
for i in range(min(5, data_matrix.shape[0])):
    row = data_matrix[i, :min(5, data_matrix.shape[1])]
    print(f"     第{i}行: {row}")
print(f"   • 数据类型: {[type(x) for x in data_matrix[0, :3]]}")

print("\n" + "=" * 70)
print("✅ 调试信息打印完成！请把以上内容复制给我。")