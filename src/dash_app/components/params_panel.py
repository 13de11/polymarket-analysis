"""
参数配置面板组件
- 标的选择：事件、市场、价格类型、窗口
- 策略参数：容量、价格阈值、距离阈值、惯性、动量修正、信号模式
- 回测设置：初始资金、开仓模式、每次投入、回测区间
- 信号确认次数（新增）
- 「运行回测」按钮
"""

import dash
from dash import html, dcc, Input, Output, State, callback
import pandas as pd
import numpy as np

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_time_range,
)


def create_params_panel(default_event_id=None):
    """创建完整的参数配置面板"""
    events_df = get_elon_tweet_events()
    event_options = []
    for _, row in events_df.iterrows():
        target = get_target_market(row['id'])
        if target:
            r_start = int(target['range_start'])
            r_end = int(target['range_end']) if target['range_end'] and not pd.isna(target['range_end']) else '∞'
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})

    default_event = default_event_id or (events_df.iloc[-1]['id'] if not events_df.empty else None)

    return html.Div([

        # ========== 标题 ==========
        html.Div([
            html.H4("📊 回测参数配置", style={'margin': 0, 'color': '#2c3e50'}),
            html.P("配置参数后信号预览实时更新，点击「运行回测」查看绩效",
                   style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '4px 0 0 0'})
        ], style={'borderBottom': '2px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '15px'}),

        # ========== 分组1：数据选择 ==========
        html.Details([
            html.Summary("📊 数据选择", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("事件:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='backtest-event-selector',
                        options=event_options,
                        value=default_event,
                        placeholder='请选择事件',
                        style={'width': '100%', 'marginTop': '3px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("目标市场:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='backtest-market-selector',
                        options=[],
                        placeholder='请先选择事件',
                        style={'width': '100%', 'marginTop': '3px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("价格类型:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.RadioItems(
                        id='backtest-price-type',
                        options=[
                            {'label': ' 最新价 (Last)', 'value': 'price_last'},
                            {'label': ' 均价 (Avg)', 'value': 'price_avg'}
                        ],
                        value='price_last',
                        inline=True,
                        style={'marginTop': '4px', 'fontSize': '13px'}
                    ),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("推文速率窗口:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.RadioItems(
                        id='backtest-window-type',
                        options=[
                            {'label': ' 7天', 'value': '7d'},
                            {'label': ' gamestart至今', 'value': 'gamestart'},
                            {'label': ' 开盘至今', 'value': 'open'}
                        ],
                        value='7d',
                        inline=True,
                        style={'marginTop': '4px', 'fontSize': '12px'}
                    ),
                    html.Div([
                        dcc.Input(
                            id='backtest-window-custom',
                            type='number',
                            placeholder='自定义小时数',
                            style={'width': '60%', 'display': 'inline-block', 'marginTop': '4px'}
                        ),
                        html.Span(" 小时", style={'fontSize': '12px', 'color': '#7f8c8d', 'marginLeft': '4px'})
                    ], style={'marginTop': '4px'}),
                ], style={'marginBottom': '0px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '12px'}),

        # ========== 分组2：策略参数 ==========
        html.Details([
            html.Summary("🧠 策略参数", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("容差 (Tolerance):", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-capacity',
                            min=0,
                            max=5,
                            step=0.5,
                            value=0.5,
                            marks={i: str(i) for i in range(0, 6, 1)},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'marginBottom': '10px'}),
                ]),
                html.Div([
                    html.Div([
                        html.Label("价格变动阈值:", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-price-threshold',
                            min=0.001,
                            max=0.02,
                            step=0.001,
                            value=0.005,
                            marks={0.005: '0.005', 0.01: '0.01', 0.015: '0.015', 0.02: '0.02'},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'marginBottom': '10px'}),
                ]),
                html.Div([
                    html.Div([
                        html.Label("距离变动阈值:", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-distance-threshold',
                            min=0.5,
                            max=4.0,
                            step=0.1,
                            value=1.5,
                            marks={0.5: '0.5', 1.0: '1.0', 2.0: '2.0', 3.0: '3.0', 4.0: '4.0'},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'marginBottom': '10px'}),
                ]),
                html.Div([
                    html.Div([
                        html.Label("惯性重置 (小时):", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-inertia',
                            min=1,
                            max=12,
                            step=1,
                            value=6,
                            marks={i: str(i) for i in range(1, 13, 2)},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'marginBottom': '10px'}),
                ]),
                html.Div([
                    html.Div([
                        html.Label("动量修正:", style={'fontSize': '12px'}),
                        dcc.RadioItems(
                            id='backtest-momentum-enable',
                            options=[
                                {'label': ' 开启', 'value': True},
                                {'label': ' 关闭', 'value': False}
                            ],
                            value=True,
                            inline=True,
                            style={'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("动量系数:", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-momentum-coef',
                            min=0.01,
                            max=0.30,
                            step=0.01,
                            value=0.10,
                            marks={0.01: '0.01', 0.10: '0.10', 0.20: '0.20', 0.30: '0.30'},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '10px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '12px'}),

        # ========== 分组3：信号展示 ==========
        html.Details([
            html.Summary("🎨 信号展示", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("信号模式:", style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id='backtest-signal-mode',
                            options=[
                                {'label': '首尾 (显示起点和终点)', 'value': 'full'},
                                {'label': '只首 (仅起点)', 'value': 'start'},
                                {'label': '只尾 (仅终点)', 'value': 'end'}
                            ],
                            value='start',
                            style={'width': '100%', 'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("信号确认次数:", style={'fontSize': '12px'}),
                        dcc.Slider(
                            id='backtest-signal-confirm',
                            min=1,
                            max=5,
                            step=1,
                            value=1,
                            marks={i: str(i) for i in range(1, 6)},
                            tooltip={'placement': 'bottom', 'always_visible': False}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '0px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '12px'}),

        # ========== 分组4：回测执行 ==========
        html.Details([
            html.Summary("💰 回测执行", style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Div([
                        html.Label("初始资金:", style={'fontSize': '12px'}),
                        dcc.Input(
                            id='backtest-initial-capital',
                            type='number',
                            value=100,
                            step=10,
                            min=1,
                            style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("开仓模式:", style={'fontSize': '12px'}),
                        dcc.RadioItems(
                            id='backtest-position-mode',
                            options=[
                                {'label': ' 固定金额', 'value': 'fixed_amount'},
                                {'label': ' 固定份额', 'value': 'fixed_shares'}
                            ],
                            value='fixed_amount',
                            inline=True,
                            style={'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '8px'}),
                html.Div([
                    html.Div([
                        html.Label("每次投入:", style={'fontSize': '12px'}),
                        dcc.Input(
                            id='backtest-position-size',
                            type='number',
                            value=10,
                            step=1,
                            min=0.1,
                            style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("回测区间:", style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id='backtest-range',
                            options=[
                                {'label': '完整周期', 'value': 'full'},
                                {'label': '开盘 → gamestart', 'value': 'pre'},
                                {'label': 'gamestart → 结束', 'value': 'post'},
                                {'label': '自定义', 'value': 'custom'}
                            ],
                            value='full',
                            style={'width': '100%', 'fontSize': '12px'}
                        ),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '0px'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], style={'marginBottom': '20px'}),

        # ========== 操作按钮 ==========
        html.Div([
            html.Button(
                '🚀 更新信号预览',
                id='backtest-preview-btn',
                n_clicks=0,
                style={
                    'width': '48%',
                    'padding': '10px',
                    'backgroundColor': '#3498db',
                    'color': 'white',
                    'border': 'none',
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'cursor': 'pointer',
                    'marginRight': '4%'
                }
            ),
            html.Button(
                '📊 运行回测',
                id='backtest-run-btn',
                n_clicks=0,
                style={
                    'width': '48%',
                    'padding': '10px',
                    'backgroundColor': '#28a745',
                    'color': 'white',
                    'border': 'none',
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'cursor': 'pointer'
                }
            ),
        ], style={'display': 'flex'}),

        # ========== 隐藏存储 ==========
        dcc.Store(id='backtest-params-store', data={}),
        dcc.Store(id='backtest-market-options-store', data=[]),

    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'border': '1px solid #e9ecef',
        'height': 'fit-content'
    })


def register_params_callbacks(app):
    """注册所有参数面板相关的回调"""

    # ===== 事件 → 市场联动 =====
    @app.callback(
        Output('backtest-market-selector', 'options'),
        Output('backtest-market-selector', 'value'),
        Input('backtest-event-selector', 'value')
    )
    def update_markets(event_id):
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

    # ===== 保存参数 =====
    @app.callback(
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
        State('backtest-signal-confirm', 'value'),
        State('backtest-initial-capital', 'value'),
        State('backtest-position-mode', 'value'),
        State('backtest-position-size', 'value'),
        State('backtest-range', 'value'),
    )
    def save_params(n_clicks_run, n_clicks_preview, event_id, market_id,
                    price_type, window_type, window_custom,
                    capacity, price_threshold, distance_threshold, inertia,
                    momentum_enable, momentum_coef, signal_mode, signal_confirm,
                    initial_capital, position_mode, position_size, backtest_range):
        trigger = dash.callback_context.triggered[0]['prop_id'] if dash.callback_context.triggered else ''
        if not trigger or (not n_clicks_run and not n_clicks_preview):
            return {}

        if window_type == '7d':
            window_hours = 168
        elif window_type == 'gamestart':
            window_hours = 'gamestart'
        elif window_type == 'open':
            window_hours = 'open'
        else:
            window_hours = int(window_custom) if window_custom else 168

        params = {
            'event_id': event_id,
            'market_id': market_id,
            'price_type': price_type or 'price_last',
            'window_type': window_type,
            'window_hours': window_hours,
            'capacity': capacity or 0,
            'price_threshold': price_threshold or 0.005,
            'distance_threshold': distance_threshold or 1.5,
            'inertia': inertia or 6,
            'momentum_enable': momentum_enable,
            'momentum_coef': momentum_coef or 0.10,
            'signal_mode': signal_mode or 'start',
            'signal_confirm': signal_confirm or 1,
            'initial_capital': initial_capital or 100,
            'position_mode': position_mode or 'fixed_amount',
            'position_size': position_size or 10,
            'backtest_range': backtest_range or 'full',
        }
        return params