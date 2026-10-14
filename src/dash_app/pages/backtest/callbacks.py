"""
预测回测系统 - 所有回调

回退到 4 tab 模式。render_tab_content 直接返回 render 函数的元组（content, status），
不再包装 html.Div（避免 React 渲染错误）。
"""
from dash import (html, Input, Output, State, callback, no_update)
import pandas as pd

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_target_markets_batch,
)
from src.dash_app.utils.parsing import safe_int, safe_float
from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.pages.backtest.tabs.preview import render_preview_tab
from src.dash_app.pages.backtest.tabs.overview import render_overview_tab
from src.dash_app.pages.backtest.tabs.trades import render_trades_tab
from src.dash_app.pages.backtest.tabs.evaluation import render_evaluation


# ==================== 面板联动 ====================

@callback(
    Output('param-range-custom-container', 'style'),
    Input('param-range', 'value'),
    Input('url', 'pathname'),
)
def toggle_custom_range(range_type, pathname):
    if pathname not in ('/backtest', '/research'):
        return no_update
    if range_type == 'custom':
        return {'display': 'block', 'marginTop': '8px'}
    return {'display': 'none', 'marginTop': '8px'}


@callback(
    Output('param-market-selector', 'options'),
    Output('param-market-selector', 'value'),
    Input('param-event-selector', 'value'),
    Input('url', 'pathname'),
    Input('global-params', 'data'),
)
def update_markets(event_id, pathname, global_params):
    if pathname != '/backtest':
        return no_update, no_update
    if not event_id:
        return [], None
    markets_df = get_markets_by_event(event_id)
    if markets_df.empty:
        return [], None
    options = []
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        if pd.isna(row['range_end']) or row['range_end'] is None:
            label = f"{r_start}-∞"
        else:
            label = f"{r_start}-{int(row['range_end'])}"
        options.append({'label': label, 'value': row['id']})
    target_id = None
    if global_params and global_params.get('market_id'):
        mid = global_params['market_id']
        if any(o['value'] == mid for o in options):
            target_id = mid
    if target_id is None:
        target = get_target_market(event_id)
        target_id = target['id'] if target else None
    return options, target_id


