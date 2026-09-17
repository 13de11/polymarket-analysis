"""
基线策略计算 - 用于对比当前策略的相对表现
"""

import pandas as pd
import numpy as np


def buy_and_hold(price_df, initial_capital=100):
    """
    全买持有：从头到尾持有，看最终收益

    Args:
        price_df: DataFrame with 'price' 列
        initial_capital: 初始资金

    Returns:
        dict: {'total_return': float(百分比), 'final_capital': float}
    """
    if price_df.empty or len(price_df) < 2:
        return {'total_return': 0, 'final_capital': initial_capital}

    prices = price_df['price'].dropna().values
    if len(prices) < 2:
        return {'total_return': 0, 'final_capital': initial_capital}

    start = prices[0]
    end = prices[-1]

    if start <= 0:
        return {'total_return': 0, 'final_capital': initial_capital}

    total_return = (end / start - 1) * 100
    final_capital = initial_capital * (end / start)

    return {
        'total_return': total_return,
        'final_capital': final_capital,
    }


def random_signal(price_df, n_signals=10, seed=42):
    """
    随机信号：随机生成 N 个 ↑/↓ 信号，按"↑ 买，↓ 卖"跑一遍

    Args:
        price_df: DataFrame with 'price' 列
        n_signals: 信号数量
        seed: 随机种子

    Returns:
        dict: {'total_return': float, 'final_capital': float, 'n_trades': int}
    """
    if price_df.empty or len(price_df) < 2:
        return {'total_return': 0, 'final_capital': 100, 'n_trades': 0}

    prices = price_df['price'].dropna().values
    n = len(prices)
    if n < 10:
        return {'total_return': 0, 'final_capital': 100, 'n_trades': 0}

    rng = np.random.default_rng(seed)

    # 随机选 n_signals 个位置
    n_signals = min(n_signals, n)
    idxs = sorted(rng.choice(n, n_signals, replace=False))

    # 模拟：随机给每个位置 ↑ 或 ↓
    cash = 100
    position = 0
    entry_price = 0
    trades = 0

    for idx in idxs:
        sig = rng.choice(['↑', '↓'])
        price = prices[idx]

        if sig == '↑' and position == 0 and price > 0:
            # 买
            position = cash / price
            entry_price = price
            cash = 0
        elif sig == '↓' and position > 0:
            # 卖
            cash = position * price
            position = 0
            trades += 1

    # 强制平仓
    if position > 0:
        cash = position * prices[-1]
        position = 0
        trades += 1

    final_capital = cash
    total_return = (final_capital / 100 - 1) * 100

    return {
        'total_return': total_return,
        'final_capital': final_capital,
        'n_trades': trades,
    }