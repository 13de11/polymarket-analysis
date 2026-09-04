"""
数据分析中心 (Data Insights Hub)
- KPI 指标卡
- 命中市场热力图
- 推文全量分析
- 命中区间分布
"""

import dash
from dash import html, dcc, Input, Output, callback
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np


from src.dash_app.utils.stats_loader import (
    get_overview_stats,
    get_hit_distribution,
    get_tweet_timeline,
    get_tweet_heatmap,
    get_correlation_data,
    get_histogram_data,
    get_event_timeline_events,
)


def layout():
    return html.Div([
        # ---- 页面标题 ----
        html.Div([
            html.H2("📊 数据分析中心", style={'marginBottom': 2}),
            html.P("历史事件回顾、推文热度图谱与市场命中模式分析",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 20}),

        # ---- KPI 卡片（5个核心指标） ----
        html.Div(id='insights-kpi-cards', style={'marginBottom': 20}),

        # ---- 主图区：命中市场热力图 ----
        html.Div([
            html.H4("🎯 事件-区间命中热力图", style={'marginBottom': 10}),
            html.P("横轴为事件（按时间排序），纵轴为推文区间，红色表示命中，灰色表示未命中",
                   style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),
            dcc.Graph(id='insights-hit-heatmap', style={'height': '500px'})
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
                dcc.Graph(id='insights-tweet-timeline', style={'height': '350px'})
            ], style={'marginBottom': 15}),
            html.Div([
                dcc.Graph(id='insights-tweet-heatmap', style={'height': '300px'})
            ])
        ], style={'marginBottom': 30}),

        # ---- 命中区间分布 + 相关性 ----
        html.Div([
            html.Div([
                html.H4("📊 命中区间分布", style={'marginBottom': 10}),
                dcc.Graph(id='insights-histogram', style={'height': '300px'})
            ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top'}),
            html.Div([
                html.H4("📈 价格 vs 推文相关性", style={'marginBottom': 10}),
                dcc.Graph(id='insights-correlation', style={'height': '300px'})
            ], style={'width': '48%', 'display': 'inline-block', 'float': 'right', 'verticalAlign': 'top'})
        ], style={'marginBottom': 20}),

        # ---- 隐藏存储 ----
        dcc.Store(id='insights-store', data={}),
    ], style={'padding': '0 20px'})


# ========== 回调 ==========

@callback(
    Output('insights-kpi-cards', 'children'),
    Output('insights-hit-heatmap', 'figure'),
    Output('insights-tweet-timeline', 'figure'),
    Output('insights-tweet-heatmap', 'figure'),
    Output('insights-histogram', 'figure'),
    Output('insights-correlation', 'figure'),
    Input('insights-time-range', 'value')
)
def update_insights(time_range):
    # ===== 1. KPI 指标卡 =====
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
            html.Div("📈 命中率", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{stats['hit_rate']:.1f}%", style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
        html.Div([
            html.Div("🔥 最热区间", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(stats['hot_range'], style={'fontSize': '24px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '10px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '100px'}),
    ], style={
        'display': 'flex',
        'flexWrap': 'wrap',
        'gap': '15px',
        'justifyContent': 'space-around'
    })

    # ===== 2. 命中热力图 =====
    hit_df = get_hit_distribution()
    if not hit_df.empty:
        events_unique = hit_df['event_slug'].unique()
        if len(events_unique) > 30:
            events_to_keep = events_unique[-30:]
            hit_df = hit_df[hit_df['event_slug'].isin(events_to_keep)]

        hit_pivot = hit_df.pivot_table(
            index='range_label',
            columns='event_slug',
            values='is_hit',
            fill_value=0
        )

        heatmap_fig = go.Figure(data=go.Heatmap(
            z=hit_pivot.values,
            x=hit_pivot.columns,
            y=hit_pivot.index,
            colorscale=[[0, '#e8e8e8'], [1, '#d62728']],
            zmin=0,
            zmax=1,
            showscale=False,
            hovertemplate='事件: %{x}<br>区间: %{y}<br>命中: %{z}<extra></extra>'
        ))
        heatmap_fig.update_layout(
            xaxis={'tickangle': -45, 'tickfont': {'size': 10}},
            yaxis={'title': '推文区间'},
            margin={'l': 100, 'r': 20, 't': 20, 'b': 120},
            height=450
        )
    else:
        heatmap_fig = go.Figure()
        heatmap_fig.add_annotation(text="暂无数据", showarrow=False)

    # ===== 3. 推文时间序列 =====
    tweet_df = get_tweet_timeline(30 if time_range == 'all' else time_range)
    if not tweet_df.empty:
        tweet_fig = go.Figure()
        tweet_fig.add_trace(go.Scatter(
            x=tweet_df['hour_utc'],
            y=tweet_df['tweet_count'],
            mode='lines',
            name='推文数',
            line=dict(color='#ff6b35', width=1.5),
            fill='tozeroy',
            fillcolor='rgba(255, 107, 53, 0.1)'
        ))
        tweet_df['sma_7'] = tweet_df['tweet_count'].rolling(7).mean()
        tweet_fig.add_trace(go.Scatter(
            x=tweet_df['hour_utc'],
            y=tweet_df['sma_7'],
            mode='lines',
            name='7日移动平均',
            line=dict(color='#2c3e50', width=2, dash='dash')
        ))
        tweet_fig.update_layout(
            xaxis={'title': '时间'},
            yaxis={'title': '推文数'},
            hovermode='x unified',
            margin={'l': 40, 'r': 20, 't': 20, 'b': 40}
        )
    else:
        tweet_fig = go.Figure()
        tweet_fig.add_annotation(text="暂无数据", showarrow=False)

    # ===== 4. 推文热力图 =====
    heatmap_df = get_tweet_heatmap()
    if not heatmap_df.empty:
        heatmap_pivot = heatmap_df.pivot_table(
            index='dow_label',
            columns='hour',
            values='avg_tweets',
            fill_value=0
        )
        heatmap2_fig = go.Figure(data=go.Heatmap(
            z=heatmap_pivot.values,
            x=heatmap_pivot.columns,
            y=heatmap_pivot.index,
            colorscale='Reds',
            hovertemplate='星期: %{y}<br>小时: %{x}<br>平均推文: %{z:.1f}<extra></extra>'
        ))
        heatmap2_fig.update_layout(
            xaxis={'title': '小时 (UTC)', 'tickmode': 'array', 'tickvals': list(range(0, 24, 3))},
            yaxis={'title': '星期'},
            margin={'l': 80, 'r': 20, 't': 20, 'b': 40}
        )
    else:
        heatmap2_fig = go.Figure()
        heatmap2_fig.add_annotation(text="暂无数据", showarrow=False)

    # ===== 5. 命中区间直方图 =====
    hist_df = get_histogram_data()
    if not hist_df.empty:
        hist_fig = px.bar(
            hist_df.sort_values('range_start'),
            x='range_label',
            y='hit_count',
            title='各区间命中次数',
            labels={'x': '推文区间', 'y': '命中次数'},
            color='hit_count',
            color_continuous_scale='Reds'
        )
        hist_fig.update_layout(
            xaxis={'tickangle': -45},
            showlegend=False,
            margin={'l': 40, 'r': 20, 't': 40, 'b': 80}
        )
    else:
        hist_fig = go.Figure()
        hist_fig.add_annotation(text="暂无数据", showarrow=False)

    # ===== 6. 相关性散点图 =====
    corr_df = get_correlation_data()
    if not corr_df.empty:
        correlation = corr_df['price_last'].corr(corr_df['tweet_count'])
        corr_fig = px.scatter(
            corr_df,
            x='tweet_count',
            y='price_last',
            title=f'价格 vs 推文 (相关系数: {correlation:.3f})',
            labels={'tweet_count': '推文数', 'price_last': '价格'},
            opacity=0.5,
            color_discrete_sequence=['#3498db']
        )
        corr_fig.update_layout(
            margin={'l': 40, 'r': 20, 't': 40, 'b': 40}
        )
    else:
        corr_fig = go.Figure()
        corr_fig.add_annotation(text="暂无数据", showarrow=False)

    return kpi_cards, heatmap_fig, tweet_fig, heatmap2_fig, hist_fig, corr_fig