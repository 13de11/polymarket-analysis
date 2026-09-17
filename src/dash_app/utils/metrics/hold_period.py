"""
持仓周期分析
"""

import pandas as pd
import numpy as np


def calculate_hold_period_analysis(trades):
    """
    分析持仓周期与胜率、收益的关系

    Args:
        trades: 交易记录列表

    Returns:
        DataFrame: 包含 'bucket', 'win_rate', 'avg_return', 'count'
    """
    if not trades:
        return pd.DataFrame()

    # 只看已完成的交易
    completed = [t for t in trades if t.get('result') != 'pending' and t.get('hold_hours') is not None]
    if not completed:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'hold_hours': t.get('hold_hours', 0),
        'profit': t.get('profit', 0),
        'is_win': 1 if t.get('profit', 0) > 0 else 0,
    } for t in completed])

    # 分桶：<2h, 2-6h, 6-12h, 12-24h, >24h
    bins = [0, 2, 6, 12, 24, float('inf')]
    labels = ['<2h', '2-6h', '6-12h', '12-24h', '>24h']
    df['bucket'] = pd.cut(df['hold_hours'], bins=bins, labels=labels, right=False)

    grouped = df.groupby('bucket', observed=False).agg(
        win_rate=('is_win', 'mean'),
        avg_return=('profit', 'mean'),
        count=('profit', 'count'),
    ).reset_index()

    grouped['win_rate'] = grouped['win_rate'] * 100  # 转百分比

    return grouped