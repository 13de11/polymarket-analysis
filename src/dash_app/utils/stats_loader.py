"""
统计分析加载器
为数据分析中心提供聚合查询函数
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date
from functools import lru_cache

from .data_loader import run_query

# F6: "市场命中"判定阈值——最终价格 > 此值视为该区间"达成"。
# 单一来源：stats_loader 的 SQL 与各页面文案统一引用此常量，
# 未来调整阈值只改这一处（当前 0.99，与历史行为一致）
HIT_THRESHOLD = 0.99

# 命中判定的统一口径：结算价 = 结算时刻（end_date）及之前最后一条价格记录。
# 不取"全表最后一条"：结算后同步到的价格可能回落（实测 7 月事件结算后出现 0.5 的脏数据）；
# 也不取"任一小时 > 阈值"：会把盘中冲高又回落的假信号误判为命中
_LATEST_PRICE_SUBQUERY = """
    SELECT p.market_id, p.price_last,
           ROW_NUMBER() OVER (PARTITION BY p.market_id ORDER BY p.hour_start_utc DESC) as rn
    FROM price_hourly p
    JOIN markets m2 ON p.market_id = m2.id
    JOIN events e2 ON m2.event_id = e2.id
    WHERE p.hour_start_utc <= CAST(strftime('%s', e2.end_date) AS INTEGER)
