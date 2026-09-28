# src/dash_app/utils/comparison/engine.py
"""
多策略对比引擎

接受 List[StrategyConfig]，对每个策略执行 run_backtest，
返回结构化结果（含错误信息、耗时、配置快照）。

设计原则：
- 不吞异常：错误以结构化形式返回，前端可展示
- 不硬编码策略：strategy_type 从 StrategyConfig 透传到 params['strategy_id']
- 预留 cache 钩子：将来接数据缓存层
"""

import time
import traceback
from typing import Dict, List, Any, Union, Optional

from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.utils.research.strategy_config import StrategyConfig


class ComparisonEngine:
    """多策略对比引擎"""

    @staticmethod
    def run_comparison(
        base_params: Dict[str, Any],
        strategy_configs: List[Union[StrategyConfig, Dict[str, Any]]],
        series: str = '7d',
        cache: Optional[Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        运行多策略对比

        Args:
            base_params: 基础参数（事件、市场、价格类型、窗口等）
            strategy_configs: StrategyConfig 列表，或可被 from_dict 解析的 dict 列表
            series: '7d' | '48h'，透传（当前 run_backtest 未使用，保留）
            cache: 预留，将来传缓存对象；当前忽略

        Returns:
            {
                strategy_name: {
                    'name': str,
                    'config': dict,          # StrategyConfig 快照
                    'params': dict,          # 合并后的完整参数（含 strategy_id）
                    'status': 'ok' | 'error',
                    'error': str | None,
                    'metrics': dict,
                    'trades': list,
                    'equity_curve': list,
                    'final_capital': float | None,
                    'elapsed_sec': float,
                },
                ...
            }

        注意：若某策略校验失败或回测抛异常，该策略的 status='error'，
        其余策略照常运行，不会整体失败。
        """
        if not strategy_configs:
            return {}

        # 归一化：dict → StrategyConfig
        configs: List[StrategyConfig] = []
        for c in strategy_configs:
            if isinstance(c, StrategyConfig):
                configs.append(c)
            elif isinstance(c, dict):
                configs.append(StrategyConfig.from_dict(c))
            else:
                # 未知类型，跳过并记一条错误
                configs.append(StrategyConfig(
                    name=str(c),
                    params={},
                ))

        results: Dict[str, Dict[str, Any]] = {}
        for cfg in configs:
            results[cfg.name] = ComparisonEngine._run_single(
                cfg, base_params, series
            )
        return results

    @staticmethod
    def _run_single(
        cfg: StrategyConfig,
        base_params: Dict[str, Any],
        series: str,
    ) -> Dict[str, Any]:
        """执行单个策略回测，保证不抛异常"""
        t0 = time.time()

        # 1. 校验
        errors = cfg.validate()
        if errors:
            return {
                'name': cfg.name,
                'config': cfg.to_dict(),
                'params': None,
                'status': 'error',
                'error': '；'.join(errors),
                'metrics': {},
                'trades': [],
                'equity_curve': [],
                'final_capital': None,
                'elapsed_sec': time.time() - t0,
            }

        # 2. 合并参数
        merged = cfg.merged_with(base_params)

        # 3. 执行回测
        try:
            result = run_backtest(merged, series)
        except Exception as e:
            return {
                'name': cfg.name,
                'config': cfg.to_dict(),
                'params': merged,
                'status': 'error',
                'error': f'{type(e).__name__}: {e}',
                'metrics': {},
                'trades': [],
                'equity_curve': [],
                'final_capital': None,
                'elapsed_sec': time.time() - t0,
                'traceback': traceback.format_exc(),
            }

        if not result:
            return {
                'name': cfg.name,
                'config': cfg.to_dict(),
                'params': merged,
                'status': 'error',
                'error': '回测返回空结果（数据不足或参数无效）',
                'metrics': {},
                'trades': [],
                'equity_curve': [],
                'final_capital': None,
                'elapsed_sec': time.time() - t0,
            }

        # 4. 正常返回
        return {
            'name': cfg.name,
            'config': cfg.to_dict(),
            'params': merged,
            'status': 'ok',
            'error': None,
            'metrics': result.get('metrics', {}),
            'trades': result.get('trades', []),
            'equity_curve': result.get('equity_curve', []),
            'final_capital': result.get('final_capital'),
            'elapsed_sec': time.time() - t0,
        }