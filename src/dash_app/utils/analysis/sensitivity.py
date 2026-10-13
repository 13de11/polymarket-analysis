# src/dash_app/utils/analysis/sensitivity.py
"""
参数敏感性分析引擎
- 单参数：沿一个参数扫描
- 双参数：网格热力图
"""

import time
import statistics
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

    # ================= 多市场敏感性 =================
    @staticmethod
    def run_sensitivity_multi_market(
        base_params: Dict[str, Any],
        param_name: str,
        param_values: Optional[List[float]] = None,
        metric_key: str = 'total_return',
        market_pairs: Optional[List] = None,
        series: str = '7d',
        n_points: int = 10,
    ) -> Dict[str, Any]:
        """
        在多个 (event_id, market_id) 上扫描单参数。

        Y 轴 = 该参数值下所有市场的平均指标
        辅助线 = 正收益市场占比（metric > 0）

        Args:
            base_params: 基础参数
            param_name: 要扫描的参数
            param_values: 参数值列表；None 时自动生成
            metric_key: 追踪指标
            market_pairs: [(event_id, market_id), ...]
            series: '7d' | '48h'
            n_points: 自动生成时的点数

        Returns:
            {
                'param_name', 'metric_key', 'direction',
                'param_values', 'results',
                'best_value', 'error', 'n_markets',
            }
            results 每项：
            {
                'param_value', 'metric_value',         # 兼容 _find_best
                'mean_metric', 'median_metric', 'std_metric',
                'win_rate',                            # 正收益市场占比 %
                'n_ok', 'n_total',
            }
        """
        if param_name not in PARAM_SCHEMA:
            return {'error': f'未知参数: {param_name}', 'results': []}
        if metric_key not in METRIC_SCHEMA:
            return {'error': f'未知指标: {metric_key}', 'results': []}
        if not market_pairs:
            return {'error': '未选择任何市场', 'results': []}

        if not param_values:
            param_values = get_param_range(param_name, n_points)

        results: List[Dict[str, Any]] = []
        n_total = len(market_pairs)

        for val in param_values:
            metrics_list: List[float] = []
            n_ok = 0

            for pair in market_pairs:
                if not pair or len(pair) < 2:
                    continue
                eid, mid = pair[0], pair[1]
                if not eid or not mid:
                    continue

                params = dict(base_params)
                params[param_name] = val
                params['event_id'] = eid
                params['market_id'] = mid

                try:
                    r = run_backtest(params, series)
                except Exception:
                    r = None

                if r and r.get('metrics'):
                    mv = r['metrics'].get(metric_key)
                    if mv is not None:
                        try:
                            metrics_list.append(float(mv))
                            n_ok += 1
                        except (TypeError, ValueError):
                            pass

            if metrics_list:
                mean_v = statistics.mean(metrics_list)
                median_v = statistics.median(metrics_list)
                std_v = (statistics.stdev(metrics_list)
                         if len(metrics_list) > 1 else 0.0)
                win_rate = (sum(1 for v in metrics_list if v > 0)
                            / len(metrics_list) * 100)
            else:
                mean_v = median_v = std_v = win_rate = None

            results.append({
                'param_value': val,
                'metric_value': mean_v,          # 兼容 _find_best
                'mean_metric': mean_v,
                'median_metric': median_v,
                'std_metric': std_v,
                'win_rate': win_rate,
                'n_ok': n_ok,
                'n_total': n_total,
            })

        direction = METRIC_SCHEMA[metric_key].get('direction', 'max')
        return {
            'param_name': param_name,
            'metric_key': metric_key,
            'direction': direction,
            'param_values': param_values,
            'results': results,
            'best_value': SensitivityAnalysis._find_best(results, metric_key),
            'error': None,
            'n_markets': n_total,
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