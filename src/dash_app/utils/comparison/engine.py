# src/dash_app/utils/comparison/engine.py
"""
多策略对比引擎
"""

import pandas as pd
from typing import Dict, List, Any
from src.dash_app.utils.backtest.runner import run_backtest


class ComparisonEngine:
    """多策略对比引擎"""

    @staticmethod
    def run_comparison(base_params: Dict[str, Any], strategy_configs: List[Dict[str, Any]], series: str = '7d') -> Dict[str, Any]:
        """
        运行多策略对比

        Args:
            base_params: 基础参数（事件、市场、价格类型等）
            strategy_configs: 策略配置列表
                [
                    {'name': '策略A', 'strategy_id': 'direction_signal', 'params': {'capacity': 0.5}},
                    {'name': '策略B', 'strategy_id': 'direction_signal', 'params': {'capacity': 1.0}},
                ]

        Returns:
            dict: 包含所有策略的回测结果
        """
        results = {}

        for config in strategy_configs:
            # 合并参数
            params = base_params.copy()
            params.update(config.get('params', {}))
            params['strategy_id'] = config.get('strategy_id', 'direction_signal')

            # 执行回测
            result = ComparisonEngine._run_single_backtest(params, series)
            results[config['name']] = {
                'name': config['name'],
                'params': params,
                'result': result,
                'metrics': result.get('metrics', {}) if result else {},
                'trades': result.get('trades', []) if result else [],
                'equity_curve': result.get('equity_curve', []) if result else [],
            }

        return results

    @staticmethod
    def _run_single_backtest(params: Dict[str, Any], series: str = '7d') -> Dict[str, Any]:
        """执行单个回测"""
        try:
            return run_backtest(params, series)
        except Exception as e:
            print(f"回测失败: {e}")
            return None