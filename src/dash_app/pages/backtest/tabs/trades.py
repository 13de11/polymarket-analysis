"""
交易明细 Tab
- 交易明细表
"""

from dash import html
import pandas as pd

from src.dash_app.utils.backtest.runner import run_backtest


def render_trades_tab(params, series='7d'):
    """渲染交易明细 Tab"""
    if not params or not params.get('market_id'):
        return html.Div([
            html.P("📋 交易明细将在此显示", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
            html.P("请配置参数并点击「运行回测」", style={'color': '#6c757d', 'textAlign': 'center'})
        ]), "请选择事件和市场，点击「运行回测」"

    result = run_backtest(params, series)
    if result is None:
        return html.Div([
            html.P("❌ 回测运行失败，请检查参数",
                   style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '40px 0'})
        ]), "回测运行失败"

    trades = result.get('trades', [])
    completed_trades = [t for t in trades if t.get('result') != 'pending']

    if not completed_trades:
        return html.Div([
            html.P("📋 暂无交易记录", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'})
        ]), "暂无交易记录"

    table_rows = []
    for t in completed_trades:
        result_color = '#28a745' if t.get('result') == '盈利' else '#e74c3c' if t.get(
            'result') == '亏损' else '#f39c12'
        entry_time = t.get('entry_time', '')
        exit_time = t.get('exit_time', '')
        if hasattr(entry_time, 'strftime'):
            entry_time = entry_time.strftime('%Y-%m-%d %H:%M')
        elif isinstance(entry_time, str) and 'T' in entry_time:
            entry_time = entry_time.replace('T', ' ')[:16]
        if hasattr(exit_time, 'strftime'):
            exit_time = exit_time.strftime('%Y-%m-%d %H:%M')
        elif isinstance(exit_time, str) and 'T' in exit_time:
            exit_time = exit_time.replace('T', ' ')[:16]

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
            html.Td(str(t.get('trade_id', ''))),
            html.Td(entry_time),
            html.Td(exit_time),
            html.Td(f"{t.get('entry_price', 0):.4f}"),
            html.Td(f"{t.get('exit_price', 0):.4f}"),
            html.Td(shares_display, style=shares_style),
            html.Td(f"${t.get('profit', 0):.2f}"),
            html.Td(f"{t.get('profit_pct', 0):.2f}%"),
            html.Td(f"{t.get('hold_hours', 0):.1f}h" if t.get('hold_hours') else ''),
            html.Td(t.get('result', ''), style={'color': result_color, 'fontWeight': 'bold'}),
        ]))

    content = html.Div([
        html.H5("📋 交易明细", style={'margin': '10px 0'}),
        html.Div([
            html.Table([
                html.Thead(html.Tr([
                    html.Th('#'), html.Th('开仓时间'), html.Th('平仓时间'),
                    html.Th('开仓价'), html.Th('平仓价'), html.Th('份数(期望/实际)'),
                    html.Th('盈亏($)'), html.Th('盈亏(%)'), html.Th('持仓时间'), html.Th('结果')
                ])),
                html.Tbody(table_rows)
            ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})
        ], style={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'})
    ])

    return content, f"✅ 共 {len(completed_trades)} 笔交易"