"""


def get_series_condition(series: str = '7d', table_alias: str = 'e') -> str:
    """
    返回 SQL WHERE 条件
    由于 SQLite 无法解析 slug 的日期跨度，这里返回宽松条件，
    由 Python 层通过 get_elon_tweet_events 过滤
    """
    return f"({table_alias}.slug LIKE 'elon-musk-of-tweets%')"


def _filter_events_by_window(events_df: pd.DataFrame, window_days) -> pd.DataFrame:
    """按窗口天数过滤事件：只保留窗口内结束的事件。

    window_days 为 None / 'all' 时不过滤（全系列口径，首页等调用方沿用）。
    """
    if window_days in (None, 'all'):
        return events_df
    cutoff = pd.Timestamp.now(tz='UTC') - pd.Timedelta(days=int(window_days))
    df = events_df.copy()
    end_dt = pd.to_datetime(df['end_date'], format='mixed', utc=True)
    return df[end_dt >= cutoff]


def _filter_events_data_complete(events_df: pd.DataFrame) -> pd.DataFrame:
    """过滤掉价格数据未同步到结算时间的事件。

    事件 end_date 已过但价格数据停在结束之前（同步滞后）时，无法判定命中，
    统计口径上视为"未就绪"，不参与数据分析中心的统计。
    判定标准：价格数据最后小时 >= end_date - 1 小时
    （已完结事件的数据通常超出 end_date 2~3 小时，未同步的事件缺口在半天以上）。
    """
    if events_df.empty:
        return events_df
    event_ids = tuple(events_df['id'].tolist())
    placeholders = ','.join(['?'] * len(event_ids))
    cov = run_query(f"""
        SELECT m.event_id, MAX(p.hour_start_utc) as max_hour
        FROM markets m
        JOIN price_hourly p ON p.market_id = m.id
        WHERE m.event_id IN ({placeholders})
        GROUP BY m.event_id
    """, event_ids)
    df = events_df.copy()
    # 注意：pandas 3.0 的 to_datetime 默认微秒精度，astype('int64') 是微秒值，
    # 不能直接 //10**9 转秒；用 Timestamp.timestamp() 逐个转换与精度无关
    df['_end_ts'] = pd.to_datetime(df['end_date'], format='mixed', utc=True).map(
        lambda x: int(x.timestamp()))
    df['_max_hour'] = df['id'].map(dict(zip(cov['event_id'], cov['max_hour'])))
    mask = df['_max_hour'].notna() & (df['_max_hour'] >= df['_end_ts'] - 3600)
    return df[mask].drop(columns=['_end_ts', '_max_hour'])


def _range_label(range_start, range_end) -> str:
    """推文区间标签：如 '105-129'；无上界时为 '230+'"""
    if pd.isna(range_end):
        return f"{int(range_start)}+"
    return f"{int(range_start)}-{int(range_end)}"


def _event_tweet_stats(event_row) -> dict:
    """单个事件统计区间（gamestart→结算，缺 gamestart 用 start_date）内的推文指标

    返回 {'total': 总推文, 'peak': 单小时峰值, 'avg_per_hour': 平均每小时推文}
    """
    start_raw = event_row['game_start_time'] if event_row['game_start_time'] else event_row['start_date']
    start_dt = pd.to_datetime(start_raw, format='mixed', utc=True)
    end_dt = pd.to_datetime(event_row['end_date'], format='mixed', utc=True)
    start_ts, end_ts = int(start_dt.timestamp()), int(end_dt.timestamp())
    duration_h = max((end_ts - start_ts) / 3600, 1)

    df = run_query("""
        SELECT SUM(tweet_count) as total, MAX(tweet_count) as peak
        FROM tweet_hourly
        WHERE timestamp_unix_utc >= ? AND timestamp_unix_utc < ?
    """, (start_ts, end_ts))
    total = int(df['total'].iloc[0]) if not df.empty and df['total'].iloc[0] else 0
    peak = int(df['peak'].iloc[0]) if not df.empty and df['peak'].iloc[0] else 0
    return {'total': total, 'peak': peak, 'avg_per_hour': round(total / duration_h, 1)}


@lru_cache(maxsize=32)
def _get_overview_stats_cached(series: str, window_days, cache_key: str) -> dict:
    """内部：带缓存的窗口化总览统计。cache_key 为当日日期，每日自动失效

    window_days=None 表示不过滤（全系列口径，首页沿用）。
    """
    from src.dash_app.utils.data_loader import get_elon_tweet_events

    # 窗口过滤 + 数据完整性过滤（价格数据未同步到结算的事件不参与统计）
    events_df = _filter_events_data_complete(
        _filter_events_by_window(get_elon_tweet_events(series), window_days))
    if events_df.empty:
        return {
            'total_events': 0, 'total_tweets': 0, 'sub_market_count': 0,
            'hit_count': 0, 'last_hit_label': '暂无命中',
            'hot_range_label': '暂无数据', 'hot_range_hits': 0,
            'hot_range_ratio': '—', 'latest_event': None,
        }

    event_ids = tuple(events_df['id'].tolist())
    placeholders = ','.join(['?'] * len(event_ids))
    total_events = len(event_ids)

    # 窗口内事件推文合计（逐事件按其统计区间累加，避免混入窗口外推文）
    total_tweets = sum(_event_tweet_stats(ev)['total'] for _, ev in events_df.iterrows())

    # 子市场总数（命中率的分母）
    sub_df = run_query(
        f"SELECT COUNT(*) AS n FROM markets WHERE event_id IN ({placeholders})",
        event_ids)
    sub_market_count = int(sub_df['n'].iloc[0]) if not sub_df.empty else 0

    # 命中市场数（口径：市场最后一条价格记录 > 阈值，即结算价命中）
    hit_markets = run_query(f"""
        SELECT COUNT(*) as hit_count
        FROM ({_LATEST_PRICE_SUBQUERY}) lp
        JOIN markets m ON lp.market_id = m.id
        WHERE lp.rn = 1
          AND lp.price_last > {HIT_THRESHOLD}
          AND m.event_id IN ({placeholders})
    """, event_ids)
    hit_count = int(hit_markets['hit_count'].iloc[0]) if not hit_markets.empty else 0

    # 最热区间（窗口内命中次数最多的推文区间；按命中市场数去重）
    hot = run_query(f"""
        SELECT m.range_start, m.range_end, COUNT(DISTINCT lp.market_id) as hit_count
        FROM ({_LATEST_PRICE_SUBQUERY}) lp
        JOIN markets m ON lp.market_id = m.id
        WHERE lp.rn = 1
          AND lp.price_last > {HIT_THRESHOLD}
          AND m.range_start IS NOT NULL
          AND m.event_id IN ({placeholders})
        GROUP BY m.range_start, m.range_end
        ORDER BY hit_count DESC
        LIMIT 1
    """, event_ids)
    if not hot.empty:
        hot_range_label = _range_label(hot['range_start'].iloc[0], hot['range_end'].iloc[0])
        hot_range_hits = int(hot['hit_count'].iloc[0])
        pct = hot_range_hits / total_events if total_events else 0
        hot_range_ratio = f"{hot_range_hits}/{total_events}（{pct:.0%}）"
    else:
        hot_range_label, hot_range_hits, hot_range_ratio = '暂无数据', 0, '—'

    # 最近命中：最近一个出现命中的事件及其命中的推文区间（结算价口径）
    last_hit = run_query(f"""
        SELECT e.end_date, m.range_start, m.range_end
        FROM ({_LATEST_PRICE_SUBQUERY}) lp
        JOIN markets m ON lp.market_id = m.id
        JOIN events e ON m.event_id = e.id
        WHERE lp.rn = 1
          AND lp.price_last > {HIT_THRESHOLD}
          AND m.range_start IS NOT NULL
          AND e.id IN ({placeholders})
    """, event_ids)
    if not last_hit.empty:
        last_hit['_end'] = pd.to_datetime(last_hit['end_date'], format='mixed', utc=True)
        rows = last_hit[last_hit['_end'] == last_hit['_end'].max()]
        labels = sorted({_range_label(r['range_start'], r['range_end']) for _, r in rows.iterrows()})
        last_hit_label = f"{'、'.join(labels)}（{rows['_end'].iloc[0].strftime('%m-%d')} 事件）"
    else:
        last_hit_label = '暂无命中'

    # 最近一个已结束事件的推文表现
    ev_df = events_df.copy()
    ev_df['_end'] = pd.to_datetime(ev_df['end_date'], format='mixed', utc=True)
    latest_ev = ev_df.sort_values('_end').iloc[-1]
    ev_stats = _event_tweet_stats(latest_ev)
    latest_event = {
        'label': latest_ev['_end'].strftime('%m-%d'),
        'total': ev_stats['total'],
        'avg_per_hour': ev_stats['avg_per_hour'],
        'peak': ev_stats['peak'],
    }

    return {
        'total_events': total_events,
        'total_tweets': total_tweets,
        'sub_market_count': sub_market_count,
        'hit_count': hit_count,
        'last_hit_label': last_hit_label,
        'hot_range_label': hot_range_label,
        'hot_range_hits': hot_range_hits,
        'hot_range_ratio': hot_range_ratio,
        'latest_event': latest_event,
    }


def get_overview_stats(series: str = '7d', window_days=None) -> dict:
    """获取总览统计（支持系列过滤 + 时间窗口过滤）

    window_days=None 时为全系列口径（首页沿用旧行为）；
    传入天数（如 30/45/60/90）时只统计窗口内已结束的事件。
    结果按天缓存，当日重复访问不重复查库。
    """
    key = None if window_days in (None, 'all') else int(window_days)
    return dict(_get_overview_stats_cached(series, key, date.today().isoformat()))


def get_hit_distribution(series: str = '7d', window_days=None) -> pd.DataFrame:
    """获取命中市场分布（支持系列过滤 + 时间窗口过滤 + 数据完整性过滤）

    is_hit 口径：市场最后一条价格记录（结算价）> HIT_THRESHOLD，
    与 get_histogram_data / README 定义一致。
    """
    from src.dash_app.utils.data_loader import get_elon_tweet_events

    events_df = _filter_events_data_complete(
        _filter_events_by_window(get_elon_tweet_events(series), window_days))
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
            CASE WHEN lp.price_last > {HIT_THRESHOLD} THEN 1 ELSE 0 END as is_hit
        FROM events e
        JOIN markets m ON e.id = m.event_id
        JOIN ({_LATEST_PRICE_SUBQUERY}) lp ON lp.market_id = m.id AND lp.rn = 1
        WHERE e.id IN ({placeholders})
          AND m.range_start IS NOT NULL
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


def get_correlation_data(limit: int = 10000) -> pd.DataFrame:
    """获取价格与推文的相关性数据（时间倒序采样，避免全表随机排序）"""
    query = """
        SELECT 
            p.price_last,
            p.price_avg,
            t.tweet_count
        FROM price_hourly p
        JOIN tweet_hourly t ON p.hour_start_utc = t.timestamp_unix_utc
        WHERE p.price_last IS NOT NULL 
          AND t.tweet_count IS NOT NULL
        ORDER BY p.hour_start_utc DESC
        LIMIT ?
    """
    df = run_query(query, (limit,))
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
        FROM ({_LATEST_PRICE_SUBQUERY}) latest
        JOIN markets m ON latest.market_id = m.id
        WHERE latest.rn = 1
          AND latest.price_last > {HIT_THRESHOLD}
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