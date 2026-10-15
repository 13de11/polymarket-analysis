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
            1: {'up_acc': 0.45, 'down_acc': 0.38, 'overall': 0.42,
                'samples': 120,
                'avg_correct_move': 0.8,   # F3: 对时均幅（%，正=朝预测方向）
                'avg_wrong_move': -0.3,    # F3: 错时均幅（%，负=反向）
                'expectancy': 0.25},       # F3: 每信号期望幅度（%）
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
        correct_moves = []   # F3: 判断正确时的方向幅度（%）
        wrong_moves = []     # F3: 判断错误时的方向幅度（%，负值）

        for i in range(n):
            sig = signals[i]
            if sig not in ('↑', '↓'):
                continue

            target_idx = i + window
            if target_idx >= n:
                continue

            entry_price = prices[i]
            exit_price = prices[target_idx]

            # F3: 方向幅度（%）——↑按原始涨跌幅，↓取反（做空视角）。
            # 正确时为正、错误时为负，弥补"只看方向不看大小"的盲区：
            # 涨 0.001 和涨 0.05 都算方向正确，但对时均幅会揭示前者没肉
            move_pct = (exit_price - entry_price) / entry_price * 100
            if sig == '↓':
                move_pct = -move_pct

            if sig == '↑':
                up_total += 1
                correct = exit_price > entry_price
            else:
                down_total += 1
                correct = exit_price < entry_price

            if correct:
                if sig == '↑':
                    up_correct += 1
                else:
                    down_correct += 1
                correct_moves.append(move_pct)
            else:
                wrong_moves.append(move_pct)

        total = up_total + down_total
        all_moves = correct_moves + wrong_moves
        result[window] = {
            'up_acc': up_correct / up_total if up_total > 0 else 0,
            'down_acc': down_correct / down_total if down_total > 0 else 0,
            'overall': (up_correct + down_correct) / total if total > 0 else 0,
            'samples': total,
            # F3: 幅度统计（%）。expectancy = overall×对时均幅 + (1-overall)×错时均幅，
            # 即全样本方向幅度的均值——正且量够大，信号才有交易价值
            'avg_correct_move': float(np.mean(correct_moves)) if correct_moves else 0,
            'avg_wrong_move': float(np.mean(wrong_moves)) if wrong_moves else 0,
            'expectancy': float(np.mean(all_moves)) if all_moves else 0,
        }

    return result