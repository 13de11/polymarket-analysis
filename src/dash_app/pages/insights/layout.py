"""
数据分析中心 - 页面布局

T2：Tab 内容内嵌为 dcc.Tab children，Dash 原生管显隐，
    不再需要 switch_insights_tab style-toggle 回调。
"""

from dash import html, dcc

from src.dash_app.utils.stats_loader import HIT_THRESHOLD
from src.dash_app.pages.insights.explorer import render_explorer_section
from src.dash_app.pages.insights._blocks import info_block


def layout():
    return html.Div([
        # ---- 页面标题 ----
        html.Div([
            html.H2("📊 数据分析中心", style={'marginBottom': 2}),
            html.P("历史事件回顾、推文热度图谱与市场命中模式分析",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 20}),

        # ---- Tab 切换（内容内嵌，Dash 原生显隐） ----
        dcc.Tabs(
            id='insights-tabs',
            value='overview',
            children=[
                # ============ Tab 1：总览 ============
                dcc.Tab(label='📊 总览', value='overview', children=[
                    # ---- 第一步：数据窗口选择 ----
                    html.Div([
                        html.Div([
                            html.Label("数据窗口：", style={'fontWeight': 'bold',
                                                            'marginRight': '8px'}),
                            dcc.Dropdown(
                                id='insights-window',
                                options=[
                                    {'label': '近 30 天', 'value': 30},
                                    {'label': '近 45 天', 'value': 45},
                                    {'label': '近 60 天', 'value': 60},
                                    {'label': '近 90 天', 'value': 90},
                                ],
                                value=30,
                                clearable=False,
                                style={'width': '160px'}
                            ),
                        ], style={'display': 'flex', 'alignItems': 'center'}),
                        html.Span("选定窗口后，下方所有指标与图表仅统计该窗口内已结束的事件。",
                                  className='hint', style={'marginTop': '6px'}),
                    ], style={'marginBottom': 15}),

                    html.Div([
                        html.Strong("📊 指标说明："),
                        html.Span("已结束事件 = 窗口内结算完成且价格数据已同步到结算时刻的事件（每个事件恰有一个命中区间）；",
                                  style={'marginLeft': '10px'}),
                        html.Span(f"总推文量 = 各事件统计区间（开始→结算）的推文合计；命中判定 = 结算时刻价格 > {HIT_THRESHOLD}；",
                                  style={'marginLeft': '5px'}),
                        html.Span("最近事件三项 = 窗口内最近一个已结束事件的推文表现。鼠标悬停各卡片名称可查看单项解释。",
                                  style={'marginLeft': '5px'}),
                    ], style={'padding': '8px 12px', 'backgroundColor': '#f8f9fa', 'borderRadius': '4px', 'marginBottom': '10px'}),
                    html.Div(id='insights-kpi-cards', style={'marginBottom': 20}),

                    html.Div([
                        html.H4("🎯 各区间命中次数", style={'marginBottom': 10}),
                        html.P("窗口内每个推文区间的累计命中次数，用于快速定位高概率区间",
                               style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
                        dcc.Graph(id='insights-range-hit-bar', style={'height': '320px'}),
                        info_block(
                            how_to_read=f"每根柱子代表一个推文区间（如 105-129），高度为窗口内该区间命中（最终存在价格 > {HIT_THRESHOLD} 的小时）的市场数量，柱顶标注具体次数。",
                            meaning="柱子越高说明该区间越容易被命中。结合窗口切换可以看出：高概率区间在不同时间跨度下是否稳定，若 30 天与 90 天的高柱一致，说明区间偏好长期稳定。",
                        )
                    ], style={'marginBottom': 30}),

                    html.Div([
                        html.H4("🗺 事件-区间命中热力图", style={'marginBottom': 10}),
                        html.P("横轴为事件（按时间排序），纵轴为推文区间，红色表示命中，灰色表示未命中",
                               style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
                        dcc.Graph(id='insights-hit-heatmap', style={'height': '500px'}),
                        info_block(
                            how_to_read=f"每一行代表一个推文区间（如 180-199），每一列代表一个历史事件。红色格子表示该区间的最终价格 > {HIT_THRESHOLD}（即“命中”），灰色表示未命中。",
                            meaning="热力图可以直观看出哪些区间更容易“达成”，以及不同事件之间的一致性。颜色越集中，说明该区间预测稳定性越高。",
                        )
                    ], style={'marginBottom': 30}),
                ]),

                # ============ Tab 2：推文分析 ============
                dcc.Tab(label='🐦 推文分析', value='tweets', children=[
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
                        info_block(
                            how_to_read="蓝色折线表示每小时实际推文数，虚线为 7 日移动平均线，用于平滑短期波动。",
                            meaning="趋势向上说明推文热度在上升，向下则反之。移动平均线可以揭示整体趋势方向。",
                        )
                    ], style={'marginBottom': 15}),

                    html.Div([
                        dcc.Graph(id='insights-tweet-heatmap', style={'height': '300px'}),
                        info_block(
                            how_to_read="横轴为 UTC 时间（0-23 时），纵轴为星期几。颜色越深表示该时段平均推文数越多。",
                            meaning="可以识别推文的活跃时段和周期规律，帮助优化策略的时间窗口。",
                        )
                    ]),

                    html.Div([
                        html.H5("📊 24小时平均推文分布", style={'marginTop': 20, 'marginBottom': 10}),
                        dcc.Graph(id='insights-hourly-distribution', style={'height': '250px'}),
                        info_block(
                            how_to_read="横轴为 UTC 小时（0-23），纵轴为该小时的平均推文数（所有日期平均）。",
                            meaning="可以直观看出一天中推文活跃的高峰和低谷时段，辅助确定最佳交易时间窗口。",
                        )
                    ])
                ]),

                # ============ Tab 3：命中与相关性 ============
                dcc.Tab(label='🎯 命中与相关性', value='hits', children=[
                    html.Div([
                        html.H4("📊 命中区间分布", style={'marginBottom': 10}),
                        dcc.Graph(id='insights-histogram', style={'height': '300px'}),
                        info_block(
                            how_to_read="每个柱子代表一个推文区间，高度表示该区间在历史上被命中的次数。",
                            meaning="柱子越高说明该区间“达成”的概率越大，可以优先跟踪这些区间。",
                        )
                    ], style={'marginBottom': 20}),

                    html.Div([
                        html.H4("📈 价格 vs 推文相关性", style={'marginBottom': 10}),
                        dcc.Graph(id='insights-correlation', style={'height': '300px'}),
                        info_block(
                            how_to_read="每个点代表一个小时的交易数据，横轴为推文数，纵轴为对应小时的价格。左上角显示皮尔逊相关系数（越接近 1 正相关越强，-1 负相关越强）。",
                            meaning="如果相关性显著为正，说明推文增多时价格倾向于上涨，可作为策略参考。",
                        )
                    ], style={'marginBottom': 20}),

                    html.Div([
                        html.H4("⏱️ 各区间平均存活时长", style={'marginBottom': 10}),
                        html.P("每个推文区间从事件开始到最终结算的平均时长（小时），柱子上显示该区间的样本数量",
                               style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
                        dcc.Graph(id='insights-survival-chart', style={'height': '300px'}),
                        info_block(
                            how_to_read="每个区间代表一个推文区间，柱子高度表示该区间内所有市场从事件开始到停止价格更新的平均时长（小时）。柱子上显示该区间的市场数量。",
                            meaning="存活时长反映了该区间市场活跃期的长短。存活时长长的区间可能价格波动持续较久，适合长线策略；存活时长短的区间可能价格波动短暂，适合短线操作。",
                        )
                    ]),
                ]),

                # ============ Tab 4：推文探索器 ============
                dcc.Tab(label='🔍 推文探索器', value='explorer', children=[
                    render_explorer_section(),
                ]),
            ],
            style={'marginBottom': '15px'}
        ),
    ], style={'padding': '0 20px'})
