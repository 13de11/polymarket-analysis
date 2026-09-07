#!/usr/bin/env python3
"""
统一配置 - scripts/data_fetcher 模块的配置中心
"""

from pathlib import Path

# 项目根目录（当前文件在 scripts/data_fetcher/ 下，向上 3 级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 数据目录
DATA_DIR = PROJECT_ROOT / "data"

# 原始大库数据库路径（所有数据拉取都写入此库）
DB_PATH = DATA_DIR / "polymarket_data.db"

# 精简数据库路径（Dash 应用读取）
LIGHT_DB_PATH = DATA_DIR / "elon_tweets_analysis.db"

# API 基础地址
GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"

# 请求配置
REQUEST_DELAY = 0.3
USER_AGENT = "polymarket-data-fetcher/1.0"