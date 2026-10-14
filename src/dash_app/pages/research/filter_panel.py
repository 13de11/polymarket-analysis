# src/dash_app/pages/research/filter_panel.py
"""
策略研究 - comparison tab 的回调

Phase C1 修订：
- save_cmp_params：只收集事件/市场/交易设置（execution 组）→ cmp-params-store
  信号参数（dimension + signal）在策略卡片各自配置，不再放顶部
- update_cmp_events：series + pathname + global-params → cmp-event-selector
- update_cmp_markets：cmp-event-selector → cmp-market-selector 联动
- toggle_cmp_range_custom：cmp-range 折叠控件显隐
- sync_research_params_from_global：临时给 sensitivity/batch 用
"""

import pandas as pd
from dash import (Input, Output, State, callback, no_update)
from src.dash_app.utils.parsing import safe_float
from src.dash_app.utils.data_loader import (
    get_elon_tweet_events, get_target_market,
    get_target_markets_batch, get_markets_by_event,
)
from src.dash_app.state.global_params import merge as _gp_merge


# ==================== cmp 事件列表（series 切换时更新） ====================

@callback(
    Output('cmp-event-selector', 'options'),
    Output('cmp-event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
    Input('global-params', 'data'),
    prevent_initial_call=False,
)
def update_cmp_events(series, pathname, global_params):
    """series 变化或页面加载时，更新 cmp-event-selector 选项"""
    if pathname != '/research':
        return no_update, no_update
    events_df = get_elon_tweet_events(series)
    if events_df.empty:
        return [], None
    event_ids = events_df['id'].tolist()
    targets_map = get_target_markets_batch(event_ids)
    event_options = []
    for _, row in events_df.iterrows():
        target = targets_map.get(row['id'])
        if target:
            r_start = int(target['range_start'])
            r_end = (int(target['range_end'])
                     if target['range_end']
                     and not pd.isna(target['range_end'])
                     else '∞')
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})
    target_event = None
    if global_params and global_params.get('event_id') in event_ids:
        target_event = global_params['event_id']
    if target_event is None and not events_df.empty:
        target_event = events_df.iloc[-1]['id']
    return event_options, target_event


# ==================== cmp 事件→市场联动 ====================

@callback(
    Output('cmp-market-selector', 'options'),
    Output('cmp-market-selector', 'value'),
    Input('cmp-event-selector', 'value'),
    State('cmp-market-selector', 'value'),
    prevent_initial_call=False,
)
def update_cmp_markets(event_id, current_market):
    """事件选择 → 市场下拉填充全部市场（不只 target）"""
    if not event_id:
        return [], None
    markets_df = get_markets_by_event(event_id)
    if markets_df is None or markets_df.empty:
        return [], None
    options = []
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        r_end = row.get('range_end')
        if pd.isna(r_end) or r_end is None:
            label = f"{r_start}-∞"
        else:
            label = f"{r_start}-{int(r_end)}"
        options.append({'label': label, 'value': row['id']})
    # 保留当前选择，否则选 target market
    value = current_market
    if value is None or not any(o['value'] == value for o in options):
        target = get_target_market(event_id)
        value = target['id'] if target else options[0]['value']
    return options, value


# ==================== cmp-params-store（只含事件/市场/交易设置） ====================

@callback(
    Output('cmp-params-store', 'data'),
    Input('cmp-event-selector', 'value'),
    Input('cmp-market-selector', 'value'),
    Input('cmp-initial-capital', 'value'),
    Input('cmp-position-mode', 'value'),
    Input('cmp-position-size', 'value'),
    Input('cmp-range', 'value'),
    Input('cmp-range-custom', 'value'),
    prevent_initial_call=False,
)
def save_cmp_params(event_id, market_id, initial_capital,
                    position_mode, position_size,
                    backtest_range, backtest_range_custom):
    """收集 cmp-* 顶部配置区（事件/市场/交易设置）→ cmp-params-store。
    信号参数在策略卡片各自配置，不在这里收集。"""
    if not market_id:
        return {}
    return {
        'event_id': event_id,
        'market_id': market_id,
        'price_type': 'price_last',  # 默认值，策略卡片可覆盖
        'initial_capital': safe_float(initial_capital, default=100.0,
                                      min_val=1.0),
        'position_mode': position_mode or 'fixed_amount',
        'position_size': safe_float(position_size, default=10.0,
                                    min_val=0.01),
        'backtest_range': backtest_range or 'full',
        'backtest_range_custom': backtest_range_custom,
    }


# ==================== cmp 折叠控件显隐 ====================

@callback(
    Output('cmp-range-custom-container', 'style'),
    Input('cmp-range', 'value'),
    prevent_initial_call=False,
)
def toggle_cmp_range_custom(backtest_range):
    return {'marginTop': '8px',
            'display': 'block' if backtest_range == 'custom' else 'none'}


# ==================== sens-* （sensitivity tab 扫参基准） ====================

