"""
数据分析中心 - 页面布局
"""

from dash import html, dcc

from src.dash_app.pages.insights.explorer import render_explorer_section


def layout():
    return html.Div([
        # ---- 页面标题 ----
        html.Div([
            html.H2("📊 数据分析中心", style={'marginBottom': 2}),
            html.P("历史事件回顾、推文热度图谱与市场命中模式分析",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 20}),

        # ---- KPI 指标卡 ----
        html.Div([
            html.Strong("📊 核心指标含义："),
            html.Span("总事件 = 所有已结束的事件数；总推文 = 覆盖时间内的推文总量；",
                      style={'marginLeft': '10px'}),
            html.Span("命中市场 = 最终价格 > 0.99 的子市场数；最热区间 = 历史上命中次数最多的推文区间。",
                      style={'marginLeft': '5px'}),
        ], style={'padding': '8px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '4px', 'marginBottom': '10px'}),
        html.Div(id='insights-kpi-cards', style={'marginBottom': 20}),

        # ---- 移动平均数值卡 ----
        html.Div([
            html.H4("📈 推文移动平均值", style={'marginBottom': 10}),
            html.Div(id='insights-ma-cards', style={'marginBottom': 15}),
        ]),

        # ---- 主图区：命中市场热力图 ----
        html.Div([
            html.H4("🎯 事件-区间命中热力图", style={'marginBottom': 10}),
            html.P("横轴为事件（按时间排序），纵轴为推文区间，红色表示命中，灰色表示未命中",
                   style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
            dcc.Graph(id='insights-hit-heatmap', style={'height': '500px'}),
            html.Div([
                html.Strong("📖 如何阅读："),
                html.Span("每一行代表一个推文区间（如 180-199），每一列代表一个历史事件。红色格子表示该区间的最终价格 > 0.99（即“命中”），灰色表示未命中。",
                          style={'color': '#495057', 'fontSize': '12px'}),
                html.Br(),
                html.Strong("💡 统计意义："),
                html.Span("热力图可以直观看出哪些区间更容易“达成”，以及不同事件之间的一致性。颜色越集中，说明该区间预测稳定性越高。",
                          style={'color': '#495057', 'fontSize': '12px'})
            ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
        ], style={'marginBottom': 30}),

        # ---- 推文分析 ----
        html.Div([
            html.H4("🐦 推文全量分析", style={'marginBottom': 10}),
            html.Div([
                html.Label("时间范围:", style={'fontWeight': 'bold'}),
                dcc.Dropdown(
                    id='insights-time-range',
                    options=[
                        {'label': '近7天', 'value': 7},
                        {'label': '近30天', 'value': 30},
                        {'label': '近90天', 'value': 90},
                        {'label': '全部', 'value': 'all'},
                    ],
                    value='all',
                    style={'width': '200px', 'display': 'inline-block', 'marginLeft': '10px'}
                ),
            ], style={'marginBottom': 15}),
            html.Div([
                dcc.Graph(id='insights-tweet-timeline', style={'height': '350px'}),
                html.Div([
                    html.Strong("📖 如何阅读："),
                    html.Span("蓝色折线表示每小时实际推文数，虚线为 7 日移动平均线，用于平滑短期波动。",
                              style={'color': '#495057', 'fontSize': '12px'}),
                    html.Br(),
                    html.Strong("💡 统计意义："),
                    html.Span("趋势向上说明推文热度在上升，向下则反之。移动平均线可以揭示整体趋势方向。",
                              style={'color': '#495057', 'fontSize': '12px'})
                ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
            ], style={'marginBottom': 15}),
            html.Div([
                dcc.Graph(id='insights-tweet-heatmap', style={'height': '300px'}),
                html.Div([
                    html.Strong("📖 如何阅读："),
                    html.Span("横轴为 UTC 时间（0-23 时），纵轴为星期几。颜色越深表示该时段平均推文数越多。",
                              style={'color': '#495057', 'fontSize': '12px'}),
                    html.Br(),
                    html.Strong("💡 统计意义："),
                    html.Span("可以识别推文的活跃时段和周期规律，帮助优化策略的时间窗口。",
                              style={'color': '#495057', 'fontSize': '12px'})
                ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
            ]),
            html.Div([
                html.H5("📊 24小时平均推文分布", style={'marginTop': 20, 'marginBottom': 10}),
                dcc.Graph(id='insights-hourly-distribution', style={'height': '250px'}),
                html.Div([
                    html.Strong("📖 如何阅读："),
                    html.Span("横轴为 UTC 小时（0-23），纵轴为该小时的平均推文数（所有日期平均）。",
                              style={'color': '#495057', 'fontSize': '12px'}),
                    html.Br(),
                    html.Strong("💡 统计意义："),
                    html.Span("可以直观看出一天中推文活跃的高峰和低谷时段，辅助确定最佳交易时间窗口。",
                              style={'color': '#495057', 'fontSize': '12px'})
                ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
            ])
        ], style={'marginBottom': 30}),

        # ---- 命中区间分布 + 相关性 ----
        html.Div([
            html.Div([
                html.H4("📊 命中区间分布", style={'marginBottom': 10}),
                dcc.Graph(id='insights-histogram', style={'height': '300px'}),
                html.Div([
                    html.Strong("📖 如何阅读："),
                    html.Span("每个柱子代表一个推文区间，高度表示该区间在历史上被命中的次数。",
                              style={'color': '#495057', 'fontSize': '12px'}),
                    html.Br(),
                    html.Strong("💡 统计意义："),
                    html.Span("柱子越高说明该区间“达成”的概率越大，可以优先跟踪这些区间。",
                              style={'color': '#495057', 'fontSize': '12px'})
                ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
            ], className='insights-half', style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            html.Div([
                html.H4("📈 价格 vs 推文相关性", style={'marginBottom': 10}),
                dcc.Graph(id='insights-correlation', style={'height': '300px'}),
                html.Div([
                    html.Strong("📖 如何阅读："),
                    html.Span("每个点代表一个小时的交易数据，横轴为推文数，纵轴为对应小时的价格。左上角显示皮尔逊相关系数（越接近 1 正相关越强，-1 负相关越强）。",
                              style={'color': '#495057', 'fontSize': '12px'}),
                    html.Br(),
                    html.Strong("💡 统计意义："),
                    html.Span("如果相关性显著为正，说明推文增多时价格倾向于上涨，可作为策略参考。",
                              style={'color': '#495057', 'fontSize': '12px'})
                ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
            ], className='insights-half', style={'width': '48%', 'display': 'inline-block', 'float': 'right', 'verticalAlign': 'top'})
        ], style={'marginBottom': 20}),

        # ---- 各区间平均存活时长 ----
        html.Div([
            html.H4("⏱️ 各区间平均存活时长", style={'marginBottom': 10}),
            html.P("每个推文区间从事件开始到最终结算的平均时长（小时），柱子上显示该区间的样本数量",
                   style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
            dcc.Graph(id='insights-survival-chart', style={'height': '300px'}),
            html.Div([
                html.Strong("📖 如何阅读："),
                html.Span("每个区间代表一个推文区间，柱子高度表示该区间内所有市场从事件开始到停止价格更新的平均时长（小时）。柱子上显示该区间的市场数量。",
                          style={'color': '#495057', 'fontSize': '12px'}),
                html.Br(),
                html.Strong("💡 统计意义："),
                html.Span("存活时长反映了该区间市场活跃期的长短。存活时长长的区间可能价格波动持续较久，适合长线策略；存活时长短的区间可能价格波动短暂，适合短线操作。",
                          style={'color': '#495057', 'fontSize': '12px'})
            ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '8px'})
        ], style={'marginBottom': 20}),

        # ---- 推文探索器 ----
        render_explorer_section(),

        dcc.Store(id='insights-store', data={}),
    ], style={'padding': '0 20px'})