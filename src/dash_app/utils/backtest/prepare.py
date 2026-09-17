"""
回测数据准备 - 从 params 组装好要回测的 DataFrame
从 runner.py 拆出，让数据准备和回测执行各司其职
"""

import pandas as pd

from src.dash_app.utils.data_loader import (
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_gamestart_label,
    get_window_start_timestamp,
)


def prepare_backtest_data(params: dict):
    """
    准备回测数据

    Args:
        params: 回测参数字典

    Returns:
        dict: {
            'combined': DataFrame,       # merge + 过滤后的数据
            'median': float,             # 市场中位数
            'remaining_hours': int,      # 事件总小时数
            'window_mode': str,
            'window_param': int,
            'window_start': str,
            'window_start_ts': int,
        } 或 None（数据不足时）
    """
    market_id = params.get('market_id')
    event_id = params.get('event_id')

    # 1. 获取价格数据
    price_df = get_price_data_for_market(market_id)
    if price_df.empty:
        return None

    # 2. 获取推文数据
    tweet_df = get_tweet_data_for_event(event_id)

    # 3. Merge
    combined = pd.merge(price_df, tweet_df, on='datetime_utc', how='left')
    combined['tweet_count'] = combined['tweet_count'].fillna(0)
    combined = combined.sort_values('datetime_utc').reset_index(drop=True)

    # 4. 区间过滤
    backtest_range = params.get('backtest_range', 'full')
    if backtest_range in ['pre', 'post']:
        gamestart_label = get_event_gamestart_label(event_id)
        if gamestart_label:
            gamestart_dt = pd.to_datetime(gamestart_label, utc=True)
            gamestart_ts = int(gamestart_dt.timestamp())
            if backtest_range == 'pre':
                combined = combined[combined['hour_start_utc'] < gamestart_ts]
            else:
                combined = combined[combined['hour_start_utc'] >= gamestart_ts]
            if combined.empty:
                return None
    elif backtest_range == 'custom':
        pct = params.get('backtest_range_custom', [0, 100])
        total_len = len(combined)
        start_idx = int(total_len * pct[0] / 100)
        end_idx = int(total_len * pct[1] / 100)
        if end_idx <= start_idx:
            return None
        combined = combined.iloc[start_idx:end_idx].reset_index(drop=True)

    if len(combined) < 10:
        return None

    # 5. 窗口参数解析
    median = get_market_median(market_id)
    remaining_hours = get_event_remaining_hours(event_id)

    window_mode = params.get('window_mode', 'rolling')
    window_param = params.get('window_param', 168)
    window_start = params.get('window_start', None)
    window_start_ts = None
    if window_mode == 'expanding' and window_start:
        window_start_ts = get_window_start_timestamp(event_id, window_start)

    return {
        'combined': combined,
        'median': median,
        'remaining_hours': remaining_hours,
        'window_mode': window_mode,
        'window_param': window_param,
        'window_start': window_start,
        'window_start_ts': window_start_ts,
    }