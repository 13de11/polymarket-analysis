"""
策略研究 - 精简参数面板
与回测页独立，ID 前缀 research-
"""

import dash
from dash import html, dcc, Input, Output, State
import pandas as pd

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_target_markets_batch,
)


def create_research_panel(series='7d'):
    """创建研究页参数面板"""
    events_df = get_elon_tweet_events(series)
    event_ids = events_df['id'].tolist()
    targets_map = get_target_markets_batch(event_ids)

    event_options = []
    for _, row in events_df.iterrows():
        target = targets_map.get(row['id'])
        if target:
            r_start = int(target['range_start'])
            r_end = int(target['range_end']) if target['range_end'] and not pd.isna(target['range_end']) else '∞'
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})

    default_event = events_df.iloc[-1]['id'] if not events_df.empty else None

    return html.Div([

        html.Div([
            html.H4("🔬 研究参数", style={'margin': 0, 'color': '#2c3e50'}),
            html.P("配置基础参数，选择对比策略 / 敏感性分析",
                   style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '4px 0 0 0'})
        ], style={'borderBottom': '2px solid #6c5ce7', 'paddingBottom': '10px', 'marginBottom': '15px'}),

        # ========== 数据选择 ==========
        html.Details([
            html.Summary("📊 数据选择", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("事件:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-event-selector',
                        options=event_options,
                        value=default_event,
                        placeholder='请选择事件',
                        style={'width': '100%', 'marginTop': '3px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("目标市场:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-market-selector',
                        options=[],
                        placeholder='请先选择事件',
                        style={'width': '100%', 'marginTop': '3px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("价格类型:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.RadioItems(
                        id='research-price-type',
                        options=[
                            {'label': ' 最新价', 'value': 'price_last'},
                            {'label': ' 均价', 'value': 'price_avg'}
                        ],
                        value='price_last',
                        inline=True,
                        style={'marginTop': '4px', 'fontSize': '13px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("推文速率窗口:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.RadioItems(
                        id='research-window-type',
                        options=[
                            {'label': ' 7天', 'value': '7d'},
                            {'label': ' gamestart', 'value': 'gamestart'},
                            {'label': ' 开盘', 'value': 'open'},
                        ],
                        value='7d',
                        inline=True,
                        style={'marginTop': '4px', 'fontSize': '12px'}
                    ),
                ], style={'marginBottom': '0px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], open=True, style={'marginBottom': '12px'}),

        # ========== 策略参数 ==========
        html.Details([
            html.Summary("🧠 策略参数", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("容差:", style={'fontSize': '12px'}),
                    dcc.Slider(
                        id='research-capacity',
                        min=0, max=5, step=0.5, value=0.5,
                        marks={i: str(i) for i in range(0, 6, 1)},
                        tooltip={'placement': 'bottom'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("价格变动阈值:", style={'fontSize': '12px'}),
                    dcc.Slider(
                        id='research-price-threshold',
                        min=0.001, max=0.02, step=0.001, value=0.005,
                        marks={0.005: '0.005', 0.01: '0.01', 0.015: '0.015', 0.02: '0.02'},
                        tooltip={'placement': 'bottom'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("距离变动阈值:", style={'fontSize': '12px'}),
                    dcc.Slider(
                        id='research-distance-threshold',
                        min=0.5, max=4.0, step=0.1, value=1.5,
                        marks={0.5: '0.5', 1.0: '1.0', 2.0: '2.0', 3.0: '3.0', 4.0: '4.0'},
                        tooltip={'placement': 'bottom'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("惯性重置 (小时):", style={'fontSize': '12px'}),
                    dcc.Slider(
                        id='research-inertia',
                        min=1, max=12, step=1, value=6,
                        marks={i: str(i) for i in range(1, 13, 2)},
                        tooltip={'placement': 'bottom'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Div([
                        html.Label("动量修正:", style={'fontSize': '12px'}),
                        dcc.RadioItems(
                            id='research-momentum-enable',
                            options=[{'label': ' 开', 'value': True}, {'label': ' 关', 'value': False}],
                            value=True, inline=True, style={'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("动量系数:", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='research-momentum-coef',
                            min=0.01, max=0.30, step=0.01, value=0.10,
                            marks={0.01: '0.01', 0.10: '0.10', 0.20: '0.20', 0.30: '0.30'},
                            tooltip={'placement': 'bottom'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '10px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '12px'}),

        # ========== 回测执行 ==========
        html.Details([
            html.Summary("💰 回测执行", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("初始资金:", style={'fontSize': '12px'}),
                    dcc.Input(
                        id='research-initial-capital',
                        type='text', value='100', debounce=True,
                        style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                    ),
                ], style={'marginBottom': '8px'}),
                html.Div([
                    html.Label("开仓模式:", style={'fontSize': '12px'}),
                    dcc.RadioItems(
                        id='research-position-mode',
                        options=[
                            {'label': ' 固定金额', 'value': 'fixed_amount'},
                            {'label': ' 固定份额', 'value': 'fixed_shares'}
                        ],
                        value='fixed_amount', inline=True, style={'fontSize': '12px'}
                    ),
                ], style={'marginBottom': '8px'}),
                html.Div([
                    html.Label("每次投入:", style={'fontSize': '12px'}),
                    dcc.Input(
                        id='research-position-size',
                        type='text', value='10', debounce=True,
                        style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                    ),
                ], style={'marginBottom': '8px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '20px'}),

        # ========== 隐藏存储 ==========
        dcc.Store(id='research-params-store', data={}),

    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'border': '1px solid #e9ecef',
        'height': 'fit-content'
    })


def register_research_callbacks(app):
    """注册研究页回调"""

    # ===== 事件 → 市场联动 =====
    @app.callback(
        Output('research-market-selector', 'options'),
        Output('research-market-selector', 'value'),
        Input('research-event-selector', 'value'),
    )
    def update_research_markets(event_id):
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

    # ===== 系列切换：更新事件列表 =====
    @app.callback(
        Output('research-event-selector', 'options'),
        Output('research-event-selector', 'value'),
        Input('series-selector', 'value'),
        Input('url', 'pathname'),
    )
    def update_research_events_on_series_change(series, pathname):
        from dash import no_update
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
                r_end = int(target['range_end']) if target['range_end'] and not pd.isna(target['range_end']) else '∞'
                label = f"{row['slug']} (命中: {r_start}-{r_end})"
            else:
                label = row['slug']
            event_options.append({'label': label, 'value': row['id']})

        default_event = events_df.iloc[-1]['id'] if not events_df.empty else None
        return event_options, default_event

    # ===== 保存参数 =====
    @app.callback(
        Output('research-params-store', 'data'),
        Input('research-event-selector', 'value'),
        Input('research-market-selector', 'value'),
        Input('research-price-type', 'value'),
        Input('research-window-type', 'value'),
        Input('research-capacity', 'value'),
        Input('research-price-threshold', 'value'),
        Input('research-distance-threshold', 'value'),
        Input('research-inertia', 'value'),
        Input('research-momentum-enable', 'value'),
        Input('research-momentum-coef', 'value'),
        Input('research-initial-capital', 'value'),
        Input('research-position-mode', 'value'),
        Input('research-position-size', 'value'),
    )
    def save_research_params(event_id, market_id, price_type, window_type,
                             capacity, price_threshold, distance_threshold, inertia,
                             momentum_enable, momentum_coef,
                             initial_capital, position_mode, position_size):
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
            'signal_mode': 'start',
            'initial_capital': int(initial_capital) if initial_capital else 100,
            'position_mode': position_mode or 'fixed_amount',
            'position_size': float(position_size) if position_size else 10,
            'backtest_range': 'full',
        }