@callback(
    Output('param-event-selector', 'options'),
    Output('param-event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
    Input('global-params', 'data'),
)
def update_events_on_series_change(series, pathname, global_params):
    if pathname != '/backtest':
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
    if global_params and global_params.get('event_id'):
        eid = global_params['event_id']
        if eid in event_ids:
            target_event = eid
    if target_event is None:
        target_event = events_df.iloc[-1]['id']
    return event_options, target_event


@callback(
    Output('global-params', 'data'),
    Input('param-run-btn', 'n_clicks'),
    State('param-event-selector', 'value'),
    State('param-market-selector', 'value'),
    State('param-price-type', 'value'),
    State('param-window-type', 'value'),
    State('param-window-custom', 'value'),
    State('param-capacity', 'value'),
    State('param-price-threshold', 'value'),
    State('param-distance-threshold', 'value'),
    State('param-inertia', 'value'),
    State('param-momentum-enable', 'value'),
    State('param-momentum-coef', 'value'),
    State('param-signal-mode', 'value'),
    State('param-initial-capital', 'value'),
    State('param-position-mode', 'value'),
    State('param-position-size', 'value'),
    State('param-range', 'value'),
    State('param-range-custom', 'value'),
    prevent_initial_call=True,
)
def save_params(n_clicks, event_id, market_id,
                price_type, window_type, window_custom,
                capacity, price_threshold, distance_threshold, inertia,
                momentum_enable, momentum_coef, signal_mode,
                initial_capital, position_mode, position_size,
                backtest_range, backtest_range_custom):
    if not n_clicks:
        return no_update
    if window_type == '7d':
        window_mode, window_param, window_start = 'rolling', 168, None
    elif window_type == 'gamestart':
        window_mode, window_param, window_start = 'expanding', None, 'gamestart'
    elif window_type == 'open':
        window_mode, window_param, window_start = 'expanding', None, 'open'
    else:
        window_mode = 'rolling'
        window_param = safe_int(window_custom, default=168, min_val=1)
        window_start = None
    return {
        'event_id': event_id, 'market_id': market_id,
        'price_type': price_type or 'price_last',
        'window_type': window_type, 'window_mode': window_mode,
        'window_param': window_param, 'window_start': window_start,
        'capacity': capacity or 0,
        'price_threshold': price_threshold or 0.005,
        'distance_threshold': distance_threshold or 1.5,
        'inertia': inertia or 6,
        'momentum_enable': momentum_enable,
        'momentum_coef': momentum_coef or 0.10,
        'signal_mode': signal_mode or 'start',
        'initial_capital': safe_float(initial_capital, default=100.0, min_val=1.0),
        'position_mode': position_mode or 'fixed_amount',
        'position_size': safe_float(position_size, default=10.0, min_val=0.01),
        'backtest_range': backtest_range or 'full',
        'backtest_range_custom': backtest_range_custom or [0, 100],
    }


@callback(
    Output('param-window-custom-container', 'style'),
    Input('param-window-type', 'value'),
)
def toggle_custom_window(window_type):
    if window_type == 'custom':
        return {'marginTop': '4px'}
    return {'marginTop': '4px', 'display': 'none'}


# ==================== 回测执行 ====================

@callback(
    Output('backtest-result-store', 'data'),
    Input('global-params', 'data'),
    prevent_initial_call=True,
)
def cache_backtest_result(params):
    if not params or not params.get('market_id'):
        return {'error': '未选择事件或市场'}
    result = run_backtest(params)
    if not result:
        return {'error': '回测失败（数据不足或参数无效，请检查事件/市场/区间）'}
    return {
        'metrics': result.get('metrics', {}),
        'trades': result.get('trades', []),
        'equity_curve': result.get('equity_curve', []),
        'final_capital': result.get('final_capital'),
    }


# ==================== Tab 内容分发 ====================

def _placeholder(msg):
    return html.Div(msg, style={
        'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0',
    })


@callback(
    Output('backtest-tab-content', 'children'),
    Output('backtest-status-text', 'children'),
    Input('backtest-tabs', 'value'),
    Input('backtest-result-store', 'data'),
    State('global-params', 'data'),
    State('series-selector', 'value'),
)
def render_tab_content(tab_name, cached_result, params, series):
    if not params or not params.get('market_id'):
        return _placeholder("请选择事件和市场，点击「运行回测」"), \
               "请选择事件和市场"

    series = series or '7d'

    if tab_name == 'preview':
        content, stats = render_preview_tab(params, series)
        n = stats.get('total_signals', 0)
        acc = stats.get('overall_accuracy', 0) * 100
        return content, f"✅ 信号预览 | 信号总数: {n} | 方向准确率: {acc:.1f}%"

    if cached_result and cached_result.get('error'):
        err = cached_result['error']
        return _placeholder(f"❌ {err}"), f"❌ {err}"

    if not cached_result or not cached_result.get('metrics'):
        return _placeholder("暂无回测结果，请点击「运行回测」"), \
               "暂无回测结果"

    # render_overview_tab / render_trades_tab / render_evaluation
    # 各自返回 (content, status_text) 元组，直接透传
    if tab_name == 'overview':
        return render_overview_tab(cached_result)
    if tab_name == 'trades':
        return render_trades_tab(cached_result)
    if tab_name == 'evaluation':
        return render_evaluation(params, cached_result)

    return _placeholder("未知 Tab"), ""


# ==================== 导入参数同步（C1） ====================

@callback(
    Output('param-price-type', 'value'),
    Output('param-window-type', 'value'),
    Output('param-window-custom', 'value'),
    Output('param-capacity', 'value'),
    Output('param-price-threshold', 'value'),
    Output('param-distance-threshold', 'value'),
    Output('param-inertia', 'value'),
    Output('param-momentum-enable', 'value'),
    Output('param-momentum-coef', 'value'),
    Output('param-signal-mode', 'value'),
    Output('param-initial-capital', 'value'),
    Output('param-position-mode', 'value'),
    Output('param-position-size', 'value'),
    Output('param-range', 'value'),
    Output('param-range-custom', 'value'),
    Input('global-params', 'data'),
    prevent_initial_call=True,
)
def sync_panel_from_import(params):
    """C1: global-params 带 _pending_nav 时同步到面板组件。"""
    if not params or not params.get('_pending_nav'):
        return tuple(no_update for _ in range(15))
    return (
        params.get('price_type') or 'price_last',
        params.get('window_type') or '7d',
        str(params.get('window_custom_hours') or ''),
        params.get('capacity') if params.get('capacity') is not None else 0.5,
        params.get('price_threshold') if params.get('price_threshold') is not None else 0.005,
        params.get('distance_threshold') if params.get('distance_threshold') is not None else 1.5,
        params.get('inertia') if params.get('inertia') is not None else 6,
        params.get('momentum_enable') if params.get('momentum_enable') is not None else True,
        params.get('momentum_coef') if params.get('momentum_coef') is not None else 0.10,
        params.get('signal_mode') or 'start',
        params.get('initial_capital') if params.get('initial_capital') is not None else 100.0,
        params.get('position_mode') or 'fixed_amount',
        params.get('position_size') if params.get('position_size') is not None else 10.0,
        params.get('backtest_range') or 'full',
        list(params.get('backtest_range_custom') or [0, 100]),
    )
