# src/dash_app/utils/strategy/registry.py
"""
策略注册表 - 定义所有可用策略及其参数
"""

from typing import Dict, Any, List
from src.dash_app.utils.signal.generator import DirectionSignalGenerator


class StrategyRegistry:
    """策略注册表"""

    @staticmethod
    def get_strategy_list() -> List[Dict[str, Any]]:
        """获取所有可用策略列表"""
        return [
            {
                'id': 'direction_signal',
                'name': '方向信号策略',
                'description': '基于推文热度的方向预测',
                'default_params': {
                    'capacity': 0.5,
                    'price_threshold': 0.005,
                    'distance_threshold': 1.5,
                    'inertia': 6,
                    'momentum_enable': True,
                    'momentum_coef': 0.10,
                },
                'param_ranges': {
                    'capacity': {'min': 0, 'max': 5, 'step': 0.5},
                    'price_threshold': {'min': 0.001, 'max': 0.02, 'step': 0.001},
                    'distance_threshold': {'min': 0.5, 'max': 4.0, 'step': 0.1},
                    'inertia': {'min': 1, 'max': 12, 'step': 1},
                    'momentum_coef': {'min': 0.01, 'max': 0.30, 'step': 0.01},
                }
            },
            # 后续可扩展更多策略
        ]

    @staticmethod
    def get_strategy_by_id(strategy_id: str) -> Dict[str, Any]:
        """根据ID获取策略配置"""
        for s in StrategyRegistry.get_strategy_list():
            if s['id'] == strategy_id:
                return s
        return None