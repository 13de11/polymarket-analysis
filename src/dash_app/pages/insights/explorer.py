"""
推文探索器 - 独立模块
- UI 构建
- 3 个回调（事件下拉 / 模式切换 / 数据更新）
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
            html.Span("表格横轴为日期，纵轴为 UTC 小时，单元格颜色深浅表示该时段推文数。Total 行 = 该日期全天推文总数；Avg 列 = 该小时在所有日期中的平均推文数。仅活跃期（事件时间范围内）的数据会着色统计，其余显示为灰色。",
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


# ========== 回调 3：更新探索器数据 ==========

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
        if start_date:
            start_date = start_date.strftime('%Y-%m-%d')
        if end_date:
            end_date = end_date.strftime('%Y-%m-%d')
    else:
        start_date = None
        end_date = None

    df = get_tweet_matrix(start_date, end_date)
    if df.empty:
        return html.Div("暂无数据"), html.Div("暂无数据")

    pivot = df.pivot_table(
        index='hour',
        columns='date',
        values='tweet_count',
        fill_value=0,
        aggfunc='sum'
    )
    pivot = pivot.sort_index(axis=1)

    hour_indices = [int(h) for h in pivot.index.tolist()]
    date_labels = [d for d in pivot.columns.tolist()]

    row_avg = pivot.mean(axis=1).round(1)
    col_total = pivot.sum(axis=0)

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

    total_tweets = 0
    for i, hour_val in enumerate(hour_indices):
        for j, date_label in enumerate(date_labels):
            if is_in_stat_period(date_label, f"{hour_val:02d}"):
                total_tweets += int(pivot.iloc[i, j])

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

    header_vals = ['小时'] + date_labels + ['Avg']

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
                display_val = ''
                color = '#e8e8e8'
            row.append({'value': display_val, 'color': color})
        row.append({'value': round(row_avg.iloc[i], 1), 'color': '#eaf2f8'})
        cell_vals.append(row)

    total_row = ['Total']
    for j, date_label in enumerate(date_labels):
        val = int(col_total.iloc[j])
        total_row.append({'value': val, 'color': '#e8e8e8'})
    total_row.append({'value': round(total_tweets / len(hour_indices), 1), 'color': '#e8e8e8'})
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