"""
统计分析加载器
为数据分析中心提供聚合查询函数
"""

import pandas as pd
import numpy as np
from .data_loader import run_query


def get_overview_stats() -> dict:
    """获取核心 KPI 指标"""
    events = run_query("""
        SELECT COUNT(*) as total_events
        FROM events
        WHERE slug LIKE 'elon-musk-of-tweets%'
    """)
    total_events = events['total_events'].iloc[0] if not events.empty else 0

    tweets = run_query("""
        SELECT SUM(tweet_count) as total_tweets
        FROM tweet_hourly
    """)
    total_tweets = tweets['total_tweets'].iloc[0] if not tweets.empty else 0

    hit_markets = run_query("""
        SELECT COUNT(DISTINCT market_id) as hit_count
        FROM price_hourly
        WHERE price_last > 0.99
    """)
    hit_count = hit_markets['hit_count'].iloc[0] if not hit_markets.empty else 0

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

    duration = run_query("""
        SELECT AVG((julianday(end_date) - julianday(start_date)) * 24) as avg_duration_hours
        FROM events
        WHERE slug LIKE 'elon-musk-of-tweets%'
    """)
    avg_duration = duration['avg_duration_hours'].iloc[0] if not duration.empty else 0

    total_markets = run_query("""
        SELECT COUNT(DISTINCT market_id) as total_markets
        FROM price_hourly
    """)
    total_markets_count = total_markets['total_markets'].iloc[0] if not total_markets.empty else 1

    hit_rate = hit_count / total_markets_count * 100 if total_markets_count > 0 else 0

    return {
        'total_events': total_events,
        'total_tweets': int(total_tweets) if total_tweets else 0,
        'hit_count': hit_count,
        'hit_rate': round(hit_rate, 1),
        'hot_range': hot_range_label,
        'avg_duration': round(avg_duration, 1) if avg_duration else 0
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

    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )
    df['start_date'] = pd.to_datetime(df['start_date'], format='ISO8601')
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
    """获取价格与推文的相关性数据"""
    query = """
        SELECT 
            p.price_last,
            p.price_avg,
            t.tweet_count
        FROM price_hourly p
        LEFT JOIN tweet_hourly t ON p.hour_start_utc = t.timestamp_unix_utc
        WHERE t.tweet_count IS NOT NULL
          AND p.price_last IS NOT NULL
        ORDER BY RANDOM()
        LIMIT 10000
    """
    return run_query(query)


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