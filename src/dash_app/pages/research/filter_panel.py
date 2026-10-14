# src/dash_app/pages/research/filter_panel.py
"""
策略研究 - 参数收集与联动回调

Phase C（comparison tab 自包含）：
- save_cmp_params：读 cmp-* 组件 → cmp-params-store（comparison tab 专用）
- update_cmp_markets：cmp-event-selector → cmp-market-selector 联动
- toggle_cmp_window_custom / toggle_cmp_range_custom：cmp-* 折叠控件显隐
- sync_research_params_from_global：global-params → research-params-store
  （临时给 sensitivity/batch 用，下一轮各自自包含后删除）
"""

from dash import (Input, Output, State, callback, no_update)
from src.dash_app.utils.parsing import safe_float
from src.dash_app.utils.data_loader import get_target_market
from src.dash_app.state.global_params import (
    merge as _gp_merge,
    window_type_to_engine as _wt2e,
)


# ==================== cmp-params-store（comparison tab 专用） ====================

@callback(
    Output('cmp-params-store', 'data'),
    Input('cmp-event-selector', 'value'),
    Input('cmp-market-selector', 'value'),
    Input('cmp-price-type', 'value'),
    Input('cmp-window-type', 'value'),
    Input('cmp-window-custom', 'value'),
    Input('cmp-capacity', 'value'),
    Input('cmp-price-threshold', 'value'),
    Input('cmp-distance-threshold', 'value'),
    Input('cmp-inertia', 'value'),
    Input('cmp-momentum-enable', 'value'),
    Input('cmp-momentum-coef', 'value'),
    Input('cmp-signal-mode', 'value'),
    Input('cmp-initial-capital', 'value'),
    Input('cmp-position-mode', 'value'),
    Input('cmp-position-size', 'value'),
    Input('cmp-range', 'value'),
    Input('cmp-range-custom', 'value'),
    prevent_initial_call=False,
)
def save_cmp_params(event_id, market_id, price_type, window_type,
                    window_custom, capacity, price_threshold,
                    distance_threshold, inertia, momentum_enable,
                    momentum_coef, signal_mode, initial_capital,
                    position_mode, position_size, backtest_range,
                    backtest_range_custom):
    """收集 cmp-* 面板组件值 → cmp-params-store"""
    if not market_id:
        return {}

    if window_type == '7d':
        wm, wp, ws = 'rolling', 168, None
    elif window_type == 'gamestart':
        wm, wp, ws = 'expanding', None, 'gamestart'
    else:
        wm, wp, ws = 'expanding', None, 'open'

    return {
        'event_id': event_id,
        'market_id': market_id,
        'price_type': price_type or 'price_last',
        'window_type': window_type,
        'window_mode': wm, 'window_param': wp, 'window_start': ws,
        'window_custom_hours': window_custom,
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
        'backtest_range_custom': backtest_range_custom,
    }


# ==================== cmp 事件→市场联动 ====================

@callback(
    Output('cmp-market-selector', 'options'),
    Output('cmp-market-selector', 'value'),
    Input('cmp-event-selector', 'value'),
    State('cmp-market-selector', 'value'),
    prevent_initial_call=False,
)
def update_cmp_markets(event_id, current_market):
    """事件选择 → 市场下拉填充（comparison tab 专用）"""
    if not event_id:
        return [], None

    target = get_target_market(event_id)
    if not target:
        return [], None

    r_start = int(target['range_start'])
    r_end = (int(target['range_end'])
             if target['range_end']
             and not str(target['range_end']) == 'nan'
             else '∞')
    label = (f"{target.get('name', '目标市场')} "
             f"(命中: {r_start}-{r_end})")
    options = [{'label': label, 'value': target['id']}]

    # 保留当前选择，否则选第一个
    value = current_market if current_market == target['id'] else target['id']
    return options, value


# ==================== cmp 折叠控件显隐 ====================

@callback(
    Output('cmp-window-custom-container', 'style'),
    Input('cmp-window-type', 'value'),
    prevent_initial_call=False,
)
def toggle_cmp_window_custom(window_type):
    return {'marginTop': '4px',
            'display': 'block' if window_type == 'custom' else 'none'}


@callback(
    Output('cmp-range-custom-container', 'style'),
    Input('cmp-range', 'value'),
    prevent_initial_call=False,
)
def toggle_cmp_range_custom(backtest_range):
    return {'marginTop': '8px',
            'display': 'block' if backtest_range == 'custom' else 'none'}


# ==================== research-params-store（临时：从 global-params 同步） ====================

@callback(
    Output('research-params-store', 'data'),
    Input('global-params', 'data'),
    prevent_initial_call=False,
)
def sync_research_params_from_global(global_params):
    """临时：sensitivity/batch 仍读 research-params-store，
    从 global-params 同步。下一轮各自自包含后删除此回调。"""
    if not global_params:
        return {}
    p = _gp_merge(global_params)
    # 过滤掉非业务字段
    return {k: v for k, v in p.items()
            if not k.startswith('_') and v is not None}
