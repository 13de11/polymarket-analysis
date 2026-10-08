"""
回测数据准备 - 从 params 组装好要回测的 DataFrame

缓存策略：
- 以 (market_id, event_id, backtest_range, backtest_range_custom,
       window_mode, window_param, window_start) 为 key
- 每日自动失效一次（与 data_loader 一致）
- 缓存输出的是 prepared dict（含 DataFrame），调用方只读使用
"""

from datetime import date
from functools import lru_cache

import pandas as pd

from src.dash_app.utils.data_loader import (
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_gamestart_label,
    get_window_start_timestamp,
)


def _daily_key() -> str:
    return date.today().isoformat()


@lru_cache(maxsize=64)
def _prepare_cached(market_id, event_id, backtest_range,
                    backtest_range_custom_t, window_mode, window_param,
                    window_start, cache_key):
    """实际计算，参数全部可哈希。cache_key 用于每日失效。"""
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
        pct = list(backtest_range_custom_t)
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


def prepare_backtest_data(params: dict):
    """
    准备回测数据（带缓存）

    Returns:
        dict: {
            'combined': DataFrame,
            'median': float,
            'remaining_hours': int,
            'window_mode': str,
            'window_param': int,
            'window_start': str,
            'window_start_ts': int,
        } 或 None（数据不足时）
    """
    market_id = params.get('market_id')
    event_id = params.get('event_id')
    backtest_range = params.get('backtest_range', 'full')
    backtest_range_custom = params.get('backtest_range_custom') or [0, 100]
    window_mode = params.get('window_mode', 'rolling')
    window_param = params.get('window_param', 168)
    window_start = params.get('window_start', None)

    return _prepare_cached(
        market_id,
        event_id,
        backtest_range,
        tuple(backtest_range_custom),
        window_mode,
        window_param,
        window_start,
        _daily_key(),
    )


def clear_prepare_cache():
    """手动清空 prepare 缓存（数据更新后立即生效）"""
    _prepare_cached.cache_clear()