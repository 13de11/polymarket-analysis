"""
统计分析加载器
为数据分析中心提供聚合查询函数
"""

import pandas as pd
import numpy as np
from datetime import datetime
from .data_loader import run_query


def get_overview_stats() -> dict:
    """获取核心 KPI 指标（精简版）"""
    # 总事件
    events = run_query("""
        SELECT COUNT(*) as total_events
        FROM events
        WHERE slug LIKE 'elon-musk-of-tweets%'
    """)
    total_events = events['total_events'].iloc[0] if not events.empty else 0

    # 总推文
    tweets = run_query("""
        SELECT SUM(tweet_count) as total_tweets
        FROM tweet_hourly
    """)
    total_tweets = tweets['total_tweets'].iloc[0] if not tweets.empty else 0

    # 命中市场
    hit_markets = run_query("""
        SELECT COUNT(DISTINCT market_id) as hit_count
        FROM price_hourly
        WHERE price_last > 0.99
    """)
    hit_count = hit_markets['hit_count'].iloc[0] if not hit_markets.empty else 0

    # 最热区间
    hot_range = run_query("""
        SELECT m.range_start, m.range_end, COUNT(*) as hit_count
        FROM price_hourly p
        JOIN markets m ON p.market_id = m.id
        WHERE p.price_last > 0.99
          AND m.range_start IS NOT NULL
        GROUP BY m.range_start, m.range_end
        ORDER BY hit_count DESC
        LIMIT 1
    """)
    if not hot_range.empty:
        r_start = int(hot_range['range_start'].iloc[0])
        r_end = hot_range['range_end'].iloc[0]
        if pd.isna(r_end):
            hot_range_label = f"{r_start}+"
        else:
            hot_range_label = f"{r_start}-{int(r_end)}"
    else:
        hot_range_label = "暂无数据"

    return {
        'total_events': total_events,
        'total_tweets': int(total_tweets) if total_tweets else 0,
        'hit_count': hit_count,
        'hot_range': hot_range_label,
    }


def get_hit_distribution() -> pd.DataFrame:
    """获取命中市场分布（事件 × 区间热力图数据）"""
    query = """
        SELECT 
            e.slug as event_slug,
            e.start_date,
            e.end_date,
            m.range_start,
            m.range_end,
            m.is_plus,
            MAX(CASE WHEN p.price_last > 0.99 THEN 1 ELSE 0 END) as is_hit
        FROM events e
        JOIN markets m ON e.id = m.event_id
        JOIN price_hourly p ON m.id = p.market_id
        WHERE e.slug LIKE 'elon-musk-of-tweets%'
          AND m.range_start IS NOT NULL
        GROUP BY e.id, m.id
        ORDER BY e.start_date
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()

    # 构建区间标签
    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )

    # 生成简化事件标签：MMDD-MMDD-YYYY
    def make_short_label(start_date, end_date):
        try:
            start_dt = pd.to_datetime(start_date, format='mixed', utc=True)
            end_dt = pd.to_datetime(end_date, format='mixed', utc=True)
            return f"{start_dt.strftime('%m%d')}-{end_dt.strftime('%m%d')}-{start_dt.strftime('%Y')}"
        except:
            return start_date[:10] if start_date else "Unknown"

    df['event_short'] = df.apply(
        lambda row: make_short_label(row['start_date'], row['end_date']),
        axis=1
    )

    # 按 range_start 排序（保证纵坐标顺序）
    df = df.sort_values('range_start').reset_index(drop=True)
    df['start_date'] = pd.to_datetime(df['start_date'], format='mixed', utc=True)
    return df


def get_tweet_timeline(days_back: int = 30) -> pd.DataFrame:
    """获取推文时间序列"""
    query = f"""
        SELECT 
            datetime(timestamp_unix_utc, 'unixepoch') as hour_utc,
            tweet_count
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= (strftime('%s', 'now') - {days_back * 86400})
        ORDER BY timestamp_unix_utc
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()
    df['hour_utc'] = pd.to_datetime(df['hour_utc'])
    return df


