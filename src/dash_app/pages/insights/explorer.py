"""
推文探索器 - 独立模块
- UI 构建
- 3 个回调（事件下拉 / 模式切换 / 数据更新）

IN-7：把原 update_tweet_explorer（约 180 行）里的计算逻辑拆成两个模块级纯函数
      _resolve_range / _compute_stats，回调只保留「守卫 + 编排 + 渲染」。
"""

from dash import html, dcc, Input, Output, callback, no_update
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

from src.dash_app.utils.stats_loader import (
    get_event_timeline_events,
    get_tweet_matrix,
    get_event_time_range,
)


# ========== 纯计算辅助（IN-7 拆出） ==========

def _resolve_range(mode, event_id, start_date, end_date, today):
    """
    把筛选模式折算成「取数区间 + 统计期」。

    Args:
        mode: 'event' / '7d' / '30d' / '90d' / 'custom'
        event_id: 事件 id（mode='event' 时有值）
        start_date, end_date: 自定义模式的日期（DatePickerSingle 的值）
        today: datetime.date，相对区间的基准日

    Returns:
        dict:
            'start'         : str | None        传给 get_tweet_matrix 的起点
            'end'           : str | None        传给 get_tweet_matrix 的终点
            'stat_start_dt' : Timestamp | None  统计期起点（None = 全部着色）
            'stat_end_dt'   : Timestamp | None  统计期终点（已减 1 小时）

    说明：get_event_time_range 全流程只调用一次（原实现同一 event_id 查了两次库）。
    """
    ev_start, ev_end = (None, None)
    if mode == 'event' and event_id:
        ev_start, ev_end = get_event_time_range(event_id)

    if mode == 'event' and event_id:
        start, end = ev_start, ev_end
    elif mode == '7d':
        start = (today - timedelta(days=7)).isoformat()
        end = today.isoformat()
    elif mode == '30d':
        start = (today - timedelta(days=30)).isoformat()
        end = today.isoformat()
    elif mode == '90d':
        start = (today - timedelta(days=90)).isoformat()
        end = today.isoformat()
    elif mode == 'custom':
        start = start_date.strftime('%Y-%m-%d') if start_date else None
        end = end_date.strftime('%Y-%m-%d') if end_date else None
    else:
        start = None
        end = None

    if mode == 'event' and ev_start:
        stat_start_dt = pd.to_datetime(ev_start)
        stat_end_dt = pd.to_datetime(ev_end) - pd.Timedelta(hours=1)
    else:
        stat_start_dt = None
        stat_end_dt = None

    return {
        'start': start,
        'end': end,
        'stat_start_dt': stat_start_dt,
        'stat_end_dt': stat_end_dt,
    }


