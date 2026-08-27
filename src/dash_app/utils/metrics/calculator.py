"""
绩效指标计算器
从交易记录和权益曲线计算各类绩效指标
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional


def calculate_metrics_from_trades(trades: List[Dict], equity_curve: List[Dict], initial_capital: float) -> Dict:
    """
    从交易记录和权益曲线计算绩效指标

    Args:
        trades: 交易记录列表
        equity_curve: 权益曲线列表
        initial_capital: 初始资金

    Returns:
        dict: 绩效指标字典
    """
    # 筛选已完成的交易
    completed_trades = [t for t in trades if t['result'] != 'pending']

    metrics = {
        'total_trades': len(completed_trades),
        'win_count': 0,
        'loss_count': 0,
        'win_rate': 0,
        'profit_factor': 0,
        'avg_win': 0,
        'avg_loss': 0,
        'max_profit': 0,
        'max_loss': 0,
        'total_profit': 0,
        'avg_hold_hours': 0,
        'max_hold_hours': 0,
        'max_drawdown': 0,
        'max_drawdown_pct': 0,
        'sharpe_ratio': 0,
        'final_capital': initial_capital,
        'total_return': 0,
    }

    if not completed_trades:
        return metrics

    # 盈亏统计
    profits = [t['profit'] for t in completed_trades if t['profit'] is not None]
    win_trades = [t for t in completed_trades if t['profit'] is not None and t['profit'] > 0]
    loss_trades = [t for t in completed_trades if t['profit'] is not None and t['profit'] < 0]

    metrics['win_count'] = len(win_trades)
    metrics['loss_count'] = len(loss_trades)
    metrics['total_profit'] = sum(profits) if profits else 0

    # 胜率
    metrics['win_rate'] = len(win_trades) / len(completed_trades) * 100 if completed_trades else 0

    # 平均盈利/亏损
    metrics['avg_win'] = sum([t['profit'] for t in win_trades]) / len(win_trades) if win_trades else 0
    metrics['avg_loss'] = abs(sum([t['profit'] for t in loss_trades]) / len(loss_trades)) if loss_trades else 0

    # 盈亏比
    metrics['profit_factor'] = abs(sum([t['profit'] for t in win_trades]) / sum([t['profit'] for t in loss_trades])) if loss_trades and sum([t['profit'] for t in loss_trades]) != 0 else 0

    # 最大盈利/亏损
    metrics['max_profit'] = max([t['profit'] for t in win_trades]) if win_trades else 0
    metrics['max_loss'] = abs(min([t['profit'] for t in loss_trades])) if loss_trades else 0

    # 持仓时间
    hold_hours = [t['hold_hours'] for t in completed_trades if t['hold_hours'] is not None]
    metrics['avg_hold_hours'] = sum(hold_hours) / len(hold_hours) if hold_hours else 0
    metrics['max_hold_hours'] = max(hold_hours) if hold_hours else 0

    # 最大回撤
    max_drawdown, max_drawdown_pct = calculate_max_drawdown(equity_curve)
    metrics['max_drawdown'] = max_drawdown
    metrics['max_drawdown_pct'] = max_drawdown_pct

    # 最终权益和总收益率
    if equity_curve:
        metrics['final_capital'] = equity_curve[-1]['equity']
        metrics['total_return'] = (metrics['final_capital'] / initial_capital - 1) * 100

    # 夏普比率
    metrics['sharpe_ratio'] = calculate_sharpe_ratio(equity_curve)

    return metrics


def calculate_max_drawdown(equity_curve: List[Dict]) -> tuple:
    """计算最大回撤"""
    if not equity_curve:
        return 0, 0

    equity_values = [e['equity'] for e in equity_curve]
    max_equity = equity_values[0]
    max_drawdown = 0
    max_drawdown_pct = 0

    for equity in equity_values:
        if equity > max_equity:
            max_equity = equity
        drawdown = max_equity - equity
        drawdown_pct = (drawdown / max_equity) * 100 if max_equity > 0 else 0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
            max_drawdown_pct = drawdown_pct

    return max_drawdown, max_drawdown_pct


def calculate_sharpe_ratio(equity_curve: List[Dict]) -> float:
    """计算夏普比率（无风险利率为0）"""
    if len(equity_curve) < 2:
        return 0

    equity_values = [e['equity'] for e in equity_curve]
    returns = [(equity_values[i] / equity_values[i-1] - 1) for i in range(1, len(equity_values))]

    if not returns:
        return 0

    avg_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0

    annual_factor = np.sqrt(252 * 24)
    return (avg_return / std_return) * annual_factor


def format_metrics_for_display(metrics: Dict) -> Dict:
    """
    格式化指标以便在Dash卡片中显示

    Returns:
        dict: 包含格式化的字符串
    """
    return {
        '总交易次数': str(metrics.get('total_trades', 0)),
        '胜率': f"{metrics.get('win_rate', 0):.1f}%",
        '盈亏比': f"{metrics.get('profit_factor', 0):.2f}",
        '总盈亏': f"${metrics.get('total_profit', 0):.2f}",
        '平均盈利': f"${metrics.get('avg_win', 0):.2f}",
        '平均亏损': f"${metrics.get('avg_loss', 0):.2f}",
        '最大盈利': f"${metrics.get('max_profit', 0):.2f}",
        '最大亏损': f"${metrics.get('max_loss', 0):.2f}",
        '平均持仓': f"{metrics.get('avg_hold_hours', 0):.1f}h",
        '最大回撤': f"{metrics.get('max_drawdown_pct', 0):.2f}%",
        '夏普比率': f"{metrics.get('sharpe_ratio', 0):.2f}",
        '最终权益': f"${metrics.get('final_capital', 0):.2f}",
        '总收益率': f"{metrics.get('total_return', 0):.2f}%",
    }