def get_tweet_heatmap() -> pd.DataFrame:
    """获取推文热力图数据（小时 × 星期）"""
    query = """
        SELECT 
            strftime('%w', timestamp_unix_utc, 'unixepoch') as dow,
            strftime('%H', timestamp_unix_utc, 'unixepoch') as hour,
            AVG(tweet_count) as avg_tweets
        FROM tweet_hourly
        GROUP BY dow, hour
        ORDER BY dow, hour
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()

    dow_names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    df['dow_label'] = df['dow'].astype(int).map(lambda x: dow_names[x] if x < 7 else 'Unknown')
    return df


def get_correlation_data() -> pd.DataFrame:
    """获取价格与推文的相关性数据（按小时关联）"""
    query = """
        SELECT 
            p.price_last,
            p.price_avg,
            t.tweet_count
        FROM price_hourly p
        JOIN tweet_hourly t ON p.hour_start_utc = t.timestamp_unix_utc
        WHERE p.price_last IS NOT NULL 
          AND t.tweet_count IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10000
    """
    df = run_query(query)
    return df


def get_histogram_data() -> pd.DataFrame:
    """获取命中区间直方图数据"""
    query = """
        SELECT 
            m.range_start,
            m.range_end,
            m.is_plus,
            COUNT(*) as hit_count
        FROM price_hourly p
        JOIN markets m ON p.market_id = m.id
        WHERE p.price_last > 0.99
          AND m.range_start IS NOT NULL
        GROUP BY m.range_start, m.range_end
        ORDER BY m.range_start
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()
    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )
    return df


def get_event_timeline_events() -> pd.DataFrame:
    """获取所有事件的时间线数据（用于联动）"""
    query = """
        SELECT 
            id,
            slug,
            start_date,
            end_date
        FROM events
        WHERE slug LIKE 'elon-musk-of-tweets%'
        ORDER BY start_date
    """
    return run_query(query)


# ===== 新增：移动平均 =====
def get_ma_values() -> dict:
    """获取 24小时、7天、14天的推文平均值"""
    now_ts = int(datetime.now().timestamp())
    day_seconds = 86400

    # 24小时
    query_24h = f"""
        SELECT AVG(tweet_count) as avg_24h
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= {now_ts - day_seconds}
    """
    # 7天
    query_7d = f"""
        SELECT AVG(tweet_count) as avg_7d
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= {now_ts - 7 * day_seconds}
    """
    # 14天
    query_14d = f"""
        SELECT AVG(tweet_count) as avg_14d
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= {now_ts - 14 * day_seconds}
    """

    avg_24h = run_query(query_24h)['avg_24h'].iloc[0] if not run_query(query_24h).empty else 0
    avg_7d = run_query(query_7d)['avg_7d'].iloc[0] if not run_query(query_7d).empty else 0
    avg_14d = run_query(query_14d)['avg_14d'].iloc[0] if not run_query(query_14d).empty else 0

    return {
        'ma_24h': round(avg_24h, 1) if avg_24h else 0,
        'ma_7d': round(avg_7d, 1) if avg_7d else 0,
        'ma_14d': round(avg_14d, 1) if avg_14d else 0,
    }


def get_hourly_distribution() -> pd.DataFrame:
    """获取 24 小时平均推文分布"""
    query = """
        SELECT 
            strftime('%H', timestamp_unix_utc, 'unixepoch') as hour,
            AVG(tweet_count) as avg_tweets
        FROM tweet_hourly
        GROUP BY hour
        ORDER BY hour
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()
    df['hour'] = df['hour'].astype(int)
    return df


# ===== 新增：各区间平均存活时长 =====
def get_survival_by_range() -> pd.DataFrame:
    """
    获取各子市场的平均存活时长
    定义：从事件 game_start_time 到该市场最后一条价格记录的时间（小时）
    """
    query = """
        SELECT 
            m.range_start,
            m.range_end,
            AVG((max_p.hour_start_utc - e.game_start_time)) / 3600 as avg_survival_hours,
            COUNT(*) as sample_count
        FROM (
            SELECT market_id, MAX(hour_start_utc) as hour_start_utc
            FROM price_hourly
            GROUP BY market_id
        ) max_p
        JOIN markets m ON max_p.market_id = m.id
        JOIN events e ON m.event_id = e.id
        WHERE e.game_start_time IS NOT NULL
          AND m.range_start IS NOT NULL
        GROUP BY m.range_start, m.range_end
        ORDER BY m.range_start
    """
    df = run_query(query)
    if df.empty:
        return pd.DataFrame()

    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )
    return df