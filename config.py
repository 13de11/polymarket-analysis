"""
Polymarket_Analysis 项目统一路径配置
所有脚本通过 `from config import *` 导入路径
"""
import os
from pathlib import Path

# 项目根目录（config.py 所在目录）
PROJECT_ROOT = Path(__file__).resolve().parent

# 子目录路径
DATA_DIR = PROJECT_ROOT / "data"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_DIR = PROJECT_ROOT / "src"
DASH_APP_DIR = SRC_DIR / "dash_app"
LEGACY_DIR = PROJECT_ROOT / "legacy_plotly"

# 数据库路径
DB_PATH = DATA_DIR / "polymarket_data.db"
LIGHT_DB_PATH = DATA_DIR / "elon_tweets_analysis.db"

# 数据文件路径
TWEET_WIDE_EXCEL = DATA_DIR / "tweet_hourly_wide.xlsx"
TWEET_LONG_EXCEL = DATA_DIR / "tweet_counts_long.xlsx"

# 确保必要的目录存在
for dir_path in [DATA_DIR, SCRIPTS_DIR, SRC_DIR]:
    dir_path.mkdir(exist_ok=True)

# 打印配置（用于调试，生产环境可注释掉）
if __name__ == "__main__":
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"DB_PATH: {DB_PATH}")
    print(f"TWEET_WIDE_EXCEL: {TWEET_WIDE_EXCEL}")