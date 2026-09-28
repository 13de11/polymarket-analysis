# src/dash_app/utils/metrics/hold_period.py
"""
持仓周期分析 - 分桶自适应

分桶策略：按 trades 里的最大持仓时长，选择合适的分桶边界。
- ≤ 1h  ：[0, 0.25, 0.5, 0.75, 1]
- ≤ 4h  ：[0, 1, 2, 3, 4]
- ≤ 12h ：[0, 2, 4, 8, 12]
- ≤ 24h ：[0, 4, 8, 16, 24]
- ≤ 48h ：[0, 8, 16, 32, 48]
- ≤ 168h：[0, 24, 48, 96, 168]
- 更大   ：[0, 2, 6, 12, 24]
"""

import pandas as pd


def _choose_buckets(max_hours: float):
    """按最大持仓时长选择分桶边界与标签"""
    if max_hours <= 0:
        return None, None

    candidates = [
        (1,   [0, 0.25, 0.5, 0.75, 1]),
        (4,   [0, 1, 2, 3, 4]),
        (12,  [0, 2, 4, 8, 12]),
        (24,  [0, 4, 8, 16, 24]),
        (48,  [0, 8, 16, 32, 48]),
        (168, [0, 24, 48, 96, 168]),
    ]
    edges = [0, 2, 6, 12, 24]  # 默认（>168h）
    for max_v, cand in candidates:
        if max_hours <= max_v:
            edges = cand
            break

    edges = edges + [float('inf')]
    labels = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if hi == float('inf'):
            labels.append(f"≥{lo:g}h")
        else:
            labels.append(f"{lo:g}-{hi:g}h")
    return edges, labels


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

    completed = [t for t in trades
                 if t.get('result') != 'pending'
                 and t.get('hold_hours') is not None]
    if not completed:
        return pd.DataFrame()

    df = pd.DataFrame([{
        'hold_hours': t.get('hold_hours', 0),
        'profit': t.get('profit', 0),
        'is_win': 1 if t.get('profit', 0) > 0 else 0,
    } for t in completed])

    max_hours = float(df['hold_hours'].max())
    edges, labels = _choose_buckets(max_hours)
    if edges is None:
        return pd.DataFrame()

    df['bucket'] = pd.cut(df['hold_hours'], bins=edges,
                          labels=labels, right=False)

    grouped = df.groupby('bucket', observed=False).agg(
        win_rate=('is_win', 'mean'),
        avg_return=('profit', 'mean'),
        count=('profit', 'count'),
    ).reset_index()

    # 过滤空桶（避免前端显示 nan）
    grouped = grouped[grouped['count'] > 0].copy()
    grouped['win_rate'] = grouped['win_rate'] * 100

    return grouped