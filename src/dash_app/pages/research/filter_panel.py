"""
策略研究 - 参数收集回调

Phase 3：面板渲染交给 create_shared_panel（shared/params_panel.py），
本文件只保留 save_research_params 回调（收集 param-* 组件值 → research-params-store）。
事件/市场联动回调已合并到 backtest/callbacks.py（统一 param-* ID + 双页 pathname 守卫）。
"""

from dash import Input, Output, callback
from src.dash_app.utils.parsing import safe_float


@callback(
    Output('research-params-store', 'data'),
    Input('param-event-selector', 'value'),
    Input('param-market-selector', 'value'),
    Input('param-price-type', 'value'),
    Input('param-window-type', 'value'),
    Input('param-capacity', 'value'),
    Input('param-price-threshold', 'value'),
    Input('param-distance-threshold', 'value'),
    Input('param-inertia', 'value'),
    Input('param-momentum-enable', 'value'),
    Input('param-momentum-coef', 'value'),
    Input('param-signal-mode', 'value'),
    Input('param-initial-capital', 'value'),
    Input('param-position-mode', 'value'),
    Input('param-position-size', 'value'),
    Input('param-range', 'value'),
)
def save_research_params(event_id, market_id, price_type, window_type,
                         capacity, price_threshold, distance_threshold, inertia,
                         momentum_enable, momentum_coef, signal_mode,
                         initial_capital, position_mode, position_size,
                         backtest_range):
    """收集 param-* 面板组件值 → research-params-store（供对比/敏感性/批量回调读取）"""
    if not market_id:
        return {}

    if window_type == '7d':
        window_mode, window_param, window_start = 'rolling', 168, None
    elif window_type == 'gamestart':
        window_mode, window_param, window_start = 'expanding', None, 'gamestart'
    else:
        window_mode, window_param, window_start = 'expanding', None, 'open'

    return {
        'event_id': event_id,
        'market_id': market_id,
        'price_type': price_type or 'price_last',
        'window_type': window_type,
        'window_mode': window_mode,
        'window_param': window_param,
        'window_start': window_start,
        'capacity': capacity or 0,
        'price_threshold': price_threshold or 0.005,
        'distance_threshold': distance_threshold or 1.5,
        'inertia': inertia or 6,
        'momentum_enable': momentum_enable,
        'momentum_coef': momentum_coef or 0.10,
        'signal_mode': signal_mode or 'start',
        'initial_capital': safe_float(initial_capital, default=100.0,
                                      min_val=1.0),
        'position_mode': position_mode or 'fixed_amount',
        'position_size': safe_float(position_size, default=10.0,
                                    min_val=0.01),
        'backtest_range': backtest_range or 'full',
    }
