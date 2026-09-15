"""
回测执行器 - 从页面层抽出的纯业务逻辑
供 prediction_backtest 页面、comparison、sensitivity 共用
"""

import pandas as pd
import numpy as np

from src.dash_app.utils.data_loader import (
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_gamestart_label,
    get_window_start_timestamp,
)
from src.dash_app.utils.signal.generator import DirectionSignalGenerator
from src.dash_app.utils.backtest.engine import BacktestEngine


def run_backtest(params: dict, series='7d'):
    """执行回测"""
    try:
        market_id = params.get('market_id')
        price_type = params.get('price_type', 'price_last')
        event_id = params.get('event_id')

        price_df = get_price_data_for_market(market_id)
        if price_df.empty:
            return None

        tweet_df = get_tweet_data_for_event(event_id)

        combined = pd.merge(price_df, tweet_df, on='datetime_utc', how='left')
        combined['tweet_count'] = combined['tweet_count'].fillna(0)
        combined = combined.sort_values('datetime_utc').reset_index(drop=True)

        # ===== 区间过滤（使用 hour_start_utc） =====
        backtest_range = params.get('backtest_range', 'full')
        if backtest_range in ['pre', 'post']:
            gamestart_label = get_event_gamestart_label(event_id)
            if gamestart_label:
                gamestart_dt = pd.to_datetime(gamestart_label, utc=True)
                gamestart_ts = int(gamestart_dt.timestamp())
                if backtest_range == 'pre':
                    combined = combined[combined['hour_start_utc'] < gamestart_ts]
                else:  # post
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
        # ===== 区间过滤结束 =====

        if len(combined) < 10:
            return None

        median = get_market_median(market_id)
        remaining_hours = get_event_remaining_hours(event_id)

        # ---- 解析窗口参数 ----
        window_mode = params.get('window_mode', 'rolling')
        window_param = params.get('window_param', 168)
        window_start = params.get('window_start', None)
        window_start_ts = None
        if window_mode == 'expanding' and window_start:
            window_start_ts = get_window_start_timestamp(event_id, window_start)

        signal_params = {
            'capacity': params.get('capacity', 0),
            'price_threshold': params.get('price_threshold', 0.005),
            'distance_threshold': params.get('distance_threshold', 1.5),
            'inertia_hours': params.get('inertia', 6),
            'momentum_enable': params.get('momentum_enable', True),
            'momentum_coef': params.get('momentum_coef', 0.10),
            'signal_mode': params.get('signal_mode', 'full'),
            'median': median,
            'remaining_hours': remaining_hours,
            'window_mode': window_mode,
            'window_param': window_param,
            'window_start': window_start,
            'window_start_ts': window_start_ts,
        }

        generator = DirectionSignalGenerator(signal_params)
        price_col = price_type
        price_df_renamed = combined[['datetime_utc', price_col]].rename(
            columns={'datetime_utc': 'timestamp', price_col: 'price'}
        )
        tweet_df_renamed = combined[['datetime_utc', 'tweet_count']].rename(
            columns={'datetime_utc': 'timestamp'}
        )
        signal_df = generator.generate_signals(price_df_renamed, tweet_df_renamed)

        if signal_df.empty:
            return None

        engine = BacktestEngine(
            initial_capital=params.get('initial_capital', 100),
            position_mode=params.get('position_mode', 'fixed_amount'),
            position_size=params.get('position_size', 10),
        )
        result = engine.run(signal_df, price_col='price')

        # ---- 序列化：把 Timestamp 转成字符串，供 dcc.Store 缓存 ----
        if result:
            for e in result.get('equity_curve', []):
                ts = e.get('timestamp')
                if hasattr(ts, 'isoformat'):
                    e['timestamp'] = ts.isoformat()
            for t in result.get('trades', []):
                for key in ('entry_time', 'exit_time'):
                    ts = t.get(key)
                    if hasattr(ts, 'isoformat'):
                        t[key] = ts.isoformat()

        return result

    except Exception as e:
        print(f"回测错误: {e}")
        import traceback
        traceback.print_exc()
        return None