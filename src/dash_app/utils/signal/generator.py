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

        # 状态变量
        self.prev_distance = None
        self.current_signal = '→'
        self.hold_hours = 0
        self.prev_total_estimate = None

    def generate_signals(self, price_data: pd.DataFrame, tweet_data: pd.DataFrame,
                         window_hours: int) -> pd.DataFrame:
        """
        生成完整信号序列

        Args:
            price_data: DataFrame with columns [timestamp, price]
            tweet_data: DataFrame with columns [timestamp, tweet_count]
            window_hours: 推文速率计算窗口（小时数）

        Returns:
            DataFrame with columns [timestamp, price, tweet_count, signal,
                                     distance, total_estimate, hold_hours]
        """
        # 合并价格和推文数据
        df = pd.merge(price_data, tweet_data, on='timestamp', how='left')
        df['tweet_count'] = df['tweet_count'].fillna(0)

        # 计算推文速率（滑动窗口）
        df['avg_rate'] = df['tweet_count'].rolling(window=window_hours, min_periods=1).mean()

        # 计算估算总量
        df['total_estimate'] = df['avg_rate'] * self.remaining_hours

        # 初始化信号列
        signals = []
        distances = []
        estimates = []
        hold_hours_list = []

        # 逐行遍历
        for idx, row in df.iterrows():
            total_estimate = row['total_estimate']

            # ---- 动量修正 ----
            if self.momentum_enable and self.prev_total_estimate is not None:
                rate_change = self._calculate_momentum(df, idx)
                adjustment = 1 + self.momentum_coef * rate_change
                adjustment = np.clip(adjustment, 0.8, 1.2)
                total_estimate = total_estimate * adjustment

            # ---- 计算距离 ----
            distance = abs(total_estimate - self.median)

            # ---- 方向判断 ----
            signal, hold_hours = self._determine_signal(distance, row['price'], idx)

            signals.append(signal)
            distances.append(distance)
            estimates.append(total_estimate)
            hold_hours_list.append(hold_hours)

            # 更新状态
            self.prev_distance = distance
            self.prev_total_estimate = total_estimate

        df['signal'] = signals
        df['distance'] = distances
        df['total_estimate'] = estimates
        df['hold_hours'] = hold_hours_list

        # ---- 信号后处理（首尾/只首/只尾） ----
        df = self._apply_signal_filter(df)

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
        """
        确定当前信号
        返回: (signal, hold_hours)
        """
        # 容差过滤
        if distance <= self.capacity:
            return '→', 0

        # 首次判断
        if self.prev_distance is None:
            self.prev_distance = distance
            return '→', 0

        # 噪声过滤：价格变动和距离变动都要满足才触发
        price_change = abs(price - self.prev_price) if hasattr(self, 'prev_price') else 0
        distance_change = distance - self.prev_distance

        if price_change <= self.price_threshold and abs(distance_change) <= self.distance_threshold:
            # 噪音：不触发新信号，累加惯性
            self.hold_hours += 1
            if self.hold_hours >= self.inertia_hours:
                self.hold_hours = 0
                return '→', self.hold_hours
            return self.current_signal, self.hold_hours

        # 有效信号：重置惯性
        self.hold_hours = 0

        # 方向判断
        if distance < self.prev_distance:
            signal = '↑'
        elif distance > self.prev_distance:
            signal = '↓'
        else:
            signal = '→'

        self.current_signal = signal
        self.prev_price = price

        return signal, self.hold_hours

    def _apply_signal_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        df_signal = df.copy()

        if self.signal_mode == 'full':
            # 首尾：连续同向信号只显示第一个和最后一个
            # 标记有效信号（非空）
            df_signal['signal_valid'] = df_signal['signal'] != ''
            # 获取前一个和后一个信号
            df_signal['prev_signal'] = df_signal['signal'].shift(1)
            df_signal['next_signal'] = df_signal['signal'].shift(-1)
            # 判断是否为段的起点（当前有效，且前一个不同或为空）
            df_signal['is_start'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['prev_signal'])
            # 判断是否为段的终点（当前有效，且后一个不同或为空）
            df_signal['is_end'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['next_signal'])
            # 只保留起点和终点
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_start'] | df_signal['is_end'], '')
            return df_signal.drop(columns=['prev_signal', 'next_signal', 'is_start', 'is_end', 'signal_valid'])

        elif self.signal_mode == 'start':
            # 只首：只显示每个连续段的第一个
            df_signal['prev_signal'] = df_signal['signal'].shift(1)
            df_signal['is_start'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['prev_signal'])
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_start'], '')
            return df_signal.drop(columns=['prev_signal', 'is_start'])

        elif self.signal_mode == 'end':
            # 只尾：只显示每个连续段的最后一个
            df_signal['next_signal'] = df_signal['signal'].shift(-1)
            df_signal['is_end'] = (df_signal['signal'] != '') & (df_signal['signal'] != df_signal['next_signal'])
            df_signal['signal'] = df_signal['signal'].where(df_signal['is_end'], '')
            return df_signal.drop(columns=['next_signal', 'is_end'])

        return df

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