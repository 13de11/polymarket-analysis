# src/dash_app/pages/backtest/tabs/trades.py
"""
交易明细 Tab
- DataTable 支持排序 / 分页 / 导出
- 外置筛选器：结果下拉 / 平仓原因下拉 / 只看部分成交
- 部分成交：份数列红色加粗
"""

import pandas as pd
from dash import html, dcc, Input, Output, State, callback
from dash import dash_table


COLUMNS = [
    {'name': '#', 'id': 'trade_id'},
    {'name': '开仓时间', 'id': 'entry_time'},
    {'name': '平仓时间', 'id': 'exit_time'},
    {'name': '开仓价', 'id': 'entry_price'},
    {'name': '平仓价', 'id': 'exit_price'},
    {'name': '份数(期望/实际)', 'id': 'shares_display'},
    {'name': '盈亏($)', 'id': 'profit'},
    {'name': '盈亏(%)', 'id': 'profit_pct'},
    {'name': '持仓(h)', 'id': 'hold_hours'},
    {'name': '结果', 'id': 'result'},
    {'name': '平仓原因', 'id': 'reason'},
]


def render_trades_tab(cached_result):
    if not cached_result:
        return html.Div("暂无回测结果",
                        style={'color': '#6c757d', 'textAlign': 'center',
                               'padding': '40px 0'}), "暂无回测结果"

    trades = cached_result.get('trades', [])
    completed = [t for t in trades if t.get('result') != 'pending']

    if not completed:
        pending = len([t for t in trades if t.get('result') == 'pending'])
        msg = "📋 暂无已完成交易"
        if pending:
            msg += f"（有 {pending} 笔未平仓）"
        return html.Div(msg, style={'color': '#6c757d',
                                    'textAlign': 'center',
                                    'padding': '40px 0'}), msg

    df = _build_dataframe(completed)
    records = df.to_dict('records')

    result_options = [{'label': '全部', 'value': 'all'}] + [
        {'label': r, 'value': r}
        for r in sorted(df['result'].dropna().unique())
    ]
    reason_options = [{'label': '全部', 'value': 'all'}] + [
        {'label': r, 'value': r}
        for r in sorted(df['reason'].dropna().unique()) if r
    ]

    content = html.Div([
        html.H5("📋 交易明细", style={'margin': '10px 0'}),
        html.Div("💡 点表头排序 · 用下方筛选栏过滤 · 右上可导出 CSV",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '10px'}),

        # ---- 筛选栏 ----
        html.Div([
            html.Div([
                html.Label("结果", style={'fontSize': '12px',
                                          'fontWeight': 'bold',
                                          'color': '#495057',
                                          'display': 'block',
                                          'marginBottom': '4px'}),
                dcc.Dropdown(
                    id='backtest-trades-result-filter',
                    options=result_options,
                    value='all',
                    clearable=False,
                    style={'width': '120px', 'fontSize': '12px'},
                ),
            ]),
            html.Div([
                html.Label("平仓原因", style={'fontSize': '12px',
                                              'fontWeight': 'bold',
                                              'color': '#495057',
                                              'display': 'block',
                                              'marginBottom': '4px'}),
                dcc.Dropdown(
                    id='backtest-trades-reason-filter',
                    options=reason_options,
                    value='all',
                    clearable=False,
                    style={'width': '140px', 'fontSize': '12px'},
                ),
            ]),
            html.Div([
                html.Label(" ", style={'display': 'block',
                                       'marginBottom': '4px'}),
                dcc.Checklist(
                    id='backtest-trades-partial-only',
                    options=[{'label': ' 只看部分成交', 'value': 'on'}],
                    value=[],
                    style={'fontSize': '13px', 'paddingTop': '6px'},
                ),
            ]),
        ], style={'display': 'flex', 'gap': '15px',
                  'alignItems': 'flex-start', 'padding': '10px 0',
                  'borderBottom': '1px solid #e9ecef',
                  'marginBottom': '10px'}),

        # ---- 原始数据（用于筛选） ----
        dcc.Store(id='backtest-trades-raw-store', data=records),

        # ---- DataTable ----
        dash_table.DataTable(
            id='backtest-trades-table',
            data=records,
            columns=COLUMNS,
            sort_action='native',
            filter_action='none',
            page_action='native',
            page_size=20,
            page_current=0,
            export_format='csv',
            export_headers='display',
            style_table={'overflowX': 'auto', 'minWidth': '100%'},
            style_header={
                'backgroundColor': '#f1f3f5', 'fontWeight': 'bold',
                'textAlign': 'center',
                'borderBottom': '1px solid #dee2e6',
                'padding': '6px 8px', 'fontSize': '12px',
            },
            style_cell={
                'textAlign': 'center', 'padding': '5px 8px',
                'fontSize': '13px', 'border': '1px solid #e9ecef',
                'whiteSpace': 'normal', 'height': 'auto',
            },
            style_cell_conditional=[
                {'if': {'column_id': 'entry_time'}, 'minWidth': '130px'},
                {'if': {'column_id': 'exit_time'}, 'minWidth': '130px'},
                {'if': {'column_id': 'shares_display'}, 'minWidth': '120px'},
                {'if': {'column_id': 'reason'}, 'minWidth': '100px'},
            ],
            style_data_conditional=[
                {'if': {'filter_query': '{result} = "盈利"',
                        'column_id': 'result'},
                 'color': '#28a745'},
                {'if': {'filter_query': '{result} = "亏损"',
                        'column_id': 'result'},
                 'color': '#e74c3c'},
                {'if': {'filter_query': '{result} = "平盘"',
                        'column_id': 'result'},
                 'color': '#f39c12'},
                # 部分成交：份数列红字加粗
                {'if': {'filter_query': '{is_partial} = "true"',
                        'column_id': 'shares_display'},
                 'color': '#e74c3c', 'fontWeight': 'bold'},
            ],
        ),
    ])

    return content, f"✅ 共 {len(completed)} 笔交易"


