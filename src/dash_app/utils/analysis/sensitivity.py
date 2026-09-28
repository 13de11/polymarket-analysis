# src/dash_app/utils/analysis/sensitivity.py
"""
参数敏感性分析引擎
- 单参数：沿一个参数扫描
- 双参数：网格热力图
"""

import time
import traceback
from typing import Dict, Any, List, Optional

from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA,
    METRIC_SCHEMA,
    get_param_range,
    is_lower_better,
)


class SensitivityAnalysis:

    # ================= 单参数 =================
    @staticmethod
    def run_sensitivity_analysis(
        base_params: Dict[str, Any],
        param_name: str,
        param_values: Optional[List[float]] = None,
        metric_key: str = 'total_return',
        series: str = '7d',
        n_points: int = 10,
    ) -> Dict[str, Any]:
        if param_name not in PARAM_SCHEMA:
            return SensitivityAnalysis._empty_result(
                param_name, metric_key, f'未知参数: {param_name}'
            )
        if metric_key not in METRIC_SCHEMA:
            return SensitivityAnalysis._empty_result(
                param_name, metric_key, f'未知指标: {metric_key}'
            )

        if not param_values:
            param_values = get_param_range(param_name, n_points)

        results = []
        for val in param_values:
            params = dict(base_params)
            params[param_name] = val
            try:
                result = run_backtest(params, series)
            except Exception as e:
                results.append({
                    'param_value': val,
                    'metric_value': None,
                    'error': f'{type(e).__name__}: {e}',
                })
                continue

            if result and result.get('metrics'):
                m = result['metrics']
                row = {'param_value': val,
                       'metric_value': m.get(metric_key)}
                for k in METRIC_SCHEMA:
                    row[k] = m.get(k)
                results.append(row)
            else:
                results.append({'param_value': val, 'metric_value': None})

        direction = METRIC_SCHEMA[metric_key].get('direction', 'max')
        return {
            'param_name': param_name,
            'metric_key': metric_key,
            'param_values': param_values,
            'results': results,
            'best_value': SensitivityAnalysis._find_best(results, metric_key),
            'direction': direction,
            'error': None,
        }

    @staticmethod
    def _find_best(results: List[Dict], metric_key: str) -> Optional[Dict]:
        valid = [r for r in results if r.get('metric_value') is not None]
        if not valid:
            return None
        if is_lower_better(metric_key):
            best = min(valid, key=lambda x: x['metric_value'])
        else:
            best = max(valid, key=lambda x: x['metric_value'])
        return {
            'param_value': best['param_value'],
            'metric_value': best['metric_value'],
        }

    @staticmethod
    def _empty_result(param_name, metric_key, error):
        return {
            'param_name': param_name,
            'metric_key': metric_key,
            'param_values': [],
            'results': [],
            'best_value': None,
            'direction': None,
            'error': error,
        }

    @staticmethod
    def get_default_param_values(param_name: str, n_points: int = 10) -> List[float]:
        if param_name not in PARAM_SCHEMA:
            return []
        return get_param_range(param_name, n_points)

    # ================= 双参数网格 =================
    @staticmethod
    def run_grid_analysis(
        base_params: Dict[str, Any],
        param_x: str,
        param_y: str,
        metric_key: str = 'total_return',
        n_points_x: int = 5,
        n_points_y: int = 5,
        series: str = '7d',
    ) -> Dict[str, Any]:
        """
        双参数网格分析

        Returns:
            {
                'param_x': str, 'param_y': str, 'metric_key': str,
                'x_values': [...], 'y_values': [...],
                'z_matrix': [[...], ...],   # z[i][j] 对应 (y[i], x[j])
                'best_cell': {'x':..., 'y':..., 'metric_value':...} | None,
                'direction': 'max' | 'min',
                'error': str | None,
                'elapsed_sec': float,
            }
        """
        t0 = time.time()

        if param_x not in PARAM_SCHEMA:
            return SensitivityAnalysis._empty_grid(
                param_x, param_y, metric_key, f'未知参数: {param_x}',
                time.time() - t0)
        if param_y not in PARAM_SCHEMA:
            return SensitivityAnalysis._empty_grid(
                param_x, param_y, metric_key, f'未知参数: {param_y}',
                time.time() - t0)
        if param_x == param_y:
            return SensitivityAnalysis._empty_grid(
                param_x, param_y, metric_key, 'X 和 Y 不能是同一参数',
                time.time() - t0)
        if metric_key not in METRIC_SCHEMA:
            return SensitivityAnalysis._empty_grid(
                param_x, param_y, metric_key, f'未知指标: {metric_key}',
                time.time() - t0)

        x_values = get_param_range(param_x, n_points_x)
        y_values = get_param_range(param_y, n_points_y)

        lower_better = is_lower_better(metric_key)
        z_matrix = []
        best_cell = None
        best_val = None

        for yv in y_values:
            row = []
            for xv in x_values:
                params = dict(base_params)
                params[param_x] = xv
                params[param_y] = yv
                try:
                    result = run_backtest(params, series)
                    mv = (result or {}).get('metrics', {}).get(metric_key)
                except Exception:
                    mv = None

                if mv is None:
                    row.append(None)
                    continue

                try:
                    mv_f = float(mv)
                except (TypeError, ValueError):
                    row.append(None)
                    continue

                row.append(mv_f)
                if best_val is None or (mv_f < best_val if lower_better
                                        else mv_f > best_val):
                    best_val = mv_f
                    best_cell = {'x': xv, 'y': yv, 'metric_value': mv_f}
            z_matrix.append(row)

        return {
            'param_x': param_x,
            'param_y': param_y,
            'metric_key': metric_key,
            'x_values': x_values,
            'y_values': y_values,
            'z_matrix': z_matrix,
            'best_cell': best_cell,
            'direction': METRIC_SCHEMA[metric_key].get('direction'),
            'error': None,
            'elapsed_sec': time.time() - t0,
        }

    @staticmethod
    def _empty_grid(param_x, param_y, metric_key, error, elapsed):
        return {
            'param_x': param_x,
            'param_y': param_y,
            'metric_key': metric_key,
            'x_values': [],
            'y_values': [],
            'z_matrix': [],
            'best_cell': None,
            'direction': None,
            'error': error,
            'elapsed_sec': elapsed,
        }