"""
价格-推文分析页面
- 事件选择器
- 自动计算目标市场，默认显示前后各2个
- 价格类型切换 (price_last / price_avg)
- 三轴图：价格 + 每小时推文 + 累计推文
"""

import dash
from dash import html, dcc, Input, Output, State, callback
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# 不再需要 dash.register_page

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_price_data,
    get_tweet_data,
)



def layout():
    events_df = get_elon_tweet_events()

    # 预计算每个事件的命中市场区间，用于下拉显示
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

    # 默认选中最新事件（按 start_date 排序后最后一个）
    default_event = events_df.iloc[-1]['id'] if not events_df.empty else None

    return html.Div([

        # ========== 页面标题 ==========
        html.Div([
            html.H2("📊 价格与推文关联分析", style={'marginBottom': 5}),
            html.P("分析 Elon Musk 推文数量与预测市场价格的关系",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 20}),

        # ========== 功能说明卡片 ==========
        html.Div([
            html.Div([
                html.Span("📌 ", style={'fontSize': '18px'}),
                html.Strong("前置过滤条件"),
                html.Span(" | 仅显示 ", style={'margin': '0 5px'}),
                html.Code("series_slug='elon-tweets'"),
                html.Span(" 且 ", style={'margin': '0 5px'}),
                html.Code("start_date >= '2026-05-30'"),
                html.Span(" 且 ", style={'margin': '0 5px'}),
                html.Code("end_date < 当前时间"),
                html.Span(" 的事件", style={'margin': '0 5px'}),
            ], style={'display': 'inline-block', 'marginRight': 30}),
            html.Div([
                html.Span("🎯 ", style={'fontSize': '18px'}),
                html.Strong("命中市场"),
                html.Span(" | 最后一个 ", style={'margin': '0 5px'}),
                html.Code("price_last > 0.99"),
                html.Span(" 的市场", style={'margin': '0 5px'}),
            ], style={'display': 'inline-block'}),
        ], style={
            'padding': '10px 15px',
            'backgroundColor': '#e8f4fd',
            'borderRadius': '6px',
            'border': '1px solid #b8d4e8',
            'fontSize': '13px',
            'marginBottom': 20,
            'display': 'flex',
            'flexWrap': 'wrap',
            'gap': '10px'
        }),

        # ========== 筛选区域 ==========
        html.Div([
            # 事件选择器
            html.Div([
                html.Label("选择事件:", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                dcc.Dropdown(
                    id='event-selector',
                    options=event_options,
                    placeholder='请选择事件',
                    value=default_event,
                    style={'width': '100%', 'marginTop': 4}
                ),
            ], style={'width': '40%', 'display': 'inline-block', 'paddingRight': 15, 'verticalAlign': 'top'}),

            # 价格类型切换
            html.Div([
                html.Label("价格类型:", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                dcc.RadioItems(
                    id='price-type-selector',
                    options=[
                        {'label': '最新价 (Last)', 'value': 'price_last'},
                        {'label': '均价 (Avg)', 'value': 'price_avg'}
                    ],
                    value='price_last',
                    inline=True,
                    style={'marginTop': 6}
                ),
            ], style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'}),

            # 市场选择提示
            html.Div([
                html.Label("默认显示:", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                html.Div([
                    html.Span("🎯 命中市场 ± 2", style={'color': '#28a745', 'fontWeight': 'bold'}),
                    html.Span("  (共5个市场)", style={'color': '#6c757d', 'fontSize': '12px'})
                ], style={'marginTop': 6})
            ], style={'width': '20%', 'display': 'inline-block', 'verticalAlign': 'top'}),
        ], style={
            'display': 'flex',
            'flexWrap': 'wrap',
            'gap': '10px',
            'padding': '15px',
            'backgroundColor': '#f8f9fa',
            'borderRadius': '8px',
            'border': '1px solid #e9ecef',
            'marginBottom': 15
        }),

        # ========== 市场多选 ==========
        html.Div([
            html.Label("选择市场 (可多选，最多11个):", style={'fontWeight': 'bold', 'fontSize': '14px'}),
            html.Div([
                dcc.Dropdown(
                    id='market-selector',
                    options=[],
                    multi=True,
                    placeholder='请先选择事件',
                    style={'width': '100%'}
                ),
                html.Div(id='market-hint', style={'fontSize': '12px', 'color': '#6c757d', 'marginTop': 4})
            ]),
        ], style={'marginBottom': 15}),

        # ========== 图表 ==========
        dcc.Loading(
            id='loading-chart',
            type='circle',
            style={'width': '100%'},
            children=[
                dcc.Graph(
                    id='main-chart',
                    style={'height': '600px', 'width': '100%'},
                    config={
                        'displayModeBar': True,
                        'modeBarButtonsToAdd': ['zoom2d', 'pan2d', 'resetScale2d'],
                        'toImageButtonOptions': {'format': 'png'}
                    }
                )
            ]
        ),

        # ========== 底部统计信息 ==========
        html.Div(id='stats-info', style={
            'marginTop': 12,
            'padding': '10px 15px',
            'backgroundColor': '#f8f9fa',
            'borderRadius': '6px',
            'border': '1px solid #e9ecef',
            'fontSize': '13px',
            'display': 'flex',
            'flexWrap': 'wrap',
            'gap': '20px',
            'alignItems': 'center'
        }),

        dcc.Store(id='target-market-store', data={}),
        dcc.Store(id='target-range-store', data={}),
    ])


# ==================== 回调函数 ====================

@callback(
    Output('market-selector', 'options'),
    Output('market-selector', 'value'),
    Output('target-market-store', 'data'),
    Output('target-range-store', 'data'),
    Output('market-hint', 'children'),
    Input('event-selector', 'value')
)
def update_markets(event_id):
    """事件变化时：只显示命中市场前后各5个（共11个），默认选中前后各2个（共5个）"""
    if not event_id:
        return [], [], {}, {}, ""

    markets_df = get_markets_by_event(event_id)

    if markets_df.empty:
        return [], [], {}, {}, "该事件暂无市场数据"

    # 查找目标市场
    target = get_target_market(event_id)

    if not target:
        selected_df = markets_df.head(5)
        options = []
        for _, row in selected_df.iterrows():
            r_start = int(row['range_start'])
            if pd.isna(row['range_end']) or row['range_end'] is None:
                label = f"{r_start}-∞"
            else:
                label = f"{r_start}-{int(row['range_end'])}"
            options.append({'label': label, 'value': row['id']})
        return options, selected_df['id'].tolist(), {}, {}, "⚠️ 未找到 price_last > 0.99 的市场，默认显示前5个"

    target_id = target['id']
    target_idx = markets_df[markets_df['id'] == target_id].index[0]

    # 前后各5个（共11个）
    start_idx = max(0, target_idx - 5)
    end_idx = min(len(markets_df), target_idx + 6)
    visible_markets = markets_df.iloc[start_idx:end_idx]

    options = []
    for _, row in visible_markets.iterrows():
        r_start = int(row['range_start'])
        if pd.isna(row['range_end']) or row['range_end'] is None:
            label = f"{r_start}-∞"
        else:
            label = f"{r_start}-{int(row['range_end'])}"
        options.append({'label': label, 'value': row['id']})

    # 默认前后各2个（共5个）
    default_start = max(0, target_idx - 2)
    default_end = min(len(markets_df), target_idx + 3)
    default_ids = markets_df.iloc[default_start:default_end]['id'].tolist()

    target_info = {'id': target_id, 'range_start': target['range_start']}
    r_start = int(target['range_start'])
    if pd.isna(target['range_end']) or target['range_end'] is None:
        target_range = f"{r_start}-∞"
    else:
        target_range = f"{r_start}-{int(target['range_end'])}"

    hint = f"🎯 命中市场 {target_range} | 下拉显示前后各5个 (共 {len(visible_markets)} 个) | 默认选中前后各2个 (共 {len(default_ids)} 个)"

    return options, default_ids, target_info, {'range': target_range}, hint


@callback(
    Output('main-chart', 'figure'),
    Output('stats-info', 'children'),
    Input('event-selector', 'value'),
    Input('market-selector', 'value'),
    Input('price-type-selector', 'value'),
    State('target-market-store', 'data'),
)
def update_chart(event_id, selected_market_ids, price_type, target_info):
    """更新图表"""
    if not event_id or not selected_market_ids:
        return go.Figure(), html.Div("请选择事件和市场")

    price_df = get_price_data(selected_market_ids)

    if price_df.empty:
        return go.Figure(), html.Div("该市场暂无价格数据")

    min_ts = price_df['hour_start_utc'].min()
    max_ts = price_df['hour_start_utc'].max()

    tweet_df = get_tweet_data(event_id, min_ts, max_ts)

    # 构建图表
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    price_col = price_type

    # 获取市场信息
    markets_df = get_markets_by_event(event_id)
    market_names = {}
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        if pd.isna(row['range_end']) or row['range_end'] is None:
            name = f"{r_start}-∞"
        else:
            name = f"{r_start}-{int(row['range_end'])}"
        market_names[row['id']] = name

    # ---- 分配颜色 ----
    color_palette = px.colors.qualitative.Plotly
    non_target_ids = [m for m in selected_market_ids if not (target_info and target_info.get('id') == m)]
    color_map = {}
    for idx, market_id in enumerate(non_target_ids):
        color_map[market_id] = color_palette[idx % len(color_palette)]

    # ---- 添加价格曲线 ----
    for market_id in selected_market_ids:
        df_market = price_df[price_df['market_id'] == market_id]
        if df_market.empty:
            continue

        market_name = market_names.get(market_id, market_id[:8])
        is_target = target_info and target_info.get('id') == market_id

        if is_target:
            line_color = '#d62728'
            line_width = 2.2
            legend_name = f"⭐ {market_name} (命中)"
        else:
            line_color = color_map.get(market_id, '#1f77b4')
            line_width = 1.5
            legend_name = market_name

        hovertemplate = (
            f'<b>{market_name}</b><br>'
            f'价格: %{{y:.4f}}'
            '<extra></extra>'
        )

        fig.add_trace(
            go.Scatter(
                x=df_market['datetime_utc'],
                y=df_market[price_col],
                name=legend_name,
                line=dict(width=line_width, dash='solid', color=line_color),
                hovertemplate=hovertemplate
            ),
            secondary_y=False
        )

    # ---- 推文柱状图 ----
    if not tweet_df.empty:
        hovertemplate_bar = (
            '每小时推文数: %{y}'
            '<extra></extra>'
        )
        fig.add_trace(
            go.Bar(
                x=tweet_df['datetime_utc'],
                y=tweet_df['tweet_count'],
                name='每小时推文数',
                marker=dict(color='rgba(255, 100, 50, 0.4)'),
                yaxis='y2',
                hovertemplate=hovertemplate_bar
            ),
            secondary_y=True
        )

        # 累计推文
        tweet_df['cumsum'] = tweet_df['tweet_count'].cumsum()
        hovertemplate_cum = (
            '累计推文数: %{y:,.0f}'
            '<extra></extra>'
        )
        fig.add_trace(
            go.Scatter(
                x=tweet_df['datetime_utc'],
                y=tweet_df['cumsum'],
                name='累计推文',
                line=dict(color='rgba(50, 150, 255, 0.7)', width=2, dash='dash'),
                yaxis='y3',
                hovertemplate=hovertemplate_cum
            ),
            secondary_y=True
        )

    # ========== 布局设置 ==========
    fig.update_layout(
        autosize=True,
        title=dict(
            text=f"价格与推文趋势分析 ({'最新价' if price_type == 'price_last' else '均价'})",
            font=dict(size=15)
        ),
        xaxis=dict(
            title=None,
            tickformat='%H:%M',
            tickangle=-45,
            dtick=21600000,
            ticklabelstep=1,
            showgrid=True,
            gridcolor='rgba(200, 200, 200, 0.4)',
            gridwidth=0.5,
            rangeslider=dict(
                visible=True,
                thickness=0.05,
                bgcolor='#e9ecef'
            )
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(200, 200, 200, 0.3)',
            gridwidth=0.5
        ),
        yaxis2=dict(
            showgrid=False,
            rangemode='tozero',  # 从 0 开始
            fixedrange=True,  # 禁止用户拖拽缩放
        ),
        legend=dict(
            orientation='h',
            yanchor='top',
            y=-0.25,
            xanchor='center',
            x=0.5,
            font=dict(size=11)
        ),
        hovermode='x unified',
        dragmode='zoom',
        margin=dict(l=60, r=80, t=50, b=120),
        # 悬停标签半透明
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.9)',
            font_size=12,
            font_family='Arial'
        )
    )

    # 设置顶部时间格式为 ISO
    fig.update_xaxes(
        hoverformat='%Y-%m-%d %H:%M:%S UTC',  # 强制 ISO 格式
        rangeslider=dict(
            visible=True,
            thickness=0.05,
            bgcolor='#e9ecef'
        )
    )

    fig.update_yaxes(title_text='价格', secondary_y=False, color='#1f77b4')
    fig.update_yaxes(title_text='每小时推文数', secondary_y=True, color='#ff6b35', side='right')

    fig.update_layout(
        yaxis3=dict(
            title='累计推文',
            overlaying='y',
            side='right',
            position=0.92,
            color='rgba(50, 150, 255, 0.7)',
            showgrid=False,
            rangemode='tozero',  # 从 0 开始
            fixedrange=True  # 禁止用户拖拽缩放（避免干扰悬停）
        )
    )

    for trace in fig.data:
        if trace.name == '累计推文':
            trace.yaxis = 'y3'

    # ---- 统计信息 ----
    stats_items = []

    stats_items.append(html.Span([
        html.Strong("📊 选中市场: "),
        f"{len(selected_market_ids)} 个"
    ]))

    stats_items.append(html.Span([
        html.Strong("💰 价格点: "),
        f"{len(price_df):,}"
    ]))

    if not tweet_df.empty:
        total_tweets = int(tweet_df['tweet_count'].sum())
        stats_items.append(html.Span([
            html.Strong("🐦 推文总数: "),
            f"{total_tweets:,} 条"
        ]))

    stats_items.append(html.Span([
        html.Strong("📅 时间范围: "),
        f"{pd.to_datetime(min_ts, unit='s').strftime('%Y-%m-%d %H:%M')} ~ "
        f"{pd.to_datetime(max_ts, unit='s').strftime('%Y-%m-%d %H:%M')} (UTC)"
    ]))

    if target_info and target_info.get('id'):
        target_row = markets_df[markets_df['id'] == target_info['id']]
        if not target_row.empty:
            r_start = int(target_row.iloc[0]['range_start'])
            if pd.isna(target_row.iloc[0]['range_end']) or target_row.iloc[0]['range_end'] is None:
                target_range = f"{r_start}-∞"
            else:
                target_range = f"{r_start}-{int(target_row.iloc[0]['range_end'])}"
            stats_items.append(html.Span([
                html.Strong("🎯 命中市场: "),
                html.Span(target_range, style={'color': '#d62728', 'fontWeight': 'bold'})
            ]))

    return fig, html.Div(stats_items, style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '20px', 'fontSize': '13px'})