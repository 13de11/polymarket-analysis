"""
回测执行器
- 调用 prepare 准备数据
- 调用 generator 生成信号
- 调用 engine 执行回测
"""

import pandas as pd

from src.dash_app.utils.backtest.prepare import prepare_backtest_data
from src.dash_app.utils.signal.generator import DirectionSignalGenerator
from src.dash_app.utils.backtest.engine import BacktestEngine


def run_backtest(params: dict, series='7d'):
    """
    执行回测

    Returns:
        dict: {
            'trades': [...],
            'equity_curve': [...],
            'final_capital': float,
            'metrics': {...},
            'signal_df': DataFrame,   # 新增：完整信号序列（用于策略评估）
        } 或 None
    """
    try:
        # 1. 准备数据
        prepared = prepare_backtest_data(params)
        if prepared is None:
            return None

        combined = prepared['combined']

        # 2. 生成信号
        signal_params = {
            'capacity': params.get('capacity', 0),
            'price_threshold': params.get('price_threshold', 0.005),
            'distance_threshold': params.get('distance_threshold', 1.5),
            'inertia_hours': params.get('inertia', 6),
            'momentum_enable': params.get('momentum_enable', True),
            'momentum_coef': params.get('momentum_coef', 0.10),
            'signal_mode': params.get('signal_mode', 'full'),
            'median': prepared['median'],
            'remaining_hours': prepared['remaining_hours'],
            'window_mode': prepared['window_mode'],
            'window_param': prepared['window_param'],
            'window_start': prepared['window_start'],
            'window_start_ts': prepared['window_start_ts'],
        }

        price_type = params.get('price_type', 'price_last')
        price_df_renamed = combined[['datetime_utc', price_type]].rename(
            columns={'datetime_utc': 'timestamp', price_type: 'price'}
        )
        tweet_df_renamed = combined[['datetime_utc', 'tweet_count']].rename(
            columns={'datetime_utc': 'timestamp'}
        )

        generator = DirectionSignalGenerator(signal_params)
        signal_df = generator.generate_signals(price_df_renamed, tweet_df_renamed)

        if signal_df.empty:
            return None

        # 3. 执行回测
        engine = BacktestEngine(
            initial_capital=params.get('initial_capital', 100),
            position_mode=params.get('position_mode', 'fixed_amount'),
            position_size=params.get('position_size', 10),
        )
        result = engine.run(signal_df, price_col='price')

        # 注意：signal_df 不能放进 result（会被 dcc.Store 序列化失败）
        # 策略评估时如需 signal_df，重新生成一次
        return result

    except Exception as e:
        print(f"回测错误: {e}")
        import traceback
        traceback.print_exc()
        return None