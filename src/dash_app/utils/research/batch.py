# src/dash_app/utils/research/batch.py
"""
多事件批量研究引擎

对每一对 (event_id, market_id) 用同一套策略跑一遍回测，
然后跨事件聚合出统计指标（均值 / 中位数 / 标准差 / 胜事件率等）。

用于回答："这套策略在 20 个事件上表现稳定吗？"
"""

import statistics
from typing import Dict, List, Any, Union, Tuple

from src.dash_app.utils.comparison.engine import ComparisonEngine
from src.dash_app.utils.research.strategy_config import StrategyConfig


class BatchEngine:
    """多事件批量研究引擎"""

    @staticmethod
    def run_batch(
        base_params: Dict[str, Any],
        strategy_configs: List[Union[StrategyConfig, Dict[str, Any]]],
        event_market_pairs: List[Tuple[Any, Any]],
        series: str = '7d',
    ) -> Dict[str, Any]:
        """
        在多个事件上跑同一套策略

        Args:
            base_params: 基础参数（会被每个事件的 event_id/market_id 覆盖）
            strategy_configs: 要复用的策略列表
            event_market_pairs: [(event_id, market_id), ...]
            series: '7d' | '48h'

        Returns:
            {
                'n_pairs': int,
                'per_event': {
                    event_id: {
                        'event_id': ..., 'market_id': ...,
                        'strategies': {
                            name: {
                                'status': 'ok'|'error',
                                'error': str|None,
                                'metrics': {...},
                                'elapsed_sec': float,
                            },
                        },
                    },
                },
                'aggregate': {
                    name: {
                        'n_events': int, 'n_ok': int,
                        'mean_return': float, 'median_return': float,
                        'std_return': float, 'min_return': float,
                        'max_return': float,
                        'win_events': int, 'win_event_rate': float,
                        'mean_sharpe': float, 'mean_win_rate': float,
                        'mean_max_drawdown': float,
                    },
                },
            }
        """
        # 归一化策略
        configs: List[StrategyConfig] = []
        for c in strategy_configs:
            if isinstance(c, StrategyConfig):
                configs.append(c)
            elif isinstance(c, dict):
                configs.append(StrategyConfig.from_dict(c))

        per_event: Dict[Any, Dict[str, Any]] = {}

        for pair in event_market_pairs:
            if not pair or len(pair) < 2:
                continue
            event_id, market_id = pair[0], pair[1]
            if not event_id or not market_id:
                continue

            event_params = dict(base_params)
            event_params['event_id'] = event_id
            event_params['market_id'] = market_id

            strategies_result: Dict[str, Any] = {}
            for cfg in configs:
                r = ComparisonEngine._run_single(cfg, event_params, series)
                strategies_result[cfg.name] = {
                    'status': r.get('status'),
                    'error': r.get('error'),
                    'metrics': r.get('metrics', {}),
                    'elapsed_sec': r.get('elapsed_sec', 0),
                }

            per_event[event_id] = {
                'event_id': event_id,
                'market_id': market_id,
                'strategies': strategies_result,
            }

        aggregate = BatchEngine._aggregate(per_event, configs)

        return {
            'n_pairs': len(per_event),
            'per_event': per_event,
            'aggregate': aggregate,
        }

    @staticmethod
    def _aggregate(per_event: Dict[Any, Dict[str, Any]],
                   configs: List[StrategyConfig]) -> Dict[str, Any]:
        """跨事件聚合出每个策略的统计指标"""
        aggregate: Dict[str, Any] = {}

        for cfg in configs:
            name = cfg.name
            returns: List[float] = []
            sharpes: List[float] = []
            win_rates: List[float] = []
            max_dds: List[float] = []
            n_ok = 0

            for event_data in per_event.values():
                s = event_data['strategies'].get(name, {})
                if s.get('status') != 'ok':
                    continue
                n_ok += 1
                m = s.get('metrics', {})

                def _pick(key):
                    v = m.get(key)
                    if v is None:
                        return None
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None

                r = _pick('total_return')
                if r is not None:
                    returns.append(r)
                sh = _pick('sharpe_ratio')
                if sh is not None:
                    sharpes.append(sh)
                wr = _pick('win_rate')
                if wr is not None:
                    win_rates.append(wr)
                dd = _pick('max_drawdown_pct')
                if dd is not None:
                    max_dds.append(dd)

            n_total = len(per_event)

            if not returns:
                aggregate[name] = {
                    'n_events': n_total, 'n_ok': n_ok,
                    'error': '无有效事件',
                }
                continue

            wins = sum(1 for r in returns if r > 0)

            aggregate[name] = {
                'n_events': n_total,
                'n_ok': n_ok,
                'mean_return': statistics.mean(returns),
                'median_return': statistics.median(returns),
                'std_return': (statistics.stdev(returns)
                               if len(returns) > 1 else 0.0),
                'min_return': min(returns),
                'max_return': max(returns),
                'win_events': wins,
                'win_event_rate': wins / n_ok * 100 if n_ok else 0,
                'mean_sharpe': (statistics.mean(sharpes)
                                if sharpes else 0.0),
                'mean_win_rate': (statistics.mean(win_rates)
                                  if win_rates else 0.0),
                'mean_max_drawdown': (statistics.mean(max_dds)
                                      if max_dds else 0.0),
            }

        return aggregate