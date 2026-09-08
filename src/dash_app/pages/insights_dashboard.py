"""
数据分析中心 (Data Insights Hub)
- KPI 指标卡
- 命中市场热力图
- 推文全量分析
- 命中区间分布
- 各区间平均存活时长
- 推文探索器（优化版）
"""

import dash
from dash import html, dcc, Input, Output, callback,dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.dash_app.utils.stats_loader import (
    get_overview_stats,
    get_hit_distribution,
    get_tweet_timeline,
    get_tweet_heatmap,
    get_correlation_data,
    get_histogram_data,
    get_event_timeline_events,
    get_ma_values,
    get_hourly_distribution,
    get_survival_by_range,
    get_tweet_matrix,
    get_event_time_range,
)


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
            html.Span("总事件 = 所有已结束的 elon-tweets 事件数；总推文 = 覆盖时间内的推文总量；",
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
                    html.Span("可以识别马斯克推文的活跃时段和周期规律，帮助优化策略的时间窗口。",
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
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
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
            ], style={'width': '48%', 'display': 'inline-block', 'float': 'right', 'verticalAlign': 'top'})
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
        html.Div([
            html.H4("🔍 推文探索器", style={'marginBottom': 10}),
            html.P("按时间范围或事件筛选，查看推文数量的日期-小时分布",
                   style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),

            # 筛选器
            html.Div([
                html.Div([
                    html.Label("筛选模式:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Dropdown(
                        id='tweet-explorer-mode',
                        options=[
                            {'label': '近7天', 'value': '7d'},
                            {'label': '近30天', 'value': '30d'},
                            {'label': '近90天', 'value': '90d'},
                            {'label': '事件', 'value': 'event'},
                            {'label': '自定义', 'value': 'custom'},
                        ],
                        value='7d',
                        style={'width': '150px', 'display': 'inline-block'}
                    ),
                ], style={'display': 'inline-block', 'marginRight': '15px'}),

                # 事件选择
                html.Div([
                    html.Label("事件:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Dropdown(
                        id='tweet-explorer-event',
                        options=[],
                        placeholder='选择事件',
                        style={'width': '250px', 'display': 'inline-block'}
                    ),
                ], id='tweet-explorer-event-container', style={'display': 'none'}),

                # 自定义日期
                html.Div([
                    html.Label("开始日期:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Input(
                        id='tweet-explorer-start-date',
                        type='date',
                        style={'width': '140px', 'display': 'inline-block', 'marginRight': '15px'}
                    ),
                    html.Label("结束日期:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                    dcc.Input(
                        id='tweet-explorer-end-date',
                        type='date',
                        style={'width': '140px', 'display': 'inline-block'}
                    ),
                ], id='tweet-explorer-date-container', style={'display': 'none'}),
            ], style={
                'padding': '12px 15px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '6px',
                'marginBottom': '15px',
                'display': 'flex',
                'flexWrap': 'wrap',
                'gap': '10px',
                'alignItems': 'center'
            }),

            # 统计摘要卡
            html.Div(id='tweet-explorer-stats', style={'marginBottom': '15px'}),

            # 表格容器
            html.Div(id='tweet-explorer-table', style={
                'overflowX': 'auto',
                'marginTop': '10px',
                'width': '100%',
                'minHeight': '300px',
                'border': '1px solid #dee2e6',
                'borderRadius': '4px',
                'padding': '10px',
                'backgroundColor': 'white'
            }),

        ], style={'marginBottom': 20}),

        dcc.Store(id='insights-store', data={}),
    ], style={'padding': '0 20px'})


# ========== 主回调 ==========

