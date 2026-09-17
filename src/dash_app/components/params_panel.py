"""
参数配置面板组件
- 标的选择：事件、市场、价格类型、窗口
- 策略参数：容量、价格阈值、距离阈值、惯性、动量修正、信号模式
- 回测设置：初始资金、开仓模式、每次投入、回测区间
- 信号确认次数（新增）
- 「运行回测」按钮
"""

import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import pandas as pd

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_time_range,
    get_target_markets_batch,
)


def create_params_panel(default_event_id=None, series='7d'):
    """创建完整的参数配置面板"""
    events_df = get_elon_tweet_events(series)  # 传入 series
    event_ids = events_df['id'].tolist()
    targets_map = get_target_markets_batch(event_ids)   # ← 批量查

    event_options = []
    for _, row in events_df.iterrows():
        target = targets_map.get(row['id'])   # ← 从字典取
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
                    html.Div("要回测的历史事件（如 elon-musk-of-tweets-june-1-june-3）",
                             style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("目标市场:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='backtest-market-selector',
                        options=[],
                        placeholder='请先选择事件',
                        style={'width': '100%', 'marginTop': '3px'}
                    ),
                    html.Div("要回测的具体推文区间市场，决定中位数锚点",
                             style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                    html.Div("last=最新成交价 | avg=小时均价",
                        style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("推文速率窗口:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.RadioItems(
                        id='backtest-window-type',
                        options=[
                            {'label': ' 7天', 'value': '7d'},
                            {'label': ' gamestart至今', 'value': 'gamestart'},
                            {'label': ' 开盘至今', 'value': 'open'},
                            {'label': ' 自定义', 'value': 'custom'}
                        ],
                        value='7d',
                        inline=True,
                        style={'marginTop': '4px', 'fontSize': '12px'}
                    ),
                    html.Div([
                        dcc.Input(
                            id='backtest-window-custom',
                            type='text',
                            placeholder='自定义小时数',
                            debounce=True,
                            style={'width': '60%', 'display': 'inline-block', 'marginTop': '4px'}
                        ),
                        html.Span(" 小时", style={'fontSize': '12px', 'color': '#7f8c8d', 'marginLeft': '4px'})
                    ], id='backtest-window-custom-container', style={'marginTop': '4px', 'display': 'none'}),
                    html.Div(
                        "7天=最近168h滚动 | gamestart/开盘=从起点累计 | 自定义=最近N小时滚动",
                        style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '4px', 'marginBottom': '2px'}
                    ),
                    html.Div(
                        "窗口决定「平均推文速率」的计算方式，进而影响估算总量和方向判断",
                        style={'fontSize': '11px', 'color': '#95a5a6', 'marginBottom': '4px'}
                    ),
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
                        html.Div("距离 ≤ 容差 → 判定为「看平」（→）",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("价格变动 ≤ 阈值 → 视为噪音，不触发新信号",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("距离变动 ≤ 阈值 → 视为噪音，不触发新信号",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("连续无有效信号 ≥ 惯性小时 → 强制输出「看平」",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("根据近期推文速率变化调整估算总量，限制 0.8~1.2 倍",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("full=首尾 | start=只首 | end=只尾（仅影响图表显示）",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                    ], style={'marginBottom': '0px'}),
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
                            type='text',
                            value='100',
                            debounce=True,
                            style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                        ),
                        html.Div("回测起始资金（美元）",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
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
                        html.Div("固定金额=每次投入固定美元 | 固定份额=每次买入固定份数",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                    ], style={'display': 'inline-block', 'width': '45%'}),
                ], style={'marginBottom': '8px'}),
                html.Div([
                    html.Div([
                        html.Label("每次投入:", style={'fontSize': '12px'}),
                        dcc.Input(
                            id='backtest-position-size',
                            type='text',
                            value='10',
                            debounce=True,
                            style={'width': '100%', 'padding': '4px', 'fontSize': '12px'}
                        ),
                        html.Div("固定金额模式下=美元数；固定份额模式下=份数",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                    ], style={'display': 'inline-block', 'width': '45%', 'paddingRight': '5%'}),
                    html.Div([
                        html.Label("回测区间:", style={'fontSize': '12px'}),
                        dcc.Dropdown(
                            id='backtest-range',
                            options=[
                                {'label': '完整周期', 'value': 'full'},
                                {'label': '开盘 → gamestart', 'value': 'pre'},
                                {'label': 'gamestart → 结束', 'value': 'post'},
                                {'label': '自定义范围', 'value': 'custom'}
                            ],
                            value='full',
                            style={'width': '100%', 'fontSize': '12px'}
                        ),
                        html.Div("完整周期 / 开盘→gamestart / gamestart→结束",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                        html.Div([
                            dcc.RangeSlider(
                                id='backtest-range-custom',
                                min=0,
                                max=100,
                                step=5,
                                value=[0, 100],
                                marks={0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%'},
                                tooltip={'placement': 'bottom', 'always_visible': False}
                            ),
                            html.Div("按事件时长百分比选择回测时段（0%=事件开始，100%=事件结束）",
                                     style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                        ], id='backtest-range-custom-container', style={'display': 'none', 'marginTop': '8px'}),
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
    # ===== 回测区间切换：自定义滑块显示/隐藏 =====
    @app.callback(
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

    # ===== 事件 → 市场联动 =====
    @app.callback(
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

    # ===== 系列切换：更新事件列表 =====
    @app.callback(
        Output('backtest-event-selector', 'options'),
        Output('backtest-event-selector', 'value'),
        Input('series-selector', 'value'),
        Input('url', 'pathname'),
    )
    def update_backtest_events_on_series_change(series, pathname):
        """当系列切换时，重新生成事件列表"""
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
                r_end = int(target['range_end']) if target['range_end'] and not pd.isna(target['range_end']) else '∞'
                label = f"{row['slug']} (命中: {r_start}-{r_end})"
            else:
                label = row['slug']
            event_options.append({'label': label, 'value': row['id']})

        # 默认选最后一个
        default_event = events_df.iloc[-1]['id'] if not events_df.empty else None
        return event_options, default_event

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
                    initial_capital, position_mode, position_size, backtest_range, backtest_range_custom):
        trigger = dash.callback_context.triggered[0]['prop_id'] if dash.callback_context.triggered else ''
        if not trigger or (not n_clicks_run and not n_clicks_preview):
            return {}

        if window_type == '7d':
            window_mode = 'rolling'
            window_param = 168
            window_start = None
        elif window_type == 'gamestart':
            window_mode = 'expanding'
            window_param = None
            window_start = 'gamestart'
        elif window_type == 'open':
            window_mode = 'expanding'
            window_param = None
            window_start = 'open'
        else:  # custom
            window_mode = 'rolling'
            window_param = int(window_custom) if window_custom else 168
            window_start = None

        params = {
            'event_id': event_id,
            'market_id': market_id,
            'price_type': price_type or 'price_last',
            'window_type': window_type,
            'window_mode': window_mode,  # ← 新增
            'window_param': window_param,  # ← 新增
            'window_start': window_start,  # ← 新增
            'capacity': capacity or 0,
            'price_threshold': price_threshold or 0.005,
            'distance_threshold': distance_threshold or 1.5,
            'inertia': inertia or 6,
            'momentum_enable': momentum_enable,
            'momentum_coef': momentum_coef or 0.10,
            'signal_mode': signal_mode or 'start',
            'initial_capital': int(initial_capital) if initial_capital else 100,
            'position_mode': position_mode or 'fixed_amount',
            'position_size': float(position_size) if position_size else 10,
            'backtest_range': backtest_range or 'full',
            'backtest_range_custom': backtest_range_custom or [0, 100],
        }

        return params

    # ===== 窗口模式切换：自定义输入框显示/隐藏 =====
    @app.callback(
        Output('backtest-window-custom-container', 'style'),
        Input('backtest-window-type', 'value')
    )
    def toggle_custom_window(window_type):
        if window_type == 'custom':
            return {'marginTop': '4px'}
        return {'marginTop': '4px', 'display': 'none'}