#!/usr/bin/env python3
"""把 elon_tweets_analysis.db（SQLite 精简库）导出成 PostgreSQL 可导入的 SQL。

产物（默认写到 data/exports/pg_YYYYMMDD/）：
  01_schema.sql  -- CREATE SCHEMA + 5 张表 + 3 个索引
  02_data.sql    -- COPY ... FROM STDIN 数据（psql -f 可直接导入）

导入命令（本机便携版 PostgreSQL）：
  psql -h 127.0.0.1 -p 5432 -U postgres -d polymarket \
       -v ON_ERROR_STOP=1 -f 01_schema.sql -f 02_data.sql

设计约定（改之前先想清楚）：
  - 所有时间戳保持 BIGINT（Unix 秒 UTC），与 stats_loader.py 口径及前端数据契约一致。
    不要在这里转成 timestamptz，否则命中判定、窗口计算、前端格式化全部要跟着改。
  - 表名与字段名原样保留，统一放进 --schema 指定的独立 schema（默认 analytics），
    避免与主平台 public 下已有的表重名、也避免污染正在使用的黑盒测试库。
  - 只做机械格式转换：不补数据、不改值、不做物化聚合。这是过渡产物，不是最终 migration。
"""
from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "elon_tweets_analysis.db"
DEFAULT_OUT = ROOT / "data" / "exports" / ("pg_" + dt.date.today().strftime("%Y%m%d"))

# 顺序即导入顺序：先维表，后事实表
TABLES: list[tuple[str, list[str]]] = [
    ("events", ["id", "slug", "game_start_time", "start_date", "end_date"]),
    ("markets", ["id", "event_id", "slug", "range_start", "range_end", "is_plus"]),
    ("market_tokens", ["market_id", "token_id"]),
    ("price_hourly", ["market_id", "hour_start_utc", "price_last", "price_avg"]),
    ("tweet_hourly", ["timestamp_unix_utc", "tweet_count"]),
]

# PostgreSQL 主键列不允许 NULL，逐表检查
PK_COLUMNS: dict[str, list[str]] = {
    "events": ["id"],
    "markets": ["id"],
    "market_tokens": ["market_id"],
    "price_hourly": ["market_id", "hour_start_utc"],
    "tweet_hourly": ["timestamp_unix_utc"],
}

DDL_TEMPLATE = """-- 由 scripts/data_fetcher/export_sqlite_to_pg.py 生成 @ {generated}
-- 来源：data/elon_tweets_analysis.db（30MB SQLite 精简库）
--
-- 这是「把测试数据搬进 PostgreSQL」的过渡产物，不是最终 migration。
-- 正式合进生产库时，表名/字段/口径要按主平台规范重新设计（推文、区间、命中结果尤其如此）。
-- 时间戳一律 BIGINT（Unix 秒 UTC），禁止改成 timestamptz。
-- 重复导入会因子已存在而失败（安全行为）；需要先清空时请手工 DROP SCHEMA {schema} CASCADE。

CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE {schema}.events (
    id               TEXT PRIMARY KEY,
    slug             TEXT,
    game_start_time  TEXT,
    start_date       TEXT,
    end_date         TEXT
);

CREATE TABLE {schema}.markets (
    id            TEXT PRIMARY KEY,
    event_id      TEXT,
    slug          TEXT,
    range_start   BIGINT,
    range_end     BIGINT,
    is_plus       BIGINT
);

CREATE TABLE {schema}.market_tokens (
    market_id   TEXT PRIMARY KEY,
    token_id    TEXT
);

CREATE TABLE {schema}.price_hourly (
    market_id        TEXT NOT NULL,
    hour_start_utc   BIGINT NOT NULL,
    price_last       DOUBLE PRECISION,
    price_avg        DOUBLE PRECISION,
    PRIMARY KEY (market_id, hour_start_utc)
);

CREATE TABLE {schema}.tweet_hourly (
    timestamp_unix_utc  BIGINT PRIMARY KEY,
    tweet_count         BIGINT
);

CREATE INDEX idx_price_market ON {schema}.price_hourly (market_id);
CREATE INDEX idx_price_hour   ON {schema}.price_hourly (hour_start_utc);
CREATE INDEX idx_tweet_hour   ON {schema}.tweet_hourly (timestamp_unix_utc);
"""


def copy_value(value) -> str:
    """转成 PostgreSQL COPY text 格式的单个字段值。"""
    if value is None:
        return r"\N"
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value)
    return (
        text.replace("\\", "\\\\")
        .replace("\b", "\\b")
        .replace("\f", "\\f")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\v", "\\v")
    )


def validate(sqlite: sqlite3.Connection) -> None:
    """导出前核对表/列是否存在、主键列有无 NULL。"""
    existing = {row[0] for row in sqlite.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    for table, columns in TABLES:
        if table not in existing:
            raise SystemExit(f"缺少表：{table}")
        actual = [row[1] for row in sqlite.execute(f'PRAGMA table_info("{table}")')]
        if actual != columns:
            raise SystemExit(f"{table} 列顺序/名称已变化：期望 {columns}，实际 {actual}")
        for pk in PK_COLUMNS[table]:
            n = sqlite.execute(
                f'SELECT count(*) FROM "{table}" WHERE "{pk}" IS NULL'
            ).fetchone()[0]
            if n:
                raise SystemExit(f"{table}.{pk} 有 {n} 行 NULL，PostgreSQL 主键不允许")


def export(sqlite_db: Path, out_dir: Path, schema: str) -> None:
    if not schema.replace("_", "").isalnum():
        raise SystemExit(f"schema 名不合法：{schema}")
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{sqlite_db.as_posix()}?mode=ro", uri=True)
    try:
        validate(conn)
        schema_file = out_dir / "01_schema.sql"
        data_file = out_dir / "02_data.sql"

        with schema_file.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(DDL_TEMPLATE.format(
                generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                schema=schema,
            ))

        with data_file.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("-- 由 export_sqlite_to_pg.py 生成；用 psql -f 导入（COPY FROM STDIN 是 psql 语法）\n")
            fh.write(f"-- 目标 schema：{schema}\n")
            fh.write("SET client_encoding = 'UTF8';\n")
            fh.write("BEGIN;\n\n")
            for table, columns in TABLES:
                col_list = ", ".join(f'"{c}"' for c in columns)
                fh.write(f"COPY {schema}.{table} ({col_list}) FROM STDIN;\n")
                rows = 0
                cursor = conn.execute(f'SELECT {col_list} FROM "{table}"')
                for row in cursor:
                    fh.write("\t".join(copy_value(v) for v in row) + "\n")
                    rows += 1
                fh.write("\\.\n\n")
                print(f"  {table:<16} {rows:>8,} 行")
            fh.write("COMMIT;\n")

        print(f"\n已生成：\n  {schema_file}\n  {data_file}")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite 精简库 -> PostgreSQL SQL 转储")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="源 SQLite 文件")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出目录")
    parser.add_argument("--schema", default="analytics", help="目标 PostgreSQL schema")
    args = parser.parse_args()
    if not args.db.is_file():
        raise SystemExit(f"找不到源库：{args.db}")
    print(f"源库：{args.db}")
    print(f"目标 schema：{args.schema}")
    export(args.db, args.out, args.schema)


if __name__ == "__main__":
    sys.exit(main())