@callback(
    Output('insights-kpi-cards', 'children'),
    Output('insights-ma-cards', 'children'),
    Output('insights-hit-heatmap', 'figure'),
    Output('insights-tweet-timeline', 'figure'),
    Output('insights-tweet-heatmap', 'figure'),
    Output('insights-histogram', 'figure'),
    Output('insights-correlation', 'figure'),
    Output('insights-hourly-distribution', 'figure'),
    Output('insights-survival-chart', 'figure'),
    Input('insights-time-range', 'value')
)
def update_insights(time_range):
    stats = get_overview_stats()
    kpi_cards = html.Div([
        html.Div([
            html.Div("📅 总事件", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(str(stats['total_events']), style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
        html.Div([
            html.Div("🐦 总推文", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{stats['total_tweets']:,}", style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
        html.Div([
            html.Div("🎯 命中市场", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(str(stats['hit_count']), style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
        html.Div([
            html.Div("🔥 最热区间", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(stats['hot_range'], style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
    ], style={
        'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px', 'justifyContent': 'space-around'
    })

    ma = get_ma_values()
    ma_cards = html.Div([
        html.Div([
            html.Div("24小时平均", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{ma['ma_24h']:.1f}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#3498db'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("7天平均", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{ma['ma_7d']:.1f}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2ecc71'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("14天平均", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{ma['ma_14d']:.1f}", style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#e67e22'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px', 'justifyContent': 'space-around'})

    hit_df = get_hit_distribution()
    if not hit_df.empty:
        events_unique = hit_df['event_short'].unique()
        if len(events_unique) > 30:
            hit_df = hit_df[hit_df['event_short'].isin(events_unique[-30:])]
        range_order = hit_df[['range_label', 'range_start']].drop_duplicates().sort_values('range_start')['range_label'].tolist()
        hit_pivot = hit_df.pivot_table(index='range_label', columns='event_short', values='is_hit', fill_value=0, aggfunc='max')
        hit_pivot = hit_pivot.reindex(range_order)
        heatmap_fig = go.Figure(data=go.Heatmap(
            z=hit_pivot.values, x=hit_pivot.columns, y=hit_pivot.index,
            colorscale=[[0, '#e8e8e8'], [1, '#d62728']], zmin=0, zmax=1, showscale=False,
            hovertemplate='事件: %{x}<br>区间: %{y}<br>命中: %{z}<extra></extra>'
        ))
        heatmap_fig.update_layout(
            xaxis={'tickangle': -45, 'tickfont': {'size': 10}},
            yaxis={'title': '推文区间', 'autorange': 'reversed'},
            margin={'l': 100, 'r': 20, 't': 20, 'b': 120}, height=450
        )
    else:
        heatmap_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    tweet_df = get_tweet_timeline(30 if time_range == 'all' else time_range)
    if not tweet_df.empty:
        tweet_fig = go.Figure()
        tweet_fig.add_trace(go.Scatter(x=tweet_df['hour_utc'], y=tweet_df['tweet_count'], mode='lines', name='推文数',
                                       line=dict(color='#ff6b35', width=1.5), fill='tozeroy', fillcolor='rgba(255,107,53,0.1)'))
        tweet_df['sma_7'] = tweet_df['tweet_count'].rolling(7).mean()
        tweet_fig.add_trace(go.Scatter(x=tweet_df['hour_utc'], y=tweet_df['sma_7'], mode='lines', name='7日移动平均',
                                       line=dict(color='#2c3e50', width=2, dash='dash')))
        tweet_fig.update_layout(xaxis={'title': '时间'}, yaxis={'title': '推文数'}, hovermode='x unified',
                                margin={'l': 40, 'r': 20, 't': 20, 'b': 40})
    else:
        tweet_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    heatmap_df = get_tweet_heatmap()
    if not heatmap_df.empty:
        heatmap_pivot = heatmap_df.pivot_table(index='dow_label', columns='hour', values='avg_tweets', fill_value=0)
        heatmap2_fig = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values, x=heatmap_pivot.columns, y=heatmap_pivot.index, colorscale='Reds',
            hovertemplate='星期: %{y}<br>小时: %{x}<br>平均推文: %{z:.1f}<extra></extra>'
        ))
        heatmap2_fig.update_layout(xaxis={'title': '小时 (UTC)', 'tickmode': 'array', 'tickvals': list(range(0, 24, 3))},
                                   yaxis={'title': '星期'}, margin={'l': 80, 'r': 20, 't': 20, 'b': 40})
    else:
        heatmap2_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    hist_df = get_histogram_data()
    if not hist_df.empty:
        hist_fig = px.bar(hist_df.sort_values('range_start'), x='range_label', y='hit_count',
                          title='各区间命中次数', labels={'x': '推文区间', 'y': '命中次数'}, color='hit_count',
                          color_continuous_scale='Reds')
        hist_fig.update_layout(xaxis={'tickangle': -45}, showlegend=False, margin={'l': 40, 'r': 20, 't': 40, 'b': 80})
    else:
        hist_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    corr_df = get_correlation_data()
    if not corr_df.empty:
        correlation = corr_df['price_last'].corr(corr_df['tweet_count'])
        corr_fig = px.scatter(corr_df, x='tweet_count', y='price_last',
                              title=f'价格 vs 推文 (相关系数: {correlation:.3f})',
                              labels={'tweet_count': '推文数', 'price_last': '价格'},
                              opacity=0.5, color_discrete_sequence=['#3498db'])
        corr_fig.update_layout(margin={'l': 40, 'r': 20, 't': 40, 'b': 40})
    else:
        corr_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    hourly_df = get_hourly_distribution()
    if not hourly_df.empty:
        hour_fig = px.bar(hourly_df, x='hour', y='avg_tweets', title='24小时平均推文数',
                          labels={'hour': 'UTC 小时', 'avg_tweets': '平均推文数'},
                          color='avg_tweets', color_continuous_scale='Blues')
        hour_fig.update_layout(xaxis={'tickmode': 'linear', 'dtick': 2}, showlegend=False,
                               margin={'l': 40, 'r': 20, 't': 40, 'b': 40})
    else:
        hour_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    survival_df = get_survival_by_range()
    if not survival_df.empty:
        survival_fig = go.Figure()
        survival_fig.add_trace(go.Bar(
            x=survival_df['range_label'], y=survival_df['avg_survival_hours'],
            text=survival_df['sample_count'].astype(str), textposition='outside',
            marker_color='#3498db', hovertemplate='区间: %{x}<br>平均存活: %{y:.1f}h<br>样本量: %{text}<extra></extra>'
        ))
        survival_fig.update_layout(xaxis={'title': '推文区间', 'tickangle': -45}, yaxis={'title': '平均存活时长 (小时)'},
                                   margin={'l': 50, 'r': 20, 't': 20, 'b': 80})
    else:
        survival_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    return kpi_cards, ma_cards, heatmap_fig, tweet_fig, heatmap2_fig, hist_fig, corr_fig, hour_fig, survival_fig


# ========== 推文探索器回调 ==========

@callback(
    Output('tweet-explorer-event', 'options'),
    Input('insights-time-range', 'value')
)
def populate_event_dropdown(_):
    events_df = get_event_timeline_events()
    if events_df.empty:
        return []
    return [
        {'label': row['slug'][:40] + '...' if len(row['slug']) > 40 else row['slug'], 'value': row['id']}
        for _, row in events_df.iterrows()
    ]


@callback(
    Output('tweet-explorer-event-container', 'style'),
    Output('tweet-explorer-date-container', 'style'),
    Input('tweet-explorer-mode', 'value')
)
def toggle_explorer_inputs(mode):
    if mode == 'event':
        return {'display': 'inline-block', 'marginRight': '15px'}, {'display': 'none'}
    elif mode == 'custom':
        return {'display': 'none'}, {'display': 'inline-block'}
    else:
        return {'display': 'none'}, {'display': 'none'}


@callback(
    Output('tweet-explorer-stats', 'children'),
    Output('tweet-explorer-table', 'children'),
    Input('tweet-explorer-mode', 'value'),
    Input('tweet-explorer-event', 'value'),
    Input('tweet-explorer-start-date', 'value'),
    Input('tweet-explorer-end-date', 'value')
)
def update_tweet_explorer(mode, event_id, start_date, end_date):
    import plotly.graph_objects as go
    today = datetime.now().date()

    if mode == 'event' and event_id:
        ev_start, ev_end = get_event_time_range(event_id)
        if ev_start:
            start_date = ev_start
            end_date = ev_end
        else:
            start_date = None
            end_date = None
    elif mode == '7d':
        start_date = (today - timedelta(days=7)).isoformat()
        end_date = today.isoformat()
    elif mode == '30d':
        start_date = (today - timedelta(days=30)).isoformat()
        end_date = today.isoformat()
    elif mode == '90d':
        start_date = (today - timedelta(days=90)).isoformat()
        end_date = today.isoformat()
    elif mode == 'custom':
        pass
    else:
        start_date = None
        end_date = None

    df = get_tweet_matrix(start_date, end_date)
    if df.empty:
        return html.Div("暂无数据"), html.Div("暂无数据")

    # ---- 构建矩阵 ----
    pivot = df.pivot_table(
        index='hour',
        columns='date',
        values='tweet_count',
        fill_value=0,
        aggfunc='sum'
    )
    pivot = pivot.sort_index(axis=1)

    # ---- 计算统计量 ----
    hour_indices = [int(h) for h in pivot.index.tolist()]
    date_labels = [d for d in pivot.columns.tolist()]

    # ---- 判断统计期 ----
    stat_start_dt = None
    stat_end_dt = None
    if mode == 'event' and event_id:
        stat_start, stat_end = get_event_time_range(event_id)
        if stat_start:
            stat_start_dt = pd.to_datetime(stat_start)
            stat_end_dt = pd.to_datetime(stat_end) - pd.Timedelta(hours=1)
        else:
            stat_start_dt = None
            stat_end_dt = None
    else:
        stat_start_dt = None
        stat_end_dt = None

    def is_in_stat_period(date_str, hour_str):
        if stat_start_dt is None or stat_end_dt is None:
            return True
        try:
            dt = pd.to_datetime(date_str) + pd.Timedelta(hours=int(hour_str))
            return stat_start_dt <= dt <= stat_end_dt
        except:
            return True

    # ---- 只统计活跃期内的总推文 ----
    total_tweets = 0
    for i, hour_val in enumerate(hour_indices):
        for j, date_label in enumerate(date_labels):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                total_tweets += int(pivot.iloc[i, j])

    # ---- 计算行平均值（只统计活跃期） ----
    row_avg_values = []
    for i, hour_val in enumerate(hour_indices):
        active_vals = []
        for j, date_label in enumerate(date_labels):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                active_vals.append(int(pivot.iloc[i, j]))
        if active_vals:
            row_avg_values.append(round(sum(active_vals) / len(active_vals), 1))
        else:
            row_avg_values.append(0)
    row_avg = pd.Series(row_avg_values, index=pivot.index)

    # ---- 计算列总计（只统计活跃期） ----
    col_total_values = []
    for j, date_label in enumerate(date_labels):
        active_vals = []
        for i, hour_val in enumerate(hour_indices):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                active_vals.append(int(pivot.iloc[i, j]))
        if active_vals:
            col_total_values.append(sum(active_vals))
        else:
            col_total_values.append(0)
    col_total = pd.Series(col_total_values, index=pivot.columns)

    # ---- 计算行平均值（只统计活跃期内的数据） ----
    row_avg_values = []
    for i, hour_val in enumerate(hour_indices):
        active_vals = []
        for j, date_label in enumerate(date_labels):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                active_vals.append(int(pivot.iloc[i, j]))
        if active_vals:
            row_avg_values.append(round(sum(active_vals) / len(active_vals), 1))
        else:
            row_avg_values.append(0)
    row_avg = pd.Series(row_avg_values, index=pivot.index)
    col_total = pivot.sum(axis=0)

    # ---- 判断统计期（用于筛选总推文） ----
    stat_start_dt = None
    stat_end_dt = None
    if mode == 'event' and event_id:
        stat_start, stat_end = get_event_time_range(event_id)
        if stat_start:
            stat_start_dt = pd.to_datetime(stat_start)
            stat_end_dt = pd.to_datetime(stat_end) - pd.Timedelta(hours=1)
        else:
            stat_start_dt = None
            stat_end_dt = None
    else:
        stat_start_dt = None
        stat_end_dt = None

    def is_in_stat_period(date_str, hour_str):
        if stat_start_dt is None or stat_end_dt is None:
            return True
        try:
            dt = pd.to_datetime(date_str) + pd.Timedelta(hours=int(hour_str))
            return stat_start_dt <= dt <= stat_end_dt
        except:
            return True

    # 只统计活跃期内的推文总数
    total_tweets = 0
    for i, hour_val in enumerate(hour_indices):
        for j, date_label in enumerate(date_labels):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                total_tweets += int(pivot.iloc[i, j])

    # ---- 统计摘要卡 ----
    avg_per_hour = df['tweet_count'].mean()
    peak_hour = df.loc[df['tweet_count'].idxmax()] if not df.empty else None
    days_count = len(df['date'].unique())

    if days_count >= 2:
        dates_sorted = sorted(df['date'].unique())
        latest_day = dates_sorted[-1]
        prev_day = dates_sorted[-2]
        latest_total = df[df['date'] == latest_day]['tweet_count'].sum()
        prev_total = df[df['date'] == prev_day]['tweet_count'].sum()
        if latest_total > prev_total * 1.1:
            trend = "↑"
        elif latest_total < prev_total * 0.9:
            trend = "↓"
        else:
            trend = "→"
    else:
        trend = "—"

    stats_cards = html.Div([
        html.Div([
            html.Div("📊 总推文", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{int(total_tweets):,}", style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("📈 平均/小时", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{avg_per_hour:.1f}", style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("🔥 峰值小时", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{int(peak_hour['hour']):02d}:00" if peak_hour is not None else "N/A",
                     style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("📅 天数", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(str(days_count), style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("📈 趋势", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(trend, style={'fontSize': '20px', 'fontWeight': 'bold', 'color': '#2ecc71' if trend == '↑' else '#e74c3c' if trend == '↓' else '#f39c12'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
    ], style={
        'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px', 'justifyContent': 'space-around'
    })

    # ---- 获取统计期范围 ----
    stat_start_dt = None
    stat_end_dt = None
    if mode == 'event' and event_id:
        stat_start, stat_end = get_event_time_range(event_id)
        if stat_start:
            stat_start_dt = pd.to_datetime(stat_start)
            stat_end_dt = pd.to_datetime(stat_end) - pd.Timedelta(hours=1)
        else:
            stat_start_dt = None
            stat_end_dt = None
    else:
        stat_start_dt = None
        stat_end_dt = None

    def is_in_stat_period(date_str, hour_str):
        if stat_start_dt is None or stat_end_dt is None:
            return True
        try:
            dt = pd.to_datetime(date_str) + pd.Timedelta(hours=int(hour_str))
            return stat_start_dt <= dt <= stat_end_dt
        except:
            return True

    # ---- 构建表格 ----
    header_vals = ['小时'] + date_labels + ['Avg']

    # 计算最大推文数（仅统计活跃期内的值）
    all_active_values = []
    for i, hour_val in enumerate(hour_indices):
        for j, date_label in enumerate(date_labels):
            val = int(pivot.iloc[i, j])
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                all_active_values.append(val)
    max_val = max(all_active_values) if all_active_values else 1

    def get_color(value, is_active):
        if not is_active:
            return '#e8e8e8'
        if value == 0:
            return '#fef9e7'
        intensity = min(value / max_val, 1.0) if max_val > 0 else 0
        r = 255
        g = int(248 - intensity * 180)
        b = int(230 - intensity * 200)
        return f'rgb({r}, {g}, {b})'

    # 构建数据行
    cell_vals = []
    for i, hour_val in enumerate(hour_indices):
        row = [f"{hour_val:02d}:00"]
        hour_str = f"{hour_val:02d}"
        for j, date_label in enumerate(date_labels):
            val = int(pivot.iloc[i, j])
            is_active = is_in_stat_period(date_label, hour_str)
            if is_active:
                display_val = val
                color = get_color(val, True)
            else:
                display_val = ''  # 灰色区域显示为空
                color = '#e8e8e8'
            row.append({'value': display_val, 'color': color})
        row.append({'value': round(row_avg.iloc[i], 1), 'color': '#eaf2f8'})
        cell_vals.append(row)

    # Total 行
    total_row = ['Total']
    for j, date_label in enumerate(date_labels):
        val = int(col_total.iloc[j])
        total_row.append({'value': val, 'color': '#e8e8e8'})
    total_row.append({'value': round(total_tweets / len(hour_indices), 1), 'color': '#e8e8e8'})
    cell_vals.append(total_row)

    # 构建列数据
    values_list = []
    colors_list = []
    for col_idx in range(len(header_vals)):
        col_vals = []
        col_colors = []
        for row in cell_vals:
            if isinstance(row[col_idx], dict):
                col_vals.append(row[col_idx]['value'])
                col_colors.append(row[col_idx]['color'])
            else:
                col_vals.append(row[col_idx])
                col_colors.append('white')
        values_list.append(col_vals)
        colors_list.append(col_colors)

    # 动态高度
    row_height = 28
    n_rows = len(hour_indices) + 1 + 1
    fig_height = max(400, n_rows * row_height + 60)

    fig = go.Figure(data=[go.Table(
        header=dict(
            values=header_vals,
            fill_color='#f1f3f5',
            align='center',
            font=dict(size=12, color='#2c3e50')
        ),
        cells=dict(
            values=values_list,
            fill_color=colors_list,
            align='center',
            font=dict(size=11, color='#1a1a1a'),
            format=[''] + ['.0f'] * len(date_labels) + ['.1f']
        )
    )])

    fig.update_layout(
        height=fig_height,
        margin=dict(l=10, r=10, t=10, b=10)
    )

    return stats_cards, dcc.Graph(figure=fig)
