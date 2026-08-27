"""
信号过滤器 - 信号后处理
"""

import pandas as pd


def apply_signal_mode(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    """
    应用信号模式过滤

    Args:
        df: DataFrame with column 'signal'
        mode: 'full' | 'start' | 'end'

    Returns:
        DataFrame with filtered signal column
    """
    if mode == 'full':
        return df

    df_copy = df.copy()
    df_copy['signal_original'] = df_copy['signal']

    if mode == 'start':
        # 只保留趋势起点
        shifted = df_copy['signal'].shift(1)
        df_copy['signal'] = df_copy['signal'].where(
            df_copy['signal'] != shifted, ''
        )
    elif mode == 'end':
        # 只保留趋势终点
        shifted = df_copy['signal'].shift(-1)
        df_copy['signal'] = df_copy['signal'].where(
            df_copy['signal'] != shifted, ''
        )

    return df_copy.drop(columns=['signal_original'])