@callback(
    Output('sens-params-store', 'data'),
    Input('sens-event-selector', 'value'),
    Input('sens-market-selector', 'value'),
    Input('sens-price-type', 'value'),
    Input('sens-window-type', 'value'),
    Input('sens-window-custom', 'value'),
    Input('sens-capacity', 'value'),
    Input('sens-price-threshold', 'value'),
    Input('sens-distance-threshold', 'value'),
    Input('sens-inertia', 'value'),
    Input('sens-momentum-enable', 'value'),
    Input('sens-momentum-coef', 'value'),
    Input('sens-signal-mode', 'value'),
    Input('sens-initial-capital', 'value'),
    Input('sens-position-mode', 'value'),
    Input('sens-position-size', 'value'),
    Input('sens-range', 'value'),
    Input('sens-range-custom', 'value'),
    prevent_initial_call=False,
)
def save_sens_params(event_id, market_id, price_type, window_type,
                    window_custom, capacity, price_threshold,
                    distance_threshold, inertia, momentum_enable,
                    momentum_coef, signal_mode, initial_capital,
                    position_mode, position_size, backtest_range,
                    backtest_range_custom):
    """收集 sens-* 面板全部值 → sens-params-store（扫参基准）"""
    if not market_id:
        return {}
    if window_type == '7d':
        wm, wp, ws = 'rolling', 168, None
    elif window_type == 'gamestart':
        wm, wp, ws = 'expanding', None, 'gamestart'
    else:
        wm, wp, ws = 'expanding', None, 'open'
    return {
        'event_id': event_id, 'market_id': market_id,
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


@callback(
    Output('sens-event-selector', 'options'),
    Output('sens-event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
    Input('global-params', 'data'),
    prevent_initial_call=False,
)
def update_sens_events(series, pathname, global_params):
    if pathname != '/research':
        return no_update, no_update
    events_df = get_elon_tweet_events(series)
    if events_df is None or events_df.empty:
        return [], None
    event_ids = events_df['id'].tolist()
    targets_map = get_target_markets_batch(event_ids)
    event_options = []
    for _, row in events_df.iterrows():
        target = targets_map.get(row['id'])
        if target:
            r_start = int(target['range_start'])
            r_end = (int(target['range_end'])
                     if target['range_end']
                     and not pd.isna(target['range_end'])
                     else '∞')
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})
    target_event = None
    if global_params and global_params.get('event_id') in event_ids:
        target_event = global_params['event_id']
    if target_event is None and not events_df.empty:
        target_event = events_df.iloc[-1]['id']
    return event_options, target_event


@callback(
    Output('sens-market-selector', 'options'),
    Output('sens-market-selector', 'value'),
    Input('sens-event-selector', 'value'),
    State('sens-market-selector', 'value'),
    prevent_initial_call=False,
)
def update_sens_markets(event_id, current_market):
    if not event_id:
        return [], None
    markets_df = get_markets_by_event(event_id)
    if markets_df is None or markets_df.empty:
        return [], None
    options = []
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        r_end = row.get('range_end')
        if pd.isna(r_end) or r_end is None:
            label = f"{r_start}-∞"
        else:
            label = f"{r_start}-{int(r_end)}"
        options.append({'label': label, 'value': row['id']})
    value = current_market
    if value is None or not any(o['value'] == value for o in options):
        target = get_target_market(event_id)
        value = target['id'] if target else options[0]['value']
    return options, value


@callback(
    Output('sens-window-custom-container', 'style'),
    Input('sens-window-type', 'value'),
    prevent_initial_call=False,
)
def toggle_sens_window_custom(window_type):
    return {'marginTop': '4px',
            'display': 'block' if window_type == 'custom' else 'none'}


@callback(
    Output('sens-range-custom-container', 'style'),
    Input('sens-range', 'value'),
    prevent_initial_call=False,
)
def toggle_sens_range_custom(backtest_range):
    return {'marginTop': '8px',
            'display': 'block' if backtest_range == 'custom' else 'none'}


# ==================== batch-* （batch tab 参数模板） ====================

@callback(
    Output('batch-params-store', 'data'),
    Input('batch-price-type', 'value'),
    Input('batch-window-type', 'value'),
    Input('batch-window-custom', 'value'),
    Input('batch-capacity', 'value'),
    Input('batch-price-threshold', 'value'),
    Input('batch-distance-threshold', 'value'),
    Input('batch-inertia', 'value'),
    Input('batch-momentum-enable', 'value'),
    Input('batch-momentum-coef', 'value'),
    Input('batch-signal-mode', 'value'),
    Input('batch-initial-capital', 'value'),
    Input('batch-position-mode', 'value'),
    Input('batch-position-size', 'value'),
    Input('batch-range', 'value'),
    Input('batch-range-custom', 'value'),
    prevent_initial_call=False,
)
def save_batch_params(price_type, window_type, window_custom,
                     capacity, price_threshold, distance_threshold,
                     inertia, momentum_enable, momentum_coef,
                     signal_mode, initial_capital, position_mode,
                     position_size, backtest_range,
                     backtest_range_custom):
    """收集 batch-* 信号参数 + 交易设置 → batch-params-store（参数模板）。
    不含 event_id/market_id——batch 用多选选择器，BatchEngine 动态覆盖。"""
    if window_type == '7d':
        wm, wp, ws = 'rolling', 168, None
    elif window_type == 'gamestart':
        wm, wp, ws = 'expanding', None, 'gamestart'
    else:
        wm, wp, ws = 'expanding', None, 'open'
    return {
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


@callback(
    Output('batch-window-custom-container', 'style'),
    Input('batch-window-type', 'value'),
    prevent_initial_call=False,
)
def toggle_batch_window_custom(window_type):
    return {'marginTop': '4px',
            'display': 'block' if window_type == 'custom' else 'none'}


@callback(
    Output('batch-range-custom-container', 'style'),
    Input('batch-range', 'value'),
    prevent_initial_call=False,
)
def toggle_batch_range_custom(backtest_range):
    return {'marginTop': '8px',
            'display': 'block' if backtest_range == 'custom' else 'none'}


# ==================== research-params-store（已废弃） ====================
# comparison → cmp-params-store，sensitivity → sens-params-store，
# batch → batch-params-store。research-params-store 不再有人读。
# sync_research_params_from_global 已删除。