def _build_dataframe(completed_trades):
    rows = []
    for t in completed_trades:
        actual_shares = t.get('shares', 0)
        desired_shares = t.get('desired_shares', actual_shares)
        is_partial = t.get('is_partial', False)
        if is_partial:
            shares_display = f"{desired_shares:.2f} / {actual_shares:.2f}"
        else:
            shares_display = f"{actual_shares:.2f}"

        rows.append({
            'trade_id': t.get('trade_id', ''),
            'entry_time': _fmt_time(t.get('entry_time')),
            'exit_time': _fmt_time(t.get('exit_time')),
            'entry_price': _fmt_num(t.get('entry_price'), 4),
            'exit_price': _fmt_num(t.get('exit_price'), 4),
            'shares_display': shares_display,
            'profit': _fmt_num(t.get('profit'), 2),
            'profit_pct': _fmt_num(t.get('profit_pct'), 2),
            'hold_hours': _fmt_num(t.get('hold_hours'), 1),
            'result': t.get('result', ''),
            'reason': t.get('reason', ''),
            # 内部字段（不在 COLUMNS 里，不显示、不导出）
            # 用于 style_data_conditional 和「只看部分成交」筛选
            'is_partial': 'true' if is_partial else 'false',
        })
    return pd.DataFrame(rows)


def _fmt_time(t):
    if t is None:
        return ''
    if hasattr(t, 'strftime'):
        return t.strftime('%Y-%m-%d %H:%M')
    if isinstance(t, str) and 'T' in t:
        return t.replace('T', ' ')[:16]
    return str(t)


def _fmt_num(v, digits):
    if v is None:
        return ''
    try:
        return round(float(v), digits)
    except (TypeError, ValueError):
        return ''


# ==================== 筛选回调 ====================

@callback(
    Output('backtest-trades-table', 'data'),
    Input('backtest-trades-result-filter', 'value'),
    Input('backtest-trades-reason-filter', 'value'),
    Input('backtest-trades-partial-only', 'value'),
    State('backtest-trades-raw-store', 'data'),
    prevent_initial_call=True,
)
def _filter_trades(result_filter, reason_filter, partial_only, raw_data):
    if not raw_data:
        return []
    df = pd.DataFrame(raw_data)
    if result_filter and result_filter != 'all':
        df = df[df['result'] == result_filter]
    if reason_filter and reason_filter != 'all':
        df = df[df['reason'] == reason_filter]
    if partial_only and 'on' in partial_only:
        df = df[df['is_partial'] == 'true']
    return df.to_dict('records')