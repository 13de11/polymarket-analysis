"""
方向准确率计算 - 支持多时间窗口
"""

import pandas as pd
import numpy as np


def calculate_multi_window_accuracy(signal_df, windows=(1, 6, 12, 24)):
    """
    计算多个时间窗口的方向准确率

    Args:
        signal_df: 包含 'timestamp', 'signal', 'price' 的 DataFrame
        windows: 时间窗口元组（小时）

    Returns:
        dict: {
            1: {'up_acc': 0.45, 'down_acc': 0.38, 'overall': 0.42, 'samples': 120},
            6: {...},
            ...
        }
    """
    result = {}
    signals = signal_df['signal'].values
    prices = signal_df['price'].values
    n = len(signals)

    for window in windows:
        up_correct = 0
        up_total = 0
        down_correct = 0
        down_total = 0

        for i in range(n):
            sig = signals[i]
            if sig not in ('↑', '↓'):
                continue

            target_idx = i + window
            if target_idx >= n:
                continue

            entry_price = prices[i]
            exit_price = prices[target_idx]

            if sig == '↑':
                up_total += 1
                if exit_price > entry_price:
                    up_correct += 1
            else:
                down_total += 1
                if exit_price < entry_price:
                    down_correct += 1

        total = up_total + down_total
        result[window] = {
            'up_acc': up_correct / up_total if up_total > 0 else 0,
            'down_acc': down_correct / down_total if down_total > 0 else 0,
            'overall': (up_correct + down_correct) / total if total > 0 else 0,
            'samples': total,
        }

    return result