def _compute_stats(df, stat_start_dt, stat_end_dt):
    """
    把推文矩阵 df 折算成渲染所需的全部统计量（纯 pandas，无 dash 依赖）。

    Args:
        df: get_tweet_matrix 的原始输出（date / hour / tweet_count）
        stat_start_dt, stat_end_dt: 统计期；两者为 None 时表示「全部着色」

    Returns:
        dict:
            pivot        : DataFrame    小时 × 日期 的推文矩阵
            active       : DataFrame    与 pivot 同形的布尔表（该格是否计入统计）
            hours        : list[int]    0-23
            dates        : list[str]    日期标签（已排序）
            row_avg      : Series       每个小时在活跃单元格上的均值
            col_total    : Series       每个日期在活跃单元格上的合计
            total_tweets : int          活跃单元格推文总数
            max_val      : int          活跃单元格最大值（全空时兜底 1，避免除零）
            avg_per_hour : float        活跃口径均值 = 活跃总数/活跃格数（F4 统一口径）
            peak_hour    : Series|None  峰值所在行
            days_count   : int          覆盖天数
            trend        : str          '↑' / '↓' / '→' / '—'

    active 这张布尔表同时解决了「统计」和「着色」两处的判断，
    所以统计期谓词不需要外露成第三个函数。
    """
    pivot = df.pivot_table(
        index='hour',
        columns='date',
        values='tweet_count',
        fill_value=0,
        aggfunc='sum'
    )
    pivot = pivot.sort_index(axis=1)

    hours = [int(h) for h in pivot.index.tolist()]
    dates = [d for d in pivot.columns.tolist()]

    def _in_stat_period(date_str, hour_str):
        if stat_start_dt is None or stat_end_dt is None:
            return True
        try:
            dt = pd.to_datetime(date_str) + pd.Timedelta(hours=int(hour_str))
            return stat_start_dt <= dt <= stat_end_dt
        except (ValueError, TypeError):
            return True

    active = pd.DataFrame(
        [[_in_stat_period(dates[j], f"{hours[i]:02d}") for j in range(len(dates))]
         for i in range(len(hours))],
        index=pivot.index,
        columns=pivot.columns,
    )

    # 总量 / 行均 / 列总 —— 只在 active 单元格上统计
    total_tweets = 0
    row_avg_values = []
    for i in range(len(hours)):
        active_vals = []
        for j in range(len(dates)):
            if active.iloc[i, j]:
                val = int(pivot.iloc[i, j])
                active_vals.append(val)
                total_tweets += val
        row_avg_values.append(
            round(sum(active_vals) / len(active_vals), 1) if active_vals else 0
        )
    row_avg = pd.Series(row_avg_values, index=pivot.index)

    col_total_values = []
    for j in range(len(dates)):
        active_vals = []
        for i in range(len(hours)):
            if active.iloc[i, j]:
                active_vals.append(int(pivot.iloc[i, j]))
        col_total_values.append(sum(active_vals) if active_vals else 0)
    col_total = pd.Series(col_total_values, index=pivot.columns)

    all_active_values = [
        int(pivot.iloc[i, j])
        for i in range(len(hours))
        for j in range(len(dates))
        if active.iloc[i, j]
    ]
    max_val = max(all_active_values) if all_active_values else 1

    # F4: 平均口径统一——原来用 df['tweet_count'].mean()（全量均值，
    # 含统计期外的行、且不含 pivot 补 0 的空格），与表格的活跃期统计
    # 不一致。统一为活跃口径：活跃总数 / 活跃格数，与 Avg 列、总推文卡同源
    active_count = int(active.values.sum())
    avg_per_hour = total_tweets / active_count if active_count else 0
    peak_hour = df.loc[df['tweet_count'].idxmax()] if not df.empty else None
    days_count = len(df['date'].unique())

    if days_count >= 2:
        dates_sorted = sorted(df['date'].unique())
        latest_total = df[df['date'] == dates_sorted[-1]]['tweet_count'].sum()
        prev_total = df[df['date'] == dates_sorted[-2]]['tweet_count'].sum()
        if latest_total > prev_total * 1.1:
            trend = "↑"
        elif latest_total < prev_total * 0.9:
            trend = "↓"
        else:
            trend = "→"
    else:
        trend = "—"

    return {
        'pivot': pivot,
        'active': active,
        'hours': hours,
        'dates': dates,
        'row_avg': row_avg,
        'col_total': col_total,
        'total_tweets': total_tweets,
        'max_val': max_val,
        'avg_per_hour': avg_per_hour,
        'peak_hour': peak_hour,
        'days_count': days_count,
        'trend': trend,
    }


