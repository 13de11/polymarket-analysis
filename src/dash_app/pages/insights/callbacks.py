"""
数据分析中心 - 回调
- update_insights_overview：KPI + MA + 热力图
- update_insights_tweets：推文时间线 + 热力图 + 24h 分布
- update_insights_hits：命中分布 + 相关性 + 存活时长
"""

from dash import html, dcc, Input, Output, callback, no_update
import plotly.graph_objects as go
import pandas as pd

from src.dash_app.utils.stats_loader import (
    get_overview_stats,
    get_hit_distribution,
    get_tweet_timeline,
    get_tweet_heatmap,
    get_correlation_data,
    get_histogram_data,
    get_ma_values,
    get_hourly_distribution,
    get_survival_by_range,
)


# ========== 回调 1：KPI + 移动平均 + 命中热力图 ==========

@callback(
    Output('insights-kpi-cards', 'children'),
    Output('insights-ma-cards', 'children'),
    Output('insights-hit-heatmap', 'figure'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
)
def update_insights_overview(series, pathname):
    if pathname != '/insights':
        return no_update, no_update, no_update

    stats = get_overview_stats(series)

    def _kpi_card(icon_label, value):
        return html.Div([
            html.Div(icon_label, style={'fontSize': '12px',
                                        'color': '#6c757d'}),
            html.Div(str(value), style={'fontSize': '24px',
                                        'fontWeight': 'bold',
                                        'marginTop': '4px'})
        ], style={
            'textAlign': 'center', 'padding': '15px',
            'backgroundColor': 'white',
            'borderRadius': '6px',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
            'minWidth': '140px', 'flex': '1'
        })

    kpi_cards = html.Div([
        _kpi_card("📅 总事件", stats['total_events']),
        _kpi_card("🐦 总推文", f"{stats['total_tweets']:,}"),
        _kpi_card("🎯 命中市场", stats['hit_count']),
        _kpi_card("🔥 最热区间", stats['hot_range']),
    ], style={
        'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px'
    })

    ma = get_ma_values()

    def _ma_card(label, value, color):
        return html.Div([
            html.Div(label, style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{value:.1f}", style={'fontSize': '24px',
                                            'fontWeight': 'bold',
                                            'color': color,
                                            'marginTop': '4px'})
        ], style={
            'textAlign': 'center', 'padding': '15px',
            'backgroundColor': 'white',
            'borderRadius': '6px',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
            'minWidth': '140px', 'flex': '1'
        })

    ma_cards = html.Div([
        _ma_card("24小时平均", ma['ma_24h'], '#3498db'),
        _ma_card("7天平均", ma['ma_7d'], '#2ecc71'),
        _ma_card("14天平均", ma['ma_14d'], '#e67e22'),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px'})

    hit_df = get_hit_distribution(series)

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

    return kpi_cards, ma_cards, heatmap_fig


# ========== 回调 2：推文相关（时间线 + 热力图 + 24h 分布） ==========

@callback(
    Output('insights-tweet-timeline', 'figure'),
    Output('insights-tweet-heatmap', 'figure'),
    Output('insights-hourly-distribution', 'figure'),
    Input('insights-time-range', 'value'),
    Input('url', 'pathname'),
)
def update_insights_tweets(time_range, pathname):
    if pathname != '/insights':
        return no_update, no_update, no_update

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

    hourly_df = get_hourly_distribution()

    if not hourly_df.empty:
        hour_fig = go.Figure(go.Bar(
            x=hourly_df['hour'],
            y=hourly_df['avg_tweets'],
            marker=dict(
                color=hourly_df['avg_tweets'],
                colorscale='Blues',
                showscale=False,
            ),
            hovertemplate='小时: %{x}<br>平均推文: %{y:.1f}<extra></extra>',
        ))
        hour_fig.update_layout(
            title='24小时平均推文数',
            xaxis=dict(title='UTC 小时', tickmode='linear', dtick=2),
            yaxis=dict(title='平均推文数'),
            showlegend=False,
            margin=dict(l=40, r=20, t=40, b=40),
        )
    else:
        hour_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    return tweet_fig, heatmap2_fig, hour_fig


# ========== 回调 3：命中分布 + 相关性 + 存活时长 ==========

@callback(
    Output('insights-histogram', 'figure'),
    Output('insights-correlation', 'figure'),
    Output('insights-survival-chart', 'figure'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
)
def update_insights_hits(series, pathname):
    if pathname != '/insights':
        return no_update, no_update, no_update

    hist_df = get_histogram_data(series)

    if not hist_df.empty:
        df_sorted = hist_df.sort_values('range_start')
        hist_fig = go.Figure(go.Bar(
            x=df_sorted['range_label'],
            y=df_sorted['hit_count'],
            marker=dict(
                color=df_sorted['hit_count'],
                colorscale='Reds',
                showscale=True,
                colorbar=dict(title='命中次数', thickness=12),
            ),
            hovertemplate='区间: %{x}<br>命中次数: %{y}<extra></extra>',
        ))
        hist_fig.update_layout(
            title='各区间命中次数（所有事件合计）',
            xaxis=dict(title='推文区间', tickangle=-45),
            yaxis=dict(title='命中次数'),
            margin=dict(l=40, r=20, t=40, b=80),
        )
    else:
        hist_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

    corr_df = get_correlation_data()

    if not corr_df.empty:
        correlation = corr_df['price_last'].corr(corr_df['tweet_count'])
        corr_fig = go.Figure(go.Scatter(
            x=corr_df['tweet_count'],
            y=corr_df['price_last'],
            mode='markers',
            marker=dict(size=6, color='#3498db', opacity=0.5),
            hovertemplate='推文数: %{x}<br>价格: %{y:.4f}<extra></extra>',
        ))
        corr_fig.update_layout(
            title=f'价格 vs 推文 (相关系数: {correlation:.3f})',
            xaxis=dict(title='推文数'),
            yaxis=dict(title='价格'),
            margin=dict(l=40, r=20, t=40, b=40),
        )
    else:
        corr_fig = go.Figure().add_annotation(text="暂无数据", showarrow=False)

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

    return hist_fig, corr_fig, survival_fig