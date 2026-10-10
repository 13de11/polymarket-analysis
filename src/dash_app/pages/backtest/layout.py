# src/dash_app/pages/backtest/layout.py
"""
预测回测系统 - 页面布局
"""

from dash import html, dcc

from src.dash_app.pages.backtest.params_panel import create_params_panel


def layout(global_params=None):
    return html.Div([

        html.Div([
            html.H2("📈 预测回测系统", style={'marginBottom': 2}),
            html.P("基于推文热度的方向预测与模拟交易回测",
                   style={'color': '#6c757d', 'fontSize': '14px',
                          'marginTop': 0}),
        ], style={'marginBottom': 15}),

        html.Details([
            html.Summary("📖 方向判断逻辑详解（点击展开）", style={
                'cursor': 'pointer', 'fontWeight': 'bold',
                'padding': '10px 15px', 'backgroundColor': '#e8f4fd',
                'borderRadius': '6px', 'border': '1px solid #b8d4e8',
                'fontSize': '14px',
            }),
            html.Div([
                html.H5("🎯 核心思路", style={'marginTop': '10px'}),
                html.P("用「推文热度」估算市场参与度，通过「估算总量距中位数的距离变化」推断价格方向。"),
                html.P("直觉：如果推文速度在加快，说明市场热度上升，目标区间更可能被触及，价格倾向上涨。"),

                html.H5("📐 五步判断流程", style={'marginTop': '15px'}),
                html.Ol([
                    html.Li([html.Strong("估算总量"),
                             html.Span(" = 平均推文速率 × 剩余小时数")]),
                    html.Li([html.Strong("距离"),
                             html.Span(" = |估算总量 − 市场中位数|")]),
                    html.Li([html.Strong("容差过滤"),
                             html.Span("：距离 ≤ 容差 → 直接判定为「看平」（→）")]),
                    html.Li([html.Strong("噪音过滤"),
                             html.Span("：距离变动 ≤ 距离阈值 且 价格变动 ≤ 价格阈值 → 不触发新信号")]),
                    html.Li([html.Strong("方向判断"),
                             html.Span("：距离变小 → ↑；变大 → ↓；不变 → →")]),
                ]),

                html.H5("🛡️ 惯性保护", style={'marginTop': '15px'}),
                html.P("连续 ≥ 惯性小时 无有效信号 → 强制输出 →（看平），避免长期持有单一方向。"),

                html.H5("⚡ 动量修正", style={'marginTop': '15px'}),
                html.P("根据最近 6 小时推文速率变化调整估算总量。调整系数 = 1 + 动量系数 × rateChange，限制在 0.8~1.2 倍。"),

                html.H5("🎨 信号模式（仅影响图表显示）", style={'marginTop': '15px'}),
                html.Ul([
                    html.Li("full：显示每个连续段的起点和终点"),
                    html.Li("start：只显示起点（推荐）"),
                    html.Li("end：只显示终点"),
                ]),

                html.H5("📊 方向准确率", style={'marginTop': '15px'}),
                html.P("信号发出 → 到下一个反向信号出现，看这段区间内价格是否朝预测方向变化。"),
            ], style={'padding': '15px 20px', 'backgroundColor': '#f8f9fa',
                      'borderRadius': '6px'}),
        ], style={'marginBottom': '15px'}),

        html.Div([
            html.Div([
                create_params_panel(global_params=global_params)
            ], className='backtest-left', style={
                'width': '28%', 'display': 'inline-block',
                'verticalAlign': 'top', 'paddingRight': '20px',
                'boxSizing': 'border-box',
            }),
            html.Div([
                html.Div([
                    html.H4("📊 回测结果",
                            style={'margin': 0, 'color': '#2c3e50'}),
                    html.P(id='backtest-status-text',
                           style={'fontSize': '12px', 'color': '#7f8c8d',
                                  'margin': '4px 0 0 0'}),
                ], style={'borderBottom': '2px solid #3498db',
                          'paddingBottom': '10px',
                          'marginBottom': '15px'}),
                dcc.Tabs(
                    id='backtest-tabs', value='preview',
                    children=[
                        dcc.Tab(label='🔍 信号预览', value='preview'),
                        dcc.Tab(label='📊 绩效概览', value='overview'),
                        dcc.Tab(label='📋 交易明细', value='trades'),
                        dcc.Tab(label='📈 策略评估', value='evaluation'),
                    ],
                    style={'marginBottom': '15px'},
                ),
                dcc.Loading(
                    id='loading-backtest', type='default', color='#3498db',
                    children=[html.Div(id='backtest-tab-content',
                                       style={'minHeight': '400px'})],
                ),
                dcc.Store(id='backtest-result-store', data={}),
            ], className='backtest-right', style={
                'width': '70%', 'display': 'inline-block',
                'verticalAlign': 'top', 'boxSizing': 'border-box',
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),

        html.Details([
            html.Summary("📖 方向判断与回测规则详解",
                         style={'cursor': 'pointer', 'fontWeight': 'bold',
                                'padding': '10px 0'}),
            html.Div([
                html.H5("🎯 方向判断逻辑",
                        style={'marginTop': '5px', 'color': '#2c3e50'}),
                html.Ol([
                    html.Li([html.Strong("估算总量 = 平均推文速率 × 剩余小时数"),
                             html.Br(),
                             html.Span("窗口决定速率：7天=最近168h滚动平均 | gamestart/开盘=从起点累计平均 | 自定义=最近N小时滚动平均",
                                       style={'fontSize': '13px',
                                              'color': '#495057'})]),
                    html.Li([html.Strong("距离 = |估算总量 − 市场中位数|")]),
                    html.Li([html.Strong("容差过滤：距离 ≤ 容差 → 看平（→）")]),
                    html.Li([html.Strong("噪音过滤：距离变动 ≤ 距离阈值 且 价格变动 ≤ 价格阈值 → 不触发新信号")]),
                    html.Li([html.Strong("方向判断：距离变小 → ↑；变大 → ↓；不变 → →")]),
                ], style={'paddingLeft': '20px'}),
                html.H5("💰 回测规则",
                        style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.Ul([
                    html.Li("开仓：预测方向 ↑ 且当前空仓 → 以当前价格买入"),
                    html.Li("平仓：预测方向 ↓ 且当前持仓 → 以当前价格卖出"),
                    html.Li("→ 信号：不触发任何交易"),
                    html.Li("回测结束强制平仓；仅做多"),
                ], style={'fontSize': '13px', 'color': '#495057'}),
            ], style={'padding': '15px 20px', 'backgroundColor': '#f8f9fa',
                      'borderRadius': '6px'}),
        ], style={'marginTop': '20px'}),

    ], style={'padding': '10px 20px'})