def render_explorer_section():
    """渲染推文探索器 UI"""
    return html.Div([
        html.H4("🔍 推文探索器", style={'marginBottom': 10}),
        html.P("按时间范围或事件筛选，查看推文数量的日期-小时分布",
               style={'color': '#6c757d', 'fontSize': '13px', 'marginTop': 0}),

        html.Div([
            html.Div([
                html.Label("筛选模式:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='tweet-explorer-mode',
                    options=[
                        {'label': '事件', 'value': 'event'},
                        {'label': '近7天', 'value': '7d'},
                        {'label': '近30天', 'value': '30d'},
                        {'label': '近90天', 'value': '90d'},
                        {'label': '自定义', 'value': 'custom'},
                    ],
                    value='7d',
                    style={'width': '150px', 'display': 'inline-block'}
                ),
            ], style={'display': 'inline-block', 'marginRight': '15px'}),

            html.Div([
                html.Label("事件:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.Dropdown(
                    id='tweet-explorer-event',
                    options=[],
                    placeholder='选择事件',
                    style={'width': '350px', 'display': 'inline-block'}
                ),
            ], id='tweet-explorer-event-container', style={'display': 'none'}),

            html.Div([
                html.Label("开始日期:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.DatePickerSingle(
                    id='tweet-explorer-start-date',
                    display_format='YYYY-MM-DD',
                    placeholder='选择日期',
                    style={'width': '140px', 'display': 'inline-block', 'marginRight': '15px'}
                ),
                html.Label("结束日期:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.DatePickerSingle(
                    id='tweet-explorer-end-date',
                    display_format='YYYY-MM-DD',
                    placeholder='选择日期',
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

        html.Div(id='tweet-explorer-stats', style={'marginBottom': '15px'}),
        html.Div(id='tweet-explorer-table', style={'overflowX': 'auto', 'marginTop': '10px'}),
        html.Div([
            html.Strong("📖 如何阅读："),
            html.Span("表格横轴为日期，纵轴为 UTC 小时，单元格颜色深浅表示该时段推文数。Total 行 = 该日期活跃时段推文总数（末格为日均总量）；Avg 列 = 该小时仅统计活跃期的平均推文数；顶部「活跃期平均/小时」卡 = 活跃期平均每小时推文数，与表格同口径。仅活跃期（事件时间范围内）的数据会着色统计，其余显示为灰色。",
                      style={'color': '#495057', 'fontSize': '12px'}),
            html.Br(),
            html.Strong("💡 统计意义："),
            html.Span("可以快速识别推文高峰时段和日期分布，辅助判断事件的推文密度规律。",
                      style={'color': '#495057', 'fontSize': '12px'})
        ], style={'padding': '8px 12px', 'backgroundColor': '#f1f3f5', 'borderRadius': '4px', 'marginTop': '10px'}),
    ], style={'marginBottom': 20})


# ========== 回调 1：填充事件下拉 ==========

@callback(
    Output('tweet-explorer-event', 'options'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
)
def populate_event_dropdown(series, pathname):
    if pathname != '/insights':
        return no_update
    events_df = get_event_timeline_events(series)
    if events_df.empty:
        return []
    return [
        {'label': row['slug'].replace('elon-musk-of-tweets-', ''), 'value': row['id']}
        for _, row in events_df.iterrows()
    ]


# ========== 回调 2：切换输入区显示 ==========

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


# ========== 回调 3：更新探索器数据（守卫 + 编排 + 渲染） ==========

@callback(
    Output('tweet-explorer-stats', 'children'),
    Output('tweet-explorer-table', 'children'),
    Input('tweet-explorer-mode', 'value'),
    Input('tweet-explorer-event', 'value'),
    Input('tweet-explorer-start-date', 'value'),
    Input('tweet-explorer-end-date', 'value'),
    Input('url', 'pathname'),
)
def update_tweet_explorer(mode, event_id, start_date, end_date, pathname):
    # ---- 守卫 ----
    if pathname != '/insights':
        return no_update, no_update

    today = datetime.now().date()

    if mode == 'event' and not event_id:
        empty_fig = go.Figure()
        empty_fig.add_annotation(
            text="请先选择一个事件",
            showarrow=False,
            font=dict(size=16, color='#6c757d')
        )
        empty_fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return html.Div("请选择事件"), dcc.Graph(figure=empty_fig)

    # ---- 编排：折算区间 → 取数 → 计算 ----
    rng = _resolve_range(mode, event_id, start_date, end_date, today)

    df = get_tweet_matrix(rng['start'], rng['end'])
    if df.empty:
        return html.Div("暂无数据"), html.Div("暂无数据")

    stats = _compute_stats(df, rng['stat_start_dt'], rng['stat_end_dt'])

    hours = stats['hours']
    dates = stats['dates']
    pivot = stats['pivot']
    active = stats['active']
    row_avg = stats['row_avg']
    col_total = stats['col_total']
    max_val = stats['max_val']
    total_tweets = stats['total_tweets']
    avg_per_hour = stats['avg_per_hour']
    peak_hour = stats['peak_hour']
    days_count = stats['days_count']
    trend = stats['trend']

    # ---- 渲染：统计卡片 ----
    stats_cards = html.Div([
        html.Div([
            html.Div("📊 总推文", style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(f"{int(total_tweets):,}", style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'padding': '8px 12px', 'backgroundColor': 'white', 'borderRadius': '6px',
                  'boxShadow': '0 1px 3px rgba(0,0,0,0.1)', 'minWidth': '80px'}),
        html.Div([
            html.Div("📈 活跃期平均/小时", style={'fontSize': '12px', 'color': '#6c757d'}),
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

    # ---- 渲染：矩阵表 ----
    header_vals = ['小时'] + dates + ['Avg']

    def get_color(value):
        if value == 0:
            return '#fef9e7'
        intensity = min(value / max_val, 1.0) if max_val > 0 else 0
        r = 255
        g = int(248 - intensity * 180)
        b = int(230 - intensity * 200)
        return f'rgb({r}, {g}, {b})'

    cell_vals = []
    for i, hour_val in enumerate(hours):
        row = [f"{hour_val:02d}:00"]
        for j in range(len(dates)):
            if active.iloc[i, j]:
                val = int(pivot.iloc[i, j])
                row.append({'value': val, 'color': get_color(val)})
            else:
                row.append({'value': '', 'color': '#e8e8e8'})
        row.append({'value': round(row_avg.iloc[i], 1), 'color': '#eaf2f8'})
        cell_vals.append(row)

    total_row = ['Total']
    for j in range(len(dates)):
        total_row.append({'value': int(col_total.iloc[j]), 'color': '#e8e8e8'})
    # F4: 末格从 total/24（多天时=均值×天数，语义错位）改为日均总量，
    # 与 Total 行各日期的"全天合计"同口径
    avg_all = (round(total_tweets / len(dates), 1) if dates else 0)
    total_row.append({'value': avg_all, 'color': '#e8e8e8'})
    cell_vals.append(total_row)

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

    row_height = 28
    n_rows = len(hours) + 1 + 1
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
            format=[''] + ['.0f'] * len(dates) + ['.1f']
        )
    )])

    fig.update_layout(
        height=fig_height,
        margin=dict(l=10, r=10, t=10, b=10)
    )

    return stats_cards, dcc.Graph(figure=fig)
