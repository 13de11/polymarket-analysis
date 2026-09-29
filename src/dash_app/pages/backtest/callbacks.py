# src/dash_app/pages/backtest/callbacks.py
"""
预测回测系统 - 所有回调

用 @callback 装饰器（模块被 import 时自动注册）。
app_new.py 里有一处 import 本模块，触发注册。
"""

import dash
from dash import html, dcc, Input, Output, State, callback, no_update
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


# ==================== 参数面板联动 ====================

@callback(
    Output('backtest-range-custom-container', 'style'),
    Input('backtest-range', 'value'),
    Input('url', 'pathname'),
)
def toggle_custom_range(range_type, pathname):
    if pathname != '/backtest':
        return no_update
    if range_type == 'custom':
        return {'display': 'block', 'marginTop': '8px'}
    return {'display': 'none', 'marginTop': '8px'}


@callback(
    Output('backtest-market-selector', 'options'),
    Output('backtest-market-selector', 'value'),
    Input('backtest-event-selector', 'value'),
    Input('url', 'pathname'),
)
def update_markets(event_id, pathname):
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
    target = get_target_market(event_id)
    default_value = target['id'] if target else None
    return options, default_value


@callback(
    Output('backtest-event-selector', 'options'),
    Output('backtest-event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
)
def update_backtest_events_on_series_change(series, pathname):
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
                     if target['range_end'] and not pd.isna(target['range_end'])
                     else '∞')
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})
    default_event = events_df.iloc[-1]['id'] if not events_df.empty else None
    return event_options, default_event


@callback(
    Output('backtest-params-store', 'data'),
    Input('backtest-run-btn', 'n_clicks'),
    Input('backtest-preview-btn', 'n_clicks'),
    State('backtest-event-selector', 'value'),
    State('backtest-market-selector', 'value'),
    State('backtest-price-type', 'value'),
    State('backtest-window-type', 'value'),
    State('backtest-window-custom', 'value'),
    State('backtest-capacity', 'value'),
    State('backtest-price-threshold', 'value'),
    State('backtest-distance-threshold', 'value'),
    State('backtest-inertia', 'value'),
    State('backtest-momentum-enable', 'value'),
    State('backtest-momentum-coef', 'value'),
    State('backtest-signal-mode', 'value'),
    State('backtest-initial-capital', 'value'),
    State('backtest-position-mode', 'value'),
    State('backtest-position-size', 'value'),
    State('backtest-range', 'value'),
    State('backtest-range-custom', 'value'),
)
def save_params(n_clicks_run, n_clicks_preview, event_id, market_id,
                price_type, window_type, window_custom,
                capacity, price_threshold, distance_threshold, inertia,
                momentum_enable, momentum_coef, signal_mode,
                initial_capital, position_mode, position_size,
                backtest_range, backtest_range_custom):
    trigger = (dash.callback_context.triggered[0]['prop_id']
               if dash.callback_context.triggered else '')
    if not trigger or (not n_clicks_run and not n_clicks_preview):
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
        'backtest_range_custom': backtest_range_custom or [0, 100],
    }


@callback(
    Output('backtest-window-custom-container', 'style'),
    Input('backtest-window-type', 'value'),
)
def toggle_custom_window(window_type):
    if window_type == 'custom':
        return {'marginTop': '4px'}
    return {'marginTop': '4px', 'display': 'none'}


# ==================== 回测执行 ====================

@callback(
    Output('backtest-result-store', 'data'),
    Input('backtest-run-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    prevent_initial_call=True,
)
def cache_backtest_result(n_clicks, params):
    if not n_clicks:
        return no_update
    if not params or not params.get('market_id'):
        return {}
    result = run_backtest(params)
    if not result:
        return {}
    return {
        'metrics': result.get('metrics', {}),
        'trades': result.get('trades', []),
        'equity_curve': result.get('equity_curve', []),
        'final_capital': result.get('final_capital'),
    }


# ==================== Tab 内容分发 ====================

def _placeholder(msg):
    return html.Div(msg, style={
        'color': '#6c757d', 'textAlign': 'center',
        'padding': '40px 0',
    })


@callback(
    Output('backtest-tab-content', 'children'),
    Output('backtest-status-text', 'children'),
    Input('backtest-tabs', 'value'),
    Input('backtest-result-store', 'data'),
    Input('backtest-preview-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    State('series-selector', 'value'),
)
def render_tab_content(tab_name, cached_result, preview_n, params, series):
    if not params or not params.get('market_id'):
        return _placeholder("请选择事件和市场，点击「运行回测」"), \
               "请选择事件和市场"

    series = series or '7d'

    if tab_name == 'preview':
        content, stats = render_preview_tab(params, series)
        n = stats.get('total_signals', 0)
        acc = stats.get('overall_accuracy', 0) * 100
        return content, f"✅ 信号预览 | 信号总数: {n} | 方向准确率: {acc:.1f}%"

    if not cached_result or not cached_result.get('metrics'):
        return _placeholder("暂无回测结果，请点击「运行回测」"), \
               "暂无回测结果"

    if tab_name == 'overview':
        return render_overview_tab(cached_result)
    if tab_name == 'trades':
        return render_trades_tab(cached_result)
    if tab_name == 'evaluation':
        return render_evaluation(params, cached_result)

    return _placeholder("未知 Tab"), ""


# ==================== 交易明细导出 ====================

@callback(
    Output('backtest-trades-download', 'data'),
    Input('backtest-trades-export-btn', 'n_clicks'),
    State('backtest-result-store', 'data'),
    prevent_initial_call=True,
)
def export_trades(n_clicks, cached_result):
    if not n_clicks or not cached_result:
        return no_update
    trades = cached_result.get('trades', [])
    completed = [t for t in trades if t.get('result') != 'pending']
    if not completed:
        df = pd.DataFrame(columns=['提示'])
        df.loc[0] = ['无已完成交易']
    else:
        df = pd.DataFrame(completed)
    return dcc.send_data_frame(df.to_csv, 'backtest_trades.csv',
                               index=False, encoding='utf-8-sig')