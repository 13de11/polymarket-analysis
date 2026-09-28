# src/dash_app/utils/research/strategy_config.py
"""
策略配置数据结构 + 策略类型注册表

未来新增策略，只在 STRATEGY_REGISTRY 里加一条。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, METRIC_SCHEMA,
)

# ============ 策略类型注册表 ============
STRATEGY_REGISTRY = {
    'direction_signal': {
        'label': '方向信号策略',
        'description': '基于推文速率估算与市场价格距离的方向判断（当前主力策略）',
        # 该策略允许被覆盖的参数
        'param_keys': [
            'capacity', 'price_threshold', 'distance_threshold',
            'inertia', 'momentum_enable', 'momentum_coef',
        ],
    },
    # 下面这些是未来要实现的基线策略，先占位，用于前端下拉展示时能区分
    # 实现时需要在 backtest/runner.py 里按 strategy_id 分发
    # 'buy_hold': {
    #     'label': '买入持有',
    #     'description': '开盘即全仓买入，结束平仓',
    #     'param_keys': [],
    # },
    # 'reverse_signal': {
    #     'label': '反向信号策略',
    #     'description': '方向信号取反，用于验证信号是否真有 alpha',
    #     'param_keys': [
    #         'capacity', 'price_threshold', 'distance_threshold',
    #         'inertia', 'momentum_enable', 'momentum_coef',
    #     ],
    # },
}

# ============ 策略配置数据结构 ============
@dataclass
class StrategyConfig:
    """一次回测的完整策略配置"""
    name: str                              # 显示名，如 "策略A (阈值0.005)"
    strategy_type: str = 'direction_signal'
    params: Dict[str, Any] = field(default_factory=dict)   # 覆盖 base_params 的字段
    color: Optional[str] = None            # 图表颜色，前端可指定

    def merged_with(self, base_params: Dict[str, Any]) -> Dict[str, Any]:
        """把自身 params 合并到 base_params 上，生成 run_backtest 用的完整参数"""
        merged = dict(base_params)
        merged.update(self.params)
        merged['strategy_id'] = self.strategy_type
        return merged

    def validate(self) -> List[str]:
        """返回错误列表，空列表表示通过"""
        errors = []
        if self.strategy_type not in STRATEGY_REGISTRY:
            errors.append(f"未知策略类型: {self.strategy_type}")
            return errors

        allowed = set(STRATEGY_REGISTRY[self.strategy_type]['param_keys'])
        for k, v in self.params.items():
            if k not in allowed:
                errors.append(f"策略 {self.name} 不支持参数: {k}")
                continue
            if k not in PARAM_SCHEMA:
                errors.append(f"参数未注册: {k}")
                continue
            schema = PARAM_SCHEMA[k]
            if schema['type'] in ('float', 'int'):
                if not isinstance(v, (int, float)):
                    errors.append(f"{k} 应为数值，实际 {type(v).__name__}")
                elif not (schema['min'] <= v <= schema['max']):
                    errors.append(
                        f"{k}={v} 超出范围 [{schema['min']}, {schema['max']}]"
                    )
            elif schema['type'] == 'enum':
                if v not in schema['options']:
                    errors.append(f"{k}={v} 不在 {schema['options']} 中")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'strategy_type': self.strategy_type,
            'params': self.params,
            'color': self.color,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'StrategyConfig':
        return cls(
            name=d.get('name', '未命名'),
            strategy_type=d.get('strategy_type', 'direction_signal'),
            params=d.get('params', {}),
            color=d.get('color'),
        )


# ============ 辅助函数 ============
def get_strategy_options() -> List[Dict[str, str]]:
    """前端策略类型下拉用"""
    return [{'label': v['label'], 'value': k}
            for k, v in STRATEGY_REGISTRY.items()]

def get_strategy_param_keys(strategy_type: str) -> List[str]:
    return STRATEGY_REGISTRY.get(strategy_type, {}).get('param_keys', [])

def make_default_config(name: str, strategy_type: str = 'direction_signal',
                        color: Optional[str] = None) -> StrategyConfig:
    """根据参数默认值生成一份默认策略配置"""
    params = {}
    for k in get_strategy_param_keys(strategy_type):
        params[k] = PARAM_SCHEMA[k]['default']
    return StrategyConfig(name=name, strategy_type=strategy_type,
                          params=params, color=color)

def get_all_override_param_keys() -> List[str]:
    """
    返回所有策略可覆盖参数的并集，按 PARAM_SCHEMA 的顺序。

    用于前端策略卡片渲染：卡片渲染全部参数行，
    再按当前策略类型动态显隐。
    """
    from src.dash_app.utils.research.params_schema import PARAM_SCHEMA
    keys = set()
    for info in STRATEGY_REGISTRY.values():
        keys.update(info.get('param_keys', []))
    return [k for k in PARAM_SCHEMA.keys() if k in keys]