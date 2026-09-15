"""
信号生成器 - 方向信号策略核心逻辑
基于推文热度的"估算总量距中位数距离变化"趋势判断系统
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional


class DirectionSignalGenerator:
    """
    方向信号生成器
    核心逻辑：通过推文热度估算市场参与度，通过距离中位数的变化推断方向
    """

    def __init__(self, params: Dict):
        """
        初始化信号生成器

        params:
            capacity: 容差 (Tolerance) - 距离 ≤ 容差时判定为看平
            price_threshold: 价格阈值 - 价格变动 ≤ 此值时视为噪音
            distance_threshold: 距离阈值 - 距离变动 ≤ 此值时视为噪音
            inertia_hours: 惯性（最大持有小时数）
            momentum_enable: 是否启用动量修正
            momentum_coef: 动量系数
            signal_mode: 信号模式 (full / start / end)
            median: 中位数锚点
            remaining_hours: 事件剩余总小时数
        """
        self.capacity = params.get('capacity', 0)
        self.price_threshold = params.get('price_threshold', 0.005)
        self.distance_threshold = params.get('distance_threshold', 1.5)
        self.inertia_hours = params.get('inertia_hours', 6)
        self.momentum_enable = params.get('momentum_enable', True)
        self.momentum_coef = params.get('momentum_coef', 0.10)
        self.signal_mode = params.get('signal_mode', 'full')
        self.median = params.get('median', 0.5)
        self.remaining_hours = params.get('remaining_hours', 0)

        # 新增：窗口模式
        self.window_mode = params.get('window_mode', 'rolling')
        self.window_param = params.get('window_param', 168)
        self.window_start = params.get('window_start', None)
        self.window_start_ts = params.get('window_start_ts', None)  # ← expanding 起点时间戳（秒）

        # 状态变量
        self.prev_distance = None
        self.current_signal = '→'
        self.hold_hours = 0
        self.prev_total_estimate = None
        self.prev_price = None  # ← 修复：显式初始化

    def generate_signals(self, price_data: pd.DataFrame, tweet_data: pd.DataFrame) -> pd.DataFrame:
        """
        生成完整信号序列

        Args:
            price_data: DataFrame with columns [timestamp, price]
            tweet_data: DataFrame with columns [timestamp, tweet_count]

        Returns:
            DataFrame with columns [timestamp, price, tweet_count, signal, ...]
        """
        df = pd.merge(price_data, tweet_data, on='timestamp', how='left')
        df['tweet_count'] = df['tweet_count'].fillna(0)
        df = df.sort_values('timestamp').reset_index(drop=True)

        # ---- 计算 avg_rate ----
        if self.window_mode == 'rolling':
            n = int(self.window_param) if self.window_param else 168
            df['avg_rate'] = df['tweet_count'].rolling(window=n, min_periods=1).mean()

        elif self.window_mode == 'expanding':
            if self.window_start_ts is not None:
                # 从指定时间戳开始 expanding
                mask = df['timestamp'] >= pd.to_datetime(self.window_start_ts, unit='s')
                df['avg_rate'] = np.nan
                if mask.any():
                    sub = df.loc[mask, 'tweet_count']
                    df.loc[mask, 'avg_rate'] = sub.expanding(min_periods=1).mean().values
                    # 起点之前用 rolling(1) 兜底（或用第一个值填充）
                    if (~mask).any():
                        df.loc[~mask, 'avg_rate'] = df.loc[~mask, 'tweet_count']
                    # 前向填充：起点前的 NaN 用起点后的第一个值填
                    df['avg_rate'] = df['avg_rate'].bfill()
            else:
                # 没有起点，从第一行开始 expanding
                df['avg_rate'] = df['tweet_count'].expanding(min_periods=1).mean()
        else:
            # 兜底
            df['avg_rate'] = df['tweet_count'].rolling(window=168, min_periods=1).mean()

        # ---- 估算总量 ----
        df['total_estimate'] = df['avg_rate'] * self.remaining_hours

        # ---- 逐行遍历 ----
        signals = []
        distances = []
        estimates = []
        hold_hours_list = []

        for idx, row in df.iterrows():
            total_estimate = row['total_estimate']

            # 动量修正
            if self.momentum_enable and self.prev_total_estimate is not None:
                rate_change = self._calculate_momentum(df, idx)
                adjustment = 1 + self.momentum_coef * rate_change
                adjustment = np.clip(adjustment, 0.8, 1.2)
                total_estimate = total_estimate * adjustment

            distance = abs(total_estimate - self.median)
            signal, hold_hours = self._determine_signal(distance, row['price'], idx)

            signals.append(signal)
            distances.append(distance)
            estimates.append(total_estimate)
            hold_hours_list.append(hold_hours)

            self.prev_distance = distance
            self.prev_total_estimate = total_estimate

        df['signal'] = signals
        df['distance'] = distances
        df['total_estimate'] = estimates
        df['hold_hours'] = hold_hours_list

        return df

    def _calculate_momentum(self, df: pd.DataFrame, idx: int) -> float:
        """计算动量修正系数"""
        if idx < 6:  # 前6小时无足够数据
            return 0.0
        recent_avg = df['avg_rate'].iloc[idx-6:idx].mean()
        if recent_avg == 0:
            return 0.0
        return (df['avg_rate'].iloc[idx] - recent_avg) / recent_avg

    def _determine_signal(self, distance: float, price: float, idx: int) -> Tuple[str, int]:
        # 容差过滤
        if distance <= self.capacity:
            self.prev_price = price  # ← 也要更新
            return '→', 0

        # 首次判断
        if self.prev_distance is None:
            self.prev_distance = distance
            self.prev_price = price  # ← 更新
            return '→', 0

        # 噪声过滤
        price_change = abs(price - self.prev_price) if self.prev_price is not None else 0
        distance_change = distance - self.prev_distance

        if price_change <= self.price_threshold and abs(distance_change) <= self.distance_threshold:
            self.hold_hours += 1
            self.prev_price = price  # ← 修复：噪音分支也要更新 prev_price
            if self.hold_hours >= self.inertia_hours:
                self.hold_hours = 0
                return '→', self.hold_hours
            return self.current_signal, self.hold_hours

        # 有效信号
        self.hold_hours = 0
        if distance < self.prev_distance:
            signal = '↑'
        elif distance > self.prev_distance:
            signal = '↓'
        else:
            signal = '→'

        self.current_signal = signal
        self.prev_price = price
        return signal, self.hold_hours

    def apply_display_filter(self, df: pd.DataFrame, mode: str = None) -> pd.DataFrame:
        """仅用于显示时过滤信号（不影响回测）"""
        df_signal = df.copy()
        if mode is None:
            mode = self.signal_mode

        if mode == 'full':
            df_signal['prev_signal'] = df_signal['signal'].shift(1)
            df_signal['next_signal'] = df_signal['signal'].shift(-1)
            df_signal['is_start'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['prev_signal'])
            df_signal['is_end'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['next_signal'])
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_start'] | df_signal['is_end'], '')
            return df_signal.drop(columns=['prev_signal', 'next_signal', 'is_start', 'is_end'])

        elif mode == 'start':
            df_signal['prev_signal'] = df_signal['signal'].shift(1)
            df_signal['is_start'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['prev_signal'])
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_start'], '')
            return df_signal.drop(columns=['prev_signal', 'is_start'])

        elif mode == 'end':
            df_signal['next_signal'] = df_signal['signal'].shift(-1)
            df_signal['is_end'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['next_signal'])
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_end'], '')
            return df_signal.drop(columns=['next_signal', 'is_end'])

        return df_signal

    def get_signal_stats(self, df: pd.DataFrame) -> Dict:
        """计算信号统计指标"""
        signals = df['signal']
        total_signals = len(signals[signals != ''])
        up_count = len(signals[signals == '↑'])
        down_count = len(signals[signals == '↓'])
        flat_count = len(signals[signals == '→'])

        # 方向准确率（预测方向与下一小时价格变化的一致性）
        price_change = df['price'].diff().shift(-1)
        direction_accuracy = self._calculate_accuracy(df, price_change)

        return {
            'total_signals': total_signals,
            'up_count': up_count,
            'down_count': down_count,
            'flat_count': flat_count,
            'up_accuracy': direction_accuracy['up_accuracy'],
            'down_accuracy': direction_accuracy['down_accuracy'],
            'overall_accuracy': direction_accuracy['overall'],
        }

    def _calculate_accuracy(self, df: pd.DataFrame, price_change: pd.Series) -> Dict:
        """计算方向准确率"""
        up_correct = 0
        up_total = 0
        down_correct = 0
        down_total = 0

        for idx, row in df.iterrows():
            if row['signal'] == '↑':
                up_total += 1
                if price_change.iloc[idx] > 0:
                    up_correct += 1
            elif row['signal'] == '↓':
                down_total += 1
                if price_change.iloc[idx] < 0:
                    down_correct += 1

        return {
            'up_accuracy': up_correct / up_total if up_total > 0 else 0,
            'down_accuracy': down_correct / down_total if down_total > 0 else 0,
            'overall': (up_correct + down_correct) / (up_total + down_total) if (up_total + down_total) > 0 else 0,
        }