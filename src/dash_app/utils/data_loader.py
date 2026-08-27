"""
数据加载层 - 从 elon_tweets_analysis.db 读取数据
"""
import sqlite3
import pandas as pd
import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "elon_tweets_analysis.db")


def run_query(query: str, params=()) -> pd.DataFrame:
    """执行 SQL 查询并返回 DataFrame"""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
    return df


def get_elon_tweet_events():
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc).isoformat()
    query = """
        SELECT id, slug, game_start_time, start_date, end_date
        FROM events
        WHERE end_date < ?
        ORDER BY start_date
    """
    return run_query(query, (now_utc,))


def get_markets_by_event(event_id: str):
    """获取指定事件下所有有价格数据的市场，按推文区间排序"""
    query = """
        SELECT DISTINCT m.id, m.slug, m.range_start, m.range_end, m.is_plus
        FROM markets m
        JOIN price_hourly p ON m.id = p.market_id
        WHERE m.event_id = ?
        ORDER BY m.range_start
    """
    return run_query(query, (event_id,))


def get_target_market(event_id: str):
    # 1. 获取事件 end_date
    event = run_query("SELECT end_date FROM events WHERE id = ?", (event_id,))
    if event.empty:
        return None
    end_date = pd.to_datetime(event['end_date'].iloc[0])
    end_ts = int(end_date.timestamp())

    # 2. 获取所有市场在 endDate 及之后的最新价格
    query = """
        SELECT 
            m.id,
            m.slug,
            m.range_start,
            m.range_end,
            m.is_plus,
            p.price_last,
            p.hour_start_utc
        FROM markets m
        JOIN price_hourly p ON m.id = p.market_id
        WHERE m.event_id = ?
          AND p.hour_start_utc >= ?
        ORDER BY p.hour_start_utc DESC
    """
    df = run_query(query, (event_id, end_ts))
    if df.empty:
        return None

    # 3. 取每个市场最新一条记录（group by id 取第一条，因为已按时间倒序）
    df_latest = df.groupby('id').first().reset_index()

    # 4. 按价格降序取第一个（价格最高）
    target = df_latest.sort_values('price_last', ascending=False).iloc[0]
    return target.to_dict()


def get_price_data_for_market(market_id: str, start_ts=None, end_ts=None):
    """获取单个市场的价格数据"""
    query = """
        SELECT 
            hour_start_utc,
            price_last,
            price_avg
        FROM price_hourly
        WHERE market_id = ?
    """
    params = [market_id]
    if start_ts:
        query += " AND hour_start_utc >= ?"
        params.append(start_ts)
    if end_ts:
        query += " AND hour_start_utc < ?"
        params.append(end_ts)
    query += " ORDER BY hour_start_utc"
    df = run_query(query, tuple(params))
    if not df.empty:
        df['datetime_utc'] = pd.to_datetime(df['hour_start_utc'], unit='s')
    return df


def get_tweet_data_for_event(event_id: str, start_ts=None, end_ts=None):
    """获取事件时间范围内的推文数据"""
    event = run_query("SELECT game_start_time, end_date FROM events WHERE id = ?", (event_id,))
    if event.empty:
        return pd.DataFrame()
    query = "SELECT timestamp_unix_utc, tweet_count FROM tweet_hourly WHERE 1=1"
    params = []
    if event['game_start_time'].iloc[0]:
        start_ts = pd.to_datetime(event['game_start_time'].iloc[0]).timestamp()
        query += " AND timestamp_unix_utc >= ?"
        params.append(int(start_ts))
    if event['end_date'].iloc[0]:
        end_ts = pd.to_datetime(event['end_date'].iloc[0]).timestamp()
        query += " AND timestamp_unix_utc < ?"
        params.append(int(end_ts))
    if start_ts:
        query += " AND timestamp_unix_utc >= ?"
        params.append(start_ts)
    if end_ts:
        query += " AND timestamp_unix_utc < ?"
        params.append(end_ts)
    query += " ORDER BY timestamp_unix_utc"
    df = run_query(query, tuple(params))
    if not df.empty:
        df['datetime_utc'] = pd.to_datetime(df['timestamp_unix_utc'], unit='s')
    return df


def get_event_remaining_hours(event_id: str) -> int:
    """获取事件从 gamestart 到 end 的总小时数"""
    event = run_query("SELECT game_start_time, end_date FROM events WHERE id = ?", (event_id,))
    if event.empty:
        return 0
    start = pd.to_datetime(event['game_start_time'].iloc[0])
    end = pd.to_datetime(event['end_date'].iloc[0])
    return int((end - start).total_seconds() / 3600)


def get_market_median(market_id: str) -> float:
    """获取市场的中位数锚点"""
    market = run_query("SELECT range_start, range_end FROM markets WHERE id = ?", (market_id,))
    if market.empty:
        return 0.5
    r_start = market['range_start'].iloc[0]
    r_end = market['range_end'].iloc[0]
    if pd.isna(r_end) or r_end is None:
        return float(r_start) + 50
    return (float(r_start) + float(r_end)) / 2


def get_event_time_range(event_id: str):
    """获取事件的价格数据时间范围"""
    query = """
        SELECT MIN(hour_start_utc) as min_ts, MAX(hour_start_utc) as max_ts
        FROM price_hourly
        WHERE market_id IN (SELECT id FROM markets WHERE event_id = ?)
    """
    return run_query(query, (event_id,))


# ==================== 兼容旧页面 ====================

def get_price_data(market_ids, start_ts=None, end_ts=None):
    """
    兼容旧版：支持单个或多个市场ID，返回合并后的DataFrame
    """
    if isinstance(market_ids, (list, tuple)):
        all_dfs = []
        for mid in market_ids:
            df = get_price_data_for_market(mid, start_ts, end_ts)
            if not df.empty:
                df['market_id'] = mid
                all_dfs.append(df)
        if all_dfs:
            return pd.concat(all_dfs, ignore_index=True)
        return pd.DataFrame()
    else:
        return get_price_data_for_market(market_ids, start_ts, end_ts)


def get_tweet_data(event_id, start_ts=None, end_ts=None):
    """兼容旧版，调用 get_tweet_data_for_event"""
    return get_tweet_data_for_event(event_id, start_ts, end_ts)


def get_table_list():
    """获取数据库中所有表名（用于首页）"""
    query = "SELECT name FROM sqlite_master WHERE type='table';"
    df = run_query(query)
    return df['name'].tolist()

def get_event_gamestart_label(event_id: str) -> Optional[str]:
    """获取事件的 gamestart_label（从 events 表读取）"""
    query = """
        SELECT game_start_time 
        FROM events 
        WHERE id = ?
    """
    result = run_query(query, (event_id,))
    if result.empty:
        return None
    return result['game_start_time'].iloc[0]


def get_event_start_timestamp(event_id: str) -> Optional[int]:
    """获取事件开盘时间戳（用于自定义区间）"""
    event = run_query("SELECT start_date FROM events WHERE id = ?", (event_id,))
    if event.empty:
        return None
    return int(pd.to_datetime(event['start_date'].iloc[0]).timestamp())