"""
统计分析加载器
为数据分析中心提供聚合查询函数
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .data_loader import run_query


def get_series_condition(series: str = '7d', table_alias: str = 'e') -> str:
    """
    返回 SQL WHERE 条件
    由于 SQLite 无法解析 slug 的日期跨度，这里返回宽松条件，
    由 Python 层通过 get_elon_tweet_events 过滤
    """
    return f"({table_alias}.slug LIKE 'elon-musk-of-tweets%')"


def get_overview_stats(series: str = '7d') -> dict:
    """获取核心 KPI 指标（支持系列过滤）"""
    from src.dash_app.utils.data_loader import get_elon_tweet_events

    # 先获取该系列的事件列表
    events_df = get_elon_tweet_events(series)
    event_ids = tuple(events_df['id'].tolist()) if not events_df.empty else ()

    if not event_ids:
        return {
            'total_events': 0,
            'total_tweets': 0,
            'hit_count': 0,
            'hot_range': '暂无数据',
        }

    placeholders = ','.join(['?'] * len(event_ids))

    # 总事件数
    total_events = len(event_ids)

    # 总推文
    tweets = run_query("""
        SELECT SUM(tweet_count) as total_tweets
        FROM tweet_hourly
    """)
    total_tweets = tweets['total_tweets'].iloc[0] if not tweets.empty else 0

    # 命中市场（只统计该系列的市场）
    hit_markets = run_query(f"""
        SELECT COUNT(DISTINCT p.market_id) as hit_count
        FROM price_hourly p
        JOIN markets m ON p.market_id = m.id
        WHERE p.price_last > 0.99
          AND m.event_id IN ({placeholders})
    """, event_ids)
    hit_count = hit_markets['hit_count'].iloc[0] if not hit_markets.empty else 0

    # 最热区间
    hot_range = run_query(f"""
        SELECT m.range_start, m.range_end, COUNT(*) as hit_count
        FROM price_hourly p
        JOIN markets m ON p.market_id = m.id
        WHERE p.price_last > 0.99
          AND m.range_start IS NOT NULL
          AND m.event_id IN ({placeholders})
        GROUP BY m.range_start, m.range_end
        ORDER BY hit_count DESC
        LIMIT 1
    """, event_ids)

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


def get_hit_distribution(series: str = '7d') -> pd.DataFrame:
    """获取命中市场分布（支持系列过滤）"""
    from src.dash_app.utils.data_loader import get_elon_tweet_events

    events_df = get_elon_tweet_events(series)
    event_ids = tuple(events_df['id'].tolist()) if not events_df.empty else ()

    if not event_ids:
        return pd.DataFrame()

    placeholders = ','.join(['?'] * len(event_ids))

    query = f"""
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
        WHERE e.id IN ({placeholders})
          AND m.range_start IS NOT NULL
        GROUP BY e.id, m.id
        ORDER BY e.start_date
    """
    df = run_query(query, event_ids)
    if df.empty:
        return pd.DataFrame()

    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )

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
    """获取价格与推文的相关性数据"""
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


def get_histogram_data(series: str = '7d') -> pd.DataFrame:
    """获取命中区间直方图数据（支持系列过滤）"""
    from src.dash_app.utils.data_loader import get_elon_tweet_events

    events_df = get_elon_tweet_events(series)
    event_ids = tuple(events_df['id'].tolist()) if not events_df.empty else ()

    if not event_ids:
        return pd.DataFrame()

    placeholders = ','.join(['?'] * len(event_ids))

    query = f"""
        SELECT 
            m.range_start,
            m.range_end,
            COUNT(*) as hit_count
        FROM (
            SELECT 
                p.market_id,
                ROW_NUMBER() OVER (PARTITION BY p.market_id ORDER BY p.hour_start_utc DESC) as rn
            FROM price_hourly p
            WHERE p.price_last > 0.99
        ) latest
        JOIN markets m ON latest.market_id = m.id
        WHERE latest.rn = 1
          AND m.range_start IS NOT NULL
          AND m.event_id IN ({placeholders})
        GROUP BY m.range_start, m.range_end
        ORDER BY m.range_start
    """
    df = run_query(query, event_ids)
    if df.empty:
        return pd.DataFrame()
    df['range_label'] = df.apply(
        lambda row: f"{int(row['range_start'])}-{int(row['range_end']) if not pd.isna(row['range_end']) else '∞'}",
        axis=1
    )
    return df


def get_event_timeline_events(series: str = '7d') -> pd.DataFrame:
    """获取所有事件的时间线数据（支持系列过滤）"""
    from src.dash_app.utils.data_loader import get_elon_tweet_events
    df = get_elon_tweet_events(series)
    if df.empty:
        return df
    return df[['id', 'slug', 'start_date', 'end_date']]


def get_ma_values() -> dict:
    """获取 24小时、7天、14天的推文平均值"""
    now_ts = int(datetime.now().timestamp())
    day_seconds = 86400

    query_24h = f"""
        SELECT AVG(tweet_count) as avg_24h
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= {now_ts - day_seconds}
    """
    query_7d = f"""
        SELECT AVG(tweet_count) as avg_7d
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= {now_ts - 7 * day_seconds}
    """
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


def get_survival_by_range() -> pd.DataFrame:
    """获取各子市场的平均存活时长"""
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


def get_tweet_matrix(start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """获取日期 × 小时的推文矩阵"""
    conditions = []
    params = []

    if start_date:
        start_ts = int(pd.to_datetime(start_date).timestamp())
        conditions.append("timestamp_unix_utc >= ?")
        params.append(start_ts)
    if end_date:
        end_ts = int(pd.to_datetime(end_date).timestamp())
        conditions.append("timestamp_unix_utc <= ?")
        params.append(end_ts)

    query = """
        SELECT 
            DATE(timestamp_unix_utc, 'unixepoch') as date,
            strftime('%H', timestamp_unix_utc, 'unixepoch') as hour,
            tweet_count
        FROM tweet_hourly
    """
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    df = run_query(query, tuple(params))
    if df.empty:
        return pd.DataFrame()
    return df


def get_event_time_range(event_id: str) -> tuple:
    """
    从 events 表的 slug 解析推文统计周期
    例如: elon-musk-of-tweets-june-2-june-9
    返回: (start_date_str, end_date_str)
    """
    query = """
        SELECT slug
        FROM events
        WHERE id = ?
    """
    df = run_query(query, (event_id,))
    if df.empty:
        return (None, None)

    slug = df['slug'].iloc[0]

    # 移除前缀 "elon-musk-of-tweets-"
    import re
    parts = slug.replace('elon-musk-of-tweets-', '').split('-')
    if len(parts) < 4:
        return (None, None)

    month_map = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4,
        'may': 5, 'june': 6, 'july': 7, 'august': 8,
        'september': 9, 'october': 10, 'november': 11, 'december': 12
    }

    pattern = r'([a-z]+)-(\d{1,2})-([a-z]+)-(\d{1,2})(?:-(\d{4}))?'
    match = re.search(pattern, slug)
    if not match:
        return (None, None)

    start_month_str = match.group(1)
    start_day = int(match.group(2))
    end_month_str = match.group(3)
    end_day = int(match.group(4))
    year_str = match.group(5) if match.group(5) else None

    start_month = month_map.get(start_month_str.lower())
    end_month = month_map.get(end_month_str.lower())

    if not start_month or not end_month:
        return (None, None)

    import datetime
    if year_str:
        year = int(year_str)
    else:
        year_query = """
            SELECT strftime('%Y', start_date) as year
            FROM events
            WHERE id = ?
        """
        year_df = run_query(year_query, (event_id,))
        if not year_df.empty:
            year = int(year_df['year'].iloc[0])
        else:
            year = 2026

    start_dt = datetime.datetime(year, start_month, start_day, 16, 0, 0)
    end_dt = datetime.datetime(year, end_month, end_day, 16, 0, 0)

    return (start_dt.isoformat(), end_dt.isoformat())