import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from config import LIGHT_DB_PATH  # 改为使用新数据库
import sqlite3
import pandas as pd
import os

DB_PATH = os.getenv("DATABASE_PATH", str(LIGHT_DB_PATH))

def run_query(query: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()
    return df