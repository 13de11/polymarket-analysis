"""
回测引擎 - 模拟交易执行
基于方向信号执行开仓/平仓，计算权益曲线和交易记录
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class BacktestEngine:
    """
    回测引擎
    输入信号和价格数据，输出交易记录和权益曲线
    """

    def __init__(
        self,
        initial_capital: float = 100,
        position_mode: str = 'fixed_amount',
        position_size: float = 10,
    ):
        """
        初始化回测引擎

        Args:
            initial_capital: 初始资金
            position_mode: 'fixed_amount' 固定金额 / 'fixed_shares' 固定份额
            position_size: 每次投入金额或份额
        """
        self.initial_capital = initial_capital
        self.position_mode = position_mode
        self.position_size = position_size

        # 状态变量
        self.cash = initial_capital
        self.position = 0  # 当前持仓数量（股/份）
        self.position_cost = 0  # 持仓成本（平均成本）
        self.trades = []  # 交易记录
        self.equity_curve = []  # 权益曲线
        self.is_holding = False
        self.entry_price = 0
        self.entry_time = None
        self.cumulative_trades = 0

    def run(self, signal_df: pd.DataFrame, price_col: str = 'price') -> Dict:
        """
        执行回测

        Args:
            signal_df: 信号DataFrame，必须包含 'timestamp', 'signal', 'price' 列
            price_col: 价格列名，默认 'price'

        Returns:
            dict: 包含 'trades', 'equity_curve', 'final_capital', 'metrics'
        """
        if signal_df.empty:
            return {
                'trades': [],
                'equity_curve': [],
                'final_capital': self.initial_capital,
                'metrics': {}
            }

        # 重置状态
        self._reset()

        # 按时间顺序遍历
        for idx, row in signal_df.iterrows():
            timestamp = row['timestamp']
            price = row[price_col]
            signal = row['signal']

            if pd.isna(price) or price <= 0:
                continue

            # 记录当前权益（用于曲线）
            current_equity = self._calculate_equity(price)
            self.equity_curve.append({
                'timestamp': timestamp,
                'equity': current_equity,
                'cash': self.cash,
                'position': self.position,
                'position_value': self.position * price if self.position > 0 else 0,
                'price': price,
            })

            # 处理信号
            self._process_signal(timestamp, price, signal)

        # 强制平仓（如果还有持仓）
        if self.is_holding and len(signal_df) > 0:
            last_row = signal_df.iloc[-1]
            self._close_position(last_row['timestamp'], last_row[price_col], reason='强制平仓')

        # 计算最终指标
        final_capital = self._calculate_equity(signal_df.iloc[-1][price_col]) if not signal_df.empty else self.cash
        metrics = self._calculate_metrics(signal_df)

        return {
            'trades': self.trades,
            'equity_curve': self.equity_curve,
            'final_capital': final_capital,
            'metrics': metrics,
        }

    def _reset(self):
        """重置回测状态"""
        self.cash = self.initial_capital
        self.position = 0
        self.position_cost = 0
        self.trades = []
        self.equity_curve = []
        self.is_holding = False
        self.entry_price = 0
        self.entry_time = None
        self.cumulative_trades = 0

    def _calculate_equity(self, current_price: float) -> float:
        """计算当前权益"""
        position_value = self.position * current_price if self.position > 0 else 0
        return self.cash + position_value

    def _process_signal(self, timestamp, price: float, signal: str):
        """处理信号"""
        if signal == '↑' and not self.is_holding:
            # 开仓（做多）
            self._open_position(timestamp, price)
        elif signal == '↓' and self.is_holding:
            # 平仓
            self._close_position(timestamp, price, reason='信号平仓')
        # '→' 信号不处理，维持当前状态

    def _open_position(self, timestamp, price: float):
        """开仓"""
        if price <= 0:
            return

        # 计算买入数量
        if self.position_mode == 'fixed_amount':
            # 固定金额：用投入金额除以价格
            amount = min(self.position_size, self.cash)
            shares = amount / price
        else:  # fixed_shares
            shares = self.position_size
            amount = shares * price

        # 检查是否足够现金
        if amount > self.cash:
            shares = self.cash / price
            amount = self.cash

        if shares <= 0:
            return

        # 执行买入
        self.cash -= amount
        self.position += shares
        self.position_cost = price  # 简化：使用当前价格作为成本
        self.is_holding = True
        self.entry_price = price
        self.entry_time = timestamp
        self.cumulative_trades += 1

        # 记录交易（开仓部分）
        self.trades.append({
            'trade_id': self.cumulative_trades,
            'entry_time': timestamp,
            'entry_price': price,
            'shares': shares,
            'amount': amount,
            'exit_time': None,
            'exit_price': None,
            'profit': None,
            'profit_pct': None,
            'hold_hours': None,
            'result': 'pending',
        })

    def _close_position(self, timestamp, price: float, reason: str = '信号平仓'):
        """平仓"""
        if not self.is_holding or self.position <= 0:
            return

        # 找到当前未平仓的交易
        open_trade = None
        for trade in reversed(self.trades):
            if trade['result'] == 'pending':
                open_trade = trade
                break

        if open_trade is None:
            return

        # 计算盈亏
        profit = self.position * (price - self.entry_price)
        profit_pct = (price / self.entry_price - 1) * 100 if self.entry_price > 0 else 0

        # 更新交易记录
        open_trade['exit_time'] = timestamp
        open_trade['exit_price'] = price
        open_trade['profit'] = profit
        open_trade['profit_pct'] = profit_pct
        open_trade['hold_hours'] = (timestamp - self.entry_time).total_seconds() / 3600 if self.entry_time else 0
        open_trade['result'] = '盈利' if profit > 0 else '亏损' if profit < 0 else '平盘'
        open_trade['reason'] = reason

        # 执行卖出
        self.cash += self.position * price
        self.position = 0
        self.position_cost = 0
        self.is_holding = False
        self.entry_price = 0
        self.entry_time = None

    def _calculate_metrics(self, signal_df: pd.DataFrame) -> Dict:
        """计算绩效指标"""
        # 筛选已完成的交易
        completed_trades = [t for t in self.trades if t['result'] != 'pending']

        if not completed_trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'avg_profit': 0,
                'avg_loss': 0,
                'max_profit': 0,
                'max_loss': 0,
                'total_profit': 0,
                'avg_hold_hours': 0,
                'max_hold_hours': 0,
            }

        profits = [t['profit'] for t in completed_trades if t['profit'] is not None]
        win_trades = [t for t in completed_trades if t['profit'] is not None and t['profit'] > 0]
        loss_trades = [t for t in completed_trades if t['profit'] is not None and t['profit'] < 0]

        total_profit = sum(profits) if profits else 0
        win_rate = len(win_trades) / len(completed_trades) * 100 if completed_trades else 0

        avg_win = sum([t['profit'] for t in win_trades]) / len(win_trades) if win_trades else 0
        avg_loss = sum([t['profit'] for t in loss_trades]) / len(loss_trades) if loss_trades else 0

        profit_factor = abs(sum([t['profit'] for t in win_trades]) / sum([t['profit'] for t in loss_trades])) if loss_trades and sum([t['profit'] for t in loss_trades]) != 0 else 0

        max_profit = max([t['profit'] for t in win_trades]) if win_trades else 0
        max_loss = min([t['profit'] for t in loss_trades]) if loss_trades else 0

        hold_hours = [t['hold_hours'] for t in completed_trades if t['hold_hours'] is not None]

        # 计算最大回撤
        max_drawdown, max_drawdown_pct = self._calculate_max_drawdown()

        # 计算夏普比率
        sharpe_ratio = self._calculate_sharpe_ratio()

        return {
            'total_trades': len(completed_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_profit': avg_win,
            'avg_loss': abs(avg_loss) if avg_loss else 0,
            'max_profit': max_profit,
            'max_loss': abs(max_loss) if max_loss else 0,
            'total_profit': total_profit,
            'avg_hold_hours': sum(hold_hours) / len(hold_hours) if hold_hours else 0,
            'max_hold_hours': max(hold_hours) if hold_hours else 0,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'sharpe_ratio': sharpe_ratio,
            'final_capital': self._calculate_equity(signal_df.iloc[-1]['price']) if not signal_df.empty else self.cash,
            'total_return': (self._calculate_equity(signal_df.iloc[-1]['price']) / self.initial_capital - 1) * 100 if not signal_df.empty else 0,
        }

    def _calculate_max_drawdown(self) -> Tuple[float, float]:
        """计算最大回撤"""
        if not self.equity_curve:
            return 0, 0

        equity_values = [e['equity'] for e in self.equity_curve]
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

    def _calculate_sharpe_ratio(self) -> float:
        """计算夏普比率（简化版，假设无风险利率为0）"""
        if len(self.equity_curve) < 2:
            return 0

        equity_values = [e['equity'] for e in self.equity_curve]
        returns = [(equity_values[i] / equity_values[i-1] - 1) for i in range(1, len(equity_values))]

        if not returns:
            return 0

        avg_return = np.mean(returns)
        std_return = np.std(returns)

        if std_return == 0:
            return 0

        # 年化（假设小时级数据，252天*24小时）
        annual_factor = np.sqrt(252 * 24)
        return (avg_return / std_return) * annual_factor