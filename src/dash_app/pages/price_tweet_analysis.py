"""
价格-推文分析页面
"""
from dash import html, dcc, Input, Output, State, callback, no_update
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import time
from datetime import datetime

from src.dash_app.utils.stats_loader import HIT_THRESHOLD
from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_markets_by_event,
    get_target_market,
    get_price_data,
    get_tweet_data,
    get_target_markets_batch,
    get_top_markets_by_price,
    get_event_end_ts,
    is_event_active,
)

def layout():
    return html.Div([

        # ========== 页面标题 ==========
        html.Div([
            html.H2("📊 价格与推文关联分析", style={'marginBottom': 5}),
            html.P("分析推文数量与预测市场价格的关系",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 20}),

        # ========== 功能说明卡片 ==========
        html.Div([
            html.Div([
                html.Span("📌 ", style={'fontSize': '18px'}),
                html.Strong("数据范围"),
                html.Span(" | 仅显示 ", style={'margin': '0 5px'}),
                html.Code("slug LIKE 'elon-musk-of-tweets%'"),
                html.Span(" 的已结束 + 进行中事件", style={'margin': '0 5px'}),
            ], style={'display': 'inline-block', 'marginRight': 30}),
            html.Div([
                html.Span("⏳ ", style={'fontSize': '18px'}),
                html.Strong("进行中事件"),
                html.Span(" | 未结算、无命中区间；下拉框标注 ", style={'margin': '0 5px'}),
                html.Code("(进行中)"),
                html.Span("，默认展示当前价格最高的 5 个市场", style={'margin': '0 5px'}),
            ], style={'display': 'inline-block', 'marginRight': 30}),
            html.Div([
                html.Span("🎯 ", style={'fontSize': '18px'}),
                html.Strong("命中市场"),
                html.Span(" | 仅对已结束事件：最后一个 ", style={'margin': '0 5px'}),
                html.Code(f"price_last > {HIT_THRESHOLD}"),
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
            html.Div([
                html.Label("选择事件:", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                dcc.Dropdown(
                    id='event-selector',
                    options=[],
                    placeholder='请选择事件',
                    style={'width': '100%', 'marginTop': 4}
                ),
            ], style={'width': '40%', 'display': 'inline-block', 'paddingRight': 15, 'verticalAlign': 'top'}),

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

            html.Div([
                html.Label("默认显示:", style={'fontWeight': 'bold', 'fontSize': '14px'}),
                html.Div([
                    html.Span("已结束 → 🎯 命中市场±2",
                              style={'color': '#28a745',
                                     'fontWeight': 'bold',
                                     'display': 'block'}),
                    html.Span("进行中 → ⏳ 价格前 5",
                              style={'color': '#fd7e14',
                                     'fontWeight': 'bold',
                                     'display': 'block'})
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

        # ========== 倒计时（仅进行中事件出现；秒级跳动由前端 assets/countdown.js 负责） ==========
        html.Div(id='event-countdown-bar', style={'marginBottom': 12}),

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

        # ========== 图表说明 ==========
        html.Div([
            html.Strong("📖 图表说明：", style={'fontSize': '13px'}),
            html.Ul([
                html.Li([
                    html.Strong("价格（左轴）"),
                    html.Span("：市场对该区间「最终达成」的概率（0~1）")
                ]),
                html.Li([
                    html.Strong("每小时推文数（右轴，柱状）"),
                    html.Span("：该小时的推文总量")
                ]),
                html.Li([
                    html.Strong("累计推文"),
                    html.Span("：鼠标悬停在推文柱状图上，tooltip 中会显示")
                ]),
                html.Li([
                    html.Strong("⭐ 命中市场"),
                    html.Span(f"：最后一个价格 > {HIT_THRESHOLD} 的市场（即该区间最终「达成」），红色线高亮")
                ]),
                html.Li([
                    html.Strong("⏳ 进行中事件"),
                    html.Span("：尚无结算价，不判定命中、不画红色命中线；价格与推文均截至最新采集小时")
                ]),
            ], style={'margin': '6px 0', 'paddingLeft': '20px', 'fontSize': '12px', 'color': '#495057'})
        ], style={
            'padding': '10px 15px',
            'backgroundColor': '#f1f3f5',
            'borderRadius': '6px',
            'marginTop': '10px',
            'marginBottom': '10px'
        }),

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
    ])


# ==================== 回调1：更新事件列表 ====================
@callback(
    Output('event-selector', 'options'),
    Output('event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
    Input('data-version', 'data'),
)
def update_events(series, pathname, _version):
    if pathname != '/analysis':
        return no_update, no_update


    events_df = get_elon_tweet_events(series, include_active=True)

    if events_df.empty:
        return [], None

    # 命中市场只对已结束事件有意义（进行中事件还没结算价），
    # 因此只把这些事件送去批量查命中市场，省一次无用查询。
    finished_ids = events_df.loc[~events_df['is_active'].astype(bool), 'id'].tolist()
    targets_map = get_target_markets_batch(finished_ids)

    event_options = []
    for _, row in events_df.iterrows():
        if bool(row['is_active']):
            # 未结算：不显示"命中: x-y"（那个是当前最高价市场，会被误读成命中）
            label = f"{row['slug']} (进行中)"
        else:
            target = targets_map.get(row['id'])
            if target:
                r_start = int(target['range_start'])
                r_end = int(target['range_end']) if target['range_end'] and not pd.isna(target['range_end']) else '∞'
                label = f"{row['slug']} (命中: {r_start}-{r_end})"
            else:
                label = row['slug']
        event_options.append({'label': label, 'value': row['id']})

    default_event = events_df.iloc[-1]['id'] if not events_df.empty else None
    return event_options, default_event


# ========== 回调：事件倒计时（只在进行中事件出现） ==========

@callback(
    Output('event-countdown-bar', 'children'),
    Input('event-selector', 'value'),
    Input('url', 'pathname'),
    Input('data-version', 'data'),
)
def render_event_countdown(event_id, pathname, _version):
    """进行中事件显示距离 end_date 的倒计时

    秒级跳动不在这里做：服务端每秒回调会烧掉 PA 免费额度（100 CPU 秒/天），
    实际跳秒由前端 assets/countdown.js 读 data-end-ts 属性完成，服务端零开销。
    """
    if pathname != '/analysis' or not event_id:
        return no_update

    end_ts = get_event_end_ts(event_id)
    if not end_ts:
        return no_update

    now = int(time.time())
    if end_ts <= now:
        return no_update  # 已结束的事件不显示倒计时

    days_left = (end_ts - now) / 86400
    return html.Div([
        html.Span("⏳ ", style={'fontSize': '16px'}),
        html.Span("距离事件结束 ", style={'fontWeight': 'bold'}),
        html.Span("--", id='analysis-countdown',
                  **{'data-end-ts': str(end_ts)},
                  style={'fontFamily': 'Menlo, Consolas, monospace',
                         'fontWeight': 'bold', 'color': '#e8590c',
                         'fontSize': '15px'}),
        html.Span(f"　（约 {days_left:.1f} 天）", style={'color': '#868e96'}),
    ], style={
        'padding': '8px 12px',
        'backgroundColor': '#fff4e6',
        'border': '1px solid #ffd8a8',
        'borderRadius': '6px',
        'fontSize': '13px',
        'color': '#495057',
    })


# ==================== 回调2：更新市场列表 ====================
@callback(
    Output('market-selector', 'options'),
    Output('market-selector', 'value'),
    Output('target-market-store', 'data'),
    Output('market-hint', 'children'),
    Input('event-selector', 'value'),
    Input('url', 'pathname'),
)
def update_markets(event_id, pathname):
    if pathname != '/analysis':
        return no_update, no_update, no_update, no_update

    if not event_id:
        return [], [], {}, ""


    markets_df = get_markets_by_event(event_id)

    if markets_df.empty:
        return [], [], {}, "该事件暂无市场数据"

    options = []
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        if pd.isna(row['range_end']) or row['range_end'] is None:
            label = f"{r_start}-∞"
        else:
            label = f"{r_start}-{int(row['range_end'])}"
        options.append({'label': label, 'value': row['id']})

    # ---- 进行中事件：没有结算时刻，不存在"命中市场" ----
    # 按当前最新价格降序取前 5（价格最高的就是正在打的热门区间）
    if is_event_active(event_id):
        top_df = get_top_markets_by_price(event_id, 5)
        if not top_df.empty:
            selected_ids = top_df['id'].tolist()
        else:
            # 兜底：极端情况下查不到最新价，退回按区间升序前 5
            selected_ids = markets_df.head(5)['id'].tolist()
        hint = (f"⏳ 进行中事件（未结算，无命中区间）"
                f"，默认显示当前价格最高的 {len(selected_ids)} 个市场")
        return options, selected_ids, {}, hint

    target = get_target_market(event_id)

    if target:
        target_id = target['id']
        target_idx = markets_df[markets_df['id'] == target_id].index[0]

        start_idx = max(0, target_idx - 2)
        end_idx = min(len(markets_df), target_idx + 3)

        selected_ids = markets_df.iloc[start_idx:end_idx]['id'].tolist()
        target_info = {'id': target_id, 'range_start': target['range_start']}

        r_start = int(target['range_start'])
        if pd.isna(target['range_end']) or target['range_end'] is None:
            target_range = f"{r_start}-∞"
        else:
            target_range = f"{r_start}-{int(target['range_end'])}"

        hint = f"🎯 默认选中命中市场 {target_range} 及其前后各2个 (共 {len(selected_ids)} 个)"
    else:
        selected_ids = markets_df.head(5)['id'].tolist()
        target_info = {}
        hint = f"⚠️ 未找到 price_last > {HIT_THRESHOLD} 的市场，默认显示前5个"

    return options, selected_ids, target_info, hint


# ==================== 回调3：更新图表 ====================
@callback(
    Output('main-chart', 'figure'),
    Output('stats-info', 'children'),
    Input('event-selector', 'value'),
    Input('market-selector', 'value'),
    Input('price-type-selector', 'value'),
    State('target-market-store', 'data'),
    Input('url', 'pathname'),
    Input('data-version', 'data'),
)
def update_chart(event_id, selected_market_ids, price_type, target_info, pathname, _version):
    if pathname != '/analysis':
        return no_update, no_update

    if not event_id or not selected_market_ids:
        return go.Figure(), html.Div("请选择事件和市场")

    price_df = get_price_data(selected_market_ids)


    if price_df.empty:
        return go.Figure(), html.Div("该市场暂无价格数据")

    min_ts = price_df['hour_start_utc'].min()
    max_ts = price_df['hour_start_utc'].max()

    tweet_df = get_tweet_data(event_id, min_ts, max_ts)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    price_col = price_type

    markets_df = get_markets_by_event(event_id)

    market_names = {}
    for _, row in markets_df.iterrows():
        r_start = int(row['range_start'])
        if pd.isna(row['range_end']) or row['range_end'] is None:
            name = f"{r_start}-∞"
        else:
            name = f"{r_start}-{int(row['range_end'])}"
        market_names[row['id']] = name

    color_palette = px.colors.qualitative.Plotly
    non_target_ids = [m for m in selected_market_ids if not (target_info and target_info.get('id') == m)]
    color_map = {}
    for idx, market_id in enumerate(non_target_ids):
        color_map[market_id] = color_palette[idx % len(color_palette)]

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

    if not tweet_df.empty:
        tweet_df['cumsum'] = tweet_df['tweet_count'].cumsum()

        fig.add_trace(
            go.Bar(
                x=tweet_df['datetime_utc'],
                y=tweet_df['tweet_count'],
                name='每小时推文数',
                marker=dict(color='rgba(255, 100, 50, 0.4)'),
                yaxis='y2',
                customdata=tweet_df['cumsum'],
                hovertemplate='每小时推文: %{y}<br>累计推文: %{customdata:,.0f}<extra></extra>'
            ),
            secondary_y=True
        )

    # 按事件时长自适应 X 轴格式
    # X 轴统一用日期（不带小时）：48h 事件的市场生命周期其实跨多天
    duration_hours = (max_ts - min_ts) / 3600 if max_ts and min_ts else 0
    if duration_hours <= 24 * 10:
        dtick_ms = 24 * 3600 * 1000     # 1 天
    else:
        dtick_ms = 2 * 24 * 3600 * 1000  # 2 天

    fig.update_layout(
        autosize=True,
        title=dict(
            text=f"价格与推文趋势分析 ({'最新价' if price_type == 'price_last' else '均价'})",
            font=dict(size=15)
        ),
        xaxis=dict(
            title=None,
            tickformat='%m-%d',
            tickangle=-45,
            dtick=dtick_ms,
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
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(size=11)
        ),
        hovermode='x unified',
        dragmode='zoom',
        margin=dict(l=60, r=80, t=80, b=80),
        hoverlabel=dict(
            bgcolor='rgba(255,255,255,0.8)',
            font_size=12,
            font_family='Arial'
        )
    )

    fig.update_xaxes(
        hoverformat='%Y-%m-%d %H:%M:%S UTC',
        rangeslider=dict(
            visible=True,
            thickness=0.05,
            bgcolor='#e9ecef'
        )
    )

    fig.update_yaxes(title_text='价格', secondary_y=False, color='#1f77b4')
    fig.update_yaxes(title_text='每小时推文数', secondary_y=True, color='#ff6b35', side='right')

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