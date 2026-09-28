# src/dash_app/pages/backtest/tabs/trades.py
"""
交易明细 Tab
- 从 store 读缓存结果
- 支持导出 CSV
"""

from dash import html, dcc

from src.dash_app.utils.ui.table import td, table as tbl


def render_trades_tab(cached_result):
    if not cached_result:
        return html.Div("暂无回测结果",
                        style={'color': '#6c757d', 'textAlign': 'center',
                               'padding': '40px 0'}), "暂无回测结果"

    trades = cached_result.get('trades', [])
    completed_trades = [t for t in trades if t.get('result') != 'pending']

    if not completed_trades:
        pending = len([t for t in trades if t.get('result') == 'pending'])
        msg = "📋 暂无已完成交易"
        if pending:
            msg += f"（有 {pending} 笔未平仓）"
        return html.Div(msg, style={'color': '#6c757d',
                                    'textAlign': 'center',
                                    'padding': '40px 0'}), msg

    table_rows = []
    for t in completed_trades:
        result_color = ('#28a745' if t.get('result') == '盈利'
                        else '#e74c3c' if t.get('result') == '亏损'
                        else '#f39c12')

        entry_time = _fmt_time(t.get('entry_time'))
        exit_time = _fmt_time(t.get('exit_time'))

        actual_shares = t.get('shares', 0)
        desired_shares = t.get('desired_shares', actual_shares)
        is_partial = t.get('is_partial', False)
        if is_partial:
            shares_display = f"{desired_shares:.2f} / {actual_shares:.2f}"
            shares_style = {'color': '#e74c3c', 'fontWeight': 'bold'}
        else:
            shares_display = f"{actual_shares:.2f}"
            shares_style = {}

        table_rows.append(html.Tr([
            td(str(t.get('trade_id', ''))),
            td(entry_time),
            td(exit_time),
            td(f"{t.get('entry_price', 0):.4f}"),
            td(f"{t.get('exit_price', 0):.4f}"),
            td(shares_display, **shares_style),
            td(f"${t.get('profit', 0):.2f}"),
            td(f"{t.get('profit_pct', 0):.2f}%"),
            td(f"{t.get('hold_hours', 0):.1f}h"
               if t.get('hold_hours') else ''),
            td(t.get('result', ''),
               color=result_color, fontWeight='bold'),
        ]))

    headers = ['#', '开仓时间', '平仓时间', '开仓价', '平仓价',
               '份数(期望/实际)', '盈亏($)', '盈亏(%)', '持仓时间', '结果']

    content = html.Div([
        html.Div([
            html.H5("📋 交易明细",
                    style={'margin': 0, 'display': 'inline-block'}),
            html.Button('📥 导出 CSV', id='backtest-trades-export-btn',
                        n_clicks=0,
                        style={
                            'padding': '6px 14px', 'borderRadius': '5px',
                            'border': 'none', 'fontSize': '12px',
                            'fontWeight': 'bold', 'cursor': 'pointer',
                            'backgroundColor': '#6c757d', 'color': 'white',
                            'float': 'right',
                        }),
        ], style={'margin': '10px 0'}),
        html.Div([
            tbl(headers, table_rows),
        ], style={'overflowX': 'auto', 'maxHeight': '500px',
                  'overflowY': 'auto'}),
    ])

    return content, f"✅ 共 {len(completed_trades)} 笔交易"


def _fmt_time(t):
    if t is None:
        return ''
    if hasattr(t, 'strftime'):
        return t.strftime('%Y-%m-%d %H:%M')
    if isinstance(t, str) and 'T' in t:
        return t.replace('T', ' ')[:16]
    return str(t)