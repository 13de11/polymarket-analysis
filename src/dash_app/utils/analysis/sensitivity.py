# src/dash_app/utils/analysis/sensitivity.py
"""
参数敏感性分析引擎
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Callable
from src.dash_app.pages.prediction_backtest import run_backtest


class SensitivityAnalysis:
    """参数敏感性分析"""

    @staticmethod
    def run_sensitivity_analysis(
        base_params: Dict[str, Any],
        param_name: str,
        param_values: List[float],
        metric_key: str = 'total_return'
    ) -> Dict[str, Any]:
        """
        运行参数敏感性分析

        Args:
            base_params: 基础参数
            param_name: 要分析的参数名称（如 'price_threshold'）
            param_values: 参数值列表
            metric_key: 要追踪的指标（'total_return', 'sharpe_ratio', 'win_rate'）

        Returns:
            dict: 包含参数值、指标值、详细结果
        """
        results = []
        total = len(param_values)

        for i, val in enumerate(param_values):
            print(f"  运行 {i+1}/{total}: {param_name} = {val}")

            params = base_params.copy()
            params[param_name] = val

            result = run_backtest(params)

            if result and result.get('metrics'):
                metrics = result['metrics']
                results.append({
                    'param_value': val,
                    'metric_value': metrics.get(metric_key, 0),
                    'total_return': metrics.get('total_return', 0),
                    'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                    'win_rate': metrics.get('win_rate', 0),
                    'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                    'total_trades': metrics.get('total_trades', 0),
                })
            else:
                results.append({
                    'param_value': val,
                    'metric_value': None,
                    'total_return': None,
                })

        return {
            'param_name': param_name,
            'param_values': param_values,
            'metric_key': metric_key,
            'results': results,
            'best_value': SensitivityAnalysis._find_best(results, metric_key),
        }

    @staticmethod
    def _find_best(results: List[Dict], metric_key: str) -> Dict:
        """找出最优参数值"""
        valid = [r for r in results if r.get('metric_value') is not None]
        if not valid:
            return None
        best = max(valid, key=lambda x: x['metric_value'])
        return {
            'param_value': best['param_value'],
            'metric_value': best['metric_value'],
        }