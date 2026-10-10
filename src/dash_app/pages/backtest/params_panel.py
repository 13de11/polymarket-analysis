# src/dash_app/pages/backtest/params_panel.py
"""
参数配置面板

global_params 不为 None 时，用它初始化各组件默认值。
"""

from dash import html, dcc
import pandas as pd

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
)
from src.dash_app.pages.shared.params_panel import (
    create_schema_section,
)


def create_params_panel(default_event_id=None, series='7d',
                        global_params=None):
    events_df = get_elon_tweet_events(series)
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

    # 默认事件优先级：global_params.event_id > default_event_id > 最后一个
    default_event = None
    if global_params and global_params.get('event_id') in event_ids:
        default_event = global_params['event_id']
    elif default_event_id:
        default_event = default_event_id
    elif not events_df.empty:
        default_event = events_df.iloc[-1]['id']

    # 构造 overrides
    overrides = {}
    if global_params:
        for k, v in global_params.items():
            if v is not None:
                overrides[k] = v

    # window_custom_hours 手写输入框的初始值
    custom_hours = ''
    if global_params and global_params.get('window_custom_hours') is not None:
        custom_hours = global_params['window_custom_hours']

    # backtest_range_custom 手写 RangeSlider 的初始值
    range_custom = [0, 100]
    if global_params and global_params.get('backtest_range_custom'):
        range_custom = global_params['backtest_range_custom']

    return html.Div([

        html.Div([
            html.H4("📊 回测参数配置",
                    style={'margin': 0, 'color': '#2c3e50'}),
            html.P("按顺序配置四步参数，点击「运行回测」查看结果",
                   style={'fontSize': '12px', 'color': '#7f8c8d',
                          'margin': '4px 0 0 0'}),
        ], style={'borderBottom': '2px solid #3498db',
                  'paddingBottom': '10px', 'marginBottom': '15px'}),

        # 第一步：数据选择
        html.Details([
            html.Summary("📊 数据选择",
                         style={'fontWeight': 'bold', 'fontSize': '14px',
                                'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("事件:",
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='backtest-event-selector',
                        options=event_options,
                        value=default_event,
                        placeholder='请选择事件',
                        style={'width': '100%', 'marginTop': '3px'},
                    ),
                    html.Div("要回测的历史事件",
                             style={'fontSize': '11px',
                                    'color': '#7f8c8d',
                                    'marginTop': '2px'}),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("目标市场:",
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='backtest-market-selector',
                        options=[],
                        placeholder='请先选择事件',
                        style={'width': '100%', 'marginTop': '3px'},
                    ),
                    html.Div("具体推文区间市场，决定中位数锚点",
                             style={'fontSize': '11px',
                                    'color': '#7f8c8d',
                                    'marginTop': '2px'}),
                ], style={'marginBottom': '0'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], open=True, style={'marginBottom': '12px'}),

        # 第二步：观察维度
        html.Details([
            html.Summary("🎚️ 观察维度",
                         style={'fontWeight': 'bold', 'fontSize': '14px',
                                'cursor': 'pointer'}),
            create_schema_section(
                'backtest', 'dimension',
                overrides=overrides,
                extra_children=[
                    html.Div([
                        dcc.Input(
                            id='backtest-window-custom',
                            type='text',
                            value=custom_hours,
                            placeholder='自定义小时数',
                            style={'width': '60%',
                                   'display': 'inline-block',
                                   'marginTop': '4px'},
                        ),
                        html.Span(" 小时",
                                  style={'fontSize': '12px',
                                         'color': '#7f8c8d',
                                         'marginLeft': '4px'}),
                    ], id='backtest-window-custom-container',
                       style={'marginTop': '4px', 'display': 'none'}),
                ],
            ),
        ], style={'marginBottom': '12px'}),

        # 第三步：信号参数
        html.Details([
            html.Summary("🧠 信号参数",
                         style={'fontWeight': 'bold', 'fontSize': '14px',
                                'cursor': 'pointer'}),
            create_schema_section('backtest', 'signal',
                                  overrides=overrides),
        ], style={'marginBottom': '12px'}),

        # 第四步：评价假设
        html.Details([
            html.Summary("💰 评价假设",
                         style={'fontWeight': 'bold', 'fontSize': '14px',
                                'cursor': 'pointer'}),
            create_schema_section(
                'backtest', 'execution',
                overrides=overrides,
                extra_children=[
                    html.Div([
                        dcc.RangeSlider(
                            id='backtest-range-custom',
                            min=0, max=100, step=5,
                            value=range_custom,
                            marks={0: '0%', 25: '25%', 50: '50%',
                                   75: '75%', 100: '100%'},
                            tooltip={'placement': 'bottom',
                                     'always_visible': False},
                        ),
                        html.Div("按事件时长百分比选择回测时段",
                                 style={'fontSize': '11px',
                                        'color': '#7f8c8d',
                                        'marginTop': '2px'}),
                    ], id='backtest-range-custom-container',
                       style={'display': 'none', 'marginTop': '8px'}),
                ],
            ),
        ], style={'marginBottom': '20px'}),

        # 操作按钮
        html.Div([
            html.Button(
                '🔄 刷新信号预览',
                id='backtest-preview-btn',
                n_clicks=0,
                style={
                    'width': '48%', 'padding': '10px',
                    'backgroundColor': '#3498db', 'color': 'white',
                    'border': 'none', 'borderRadius': '6px',
                    'fontSize': '14px', 'fontWeight': 'bold',
                    'cursor': 'pointer', 'marginRight': '4%',
                },
            ),
            html.Button(
                '🚀 运行回测',
                id='backtest-run-btn',
                n_clicks=0,
                style={
                    'width': '48%', 'padding': '10px',
                    'backgroundColor': '#28a745', 'color': 'white',
                    'border': 'none', 'borderRadius': '6px',
                    'fontSize': '14px', 'fontWeight': 'bold',
                    'cursor': 'pointer',
                },
            ),
        ], style={'display': 'flex', 'marginBottom': '8px'}),
        html.Div("「刷新信号预览」只更新预览图；「运行回测」跑完整回测，"
                 "刷新绩效/交易/评估",
                 style={'fontSize': '11px', 'color': '#7f8c8d',
                        'textAlign': 'center'}),

    ], style={
        'backgroundColor': 'white',
        'padding': '15px',
        'borderRadius': '8px',
        'border': '1px solid #e9ecef',
        'height': 'fit-content',
    })