"""
策略对比 Tab
- 策略对比 UI（Dropdown + 运行按钮）
- 对比回调
- 资金曲线对比图 + 绩效对比表
"""

from dash import html, dcc, Input, Output, State, callback
import plotly.graph_objects as go
from typing import Dict, Any
import pandas as pd

from src.dash_app.utils.comparison.engine import ComparisonEngine


def render_comparison_tab(params):
    """渲染策略对比 Tab 的 UI"""

    strategy_options = [
        {'label': '方向信号 (阈值0.005)', 'value': 'dir_005'},
        {'label': '方向信号 (阈值0.01)', 'value': 'dir_01'},
        {'label': '方向信号 (阈值0.015)', 'value': 'dir_015'},
    ]

    return html.Div([
        html.H5("📊 策略对比", style={'margin': '10px 0'}),
        html.Div([
            html.P("选择要对比的策略（最多3个）：", style={'fontSize': '14px'}),
            html.Div([
                html.Div([
                    html.Label("策略A:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='comparison-strategy-a',
                        options=strategy_options,
                        value='dir_005',
                        style={'width': '100%'}
                    ),
                ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                html.Div([
                    html.Label("策略B:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='comparison-strategy-b',
                        options=strategy_options,
                        value='dir_01',
                        style={'width': '100%'}
                    ),
                ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                html.Div([
                    html.Label("策略C (可选):", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='comparison-strategy-c',
                        options=[{'label': '无', 'value': None}] + strategy_options,
                        value=None,
                        style={'width': '100%'}
                    ),
                ], style={'width': '30%', 'display': 'inline-block'}),
            ], style={'marginBottom': '15px'}),
            html.Button(
                '🚀 运行对比',
                id='comparison-run-btn',
                n_clicks=0,
                style={
                    'padding': '10px 20px',
                    'backgroundColor': '#6c5ce7',
                    'color': 'white',
                    'border': 'none',
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'cursor': 'pointer'
                }
            ),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),
        html.Div(id='comparison-results', style={'marginTop': '15px'}),
    ])


def create_comparison_chart(results: Dict[str, Any]) -> go.Figure:
    """创建资金曲线对比图"""
    fig = go.Figure()
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6']

    for i, (name, data) in enumerate(results.items()):
        equity_curve = data.get('equity_curve', [])
        if equity_curve:
            df = pd.DataFrame(equity_curve)
            if not df.empty:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['equity'],
                    name=name,
                    line=dict(color=colors[i % len(colors)], width=2)
                ))

    fig.update_layout(
        title='策略资金曲线对比',
        xaxis_title='时间',
        yaxis_title='权益 ($)',
        hovermode='x',
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    return fig


def create_comparison_table(results: Dict[str, Any]) -> html.Table:
    """创建绩效指标对比表"""
    headers = ['策略名称', '总交易次数', '胜率', '盈亏比', '总收益', '最大回撤', '夏普比率']
    rows = []

    for name, data in results.items():
        metrics = data.get('metrics', {})
        rows.append(html.Tr([
            html.Td(name, style={'fontWeight': 'bold'}),
            html.Td(str(metrics.get('total_trades', 0))),
            html.Td(f"{metrics.get('win_rate', 0):.1f}%"),
            html.Td(f"{metrics.get('profit_factor', 0):.2f}"),
            html.Td(f"{metrics.get('total_return', 0):.2f}%"),
            html.Td(f"{metrics.get('max_drawdown_pct', 0):.2f}%"),
            html.Td(f"{metrics.get('sharpe_ratio', 0):.2f}"),
        ]))

    return html.Table([
        html.Thead(html.Tr([html.Th(h, style={'padding': '8px 12px', 'backgroundColor': '#f8f9fa'}) for h in headers])),
        html.Tbody(rows)
    ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})


@callback(
    Output('comparison-results', 'children'),
    Input('comparison-run-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    State('comparison-strategy-a', 'value'),
    State('comparison-strategy-b', 'value'),
    State('comparison-strategy-c', 'value'),
    State('series-selector', 'value'),
)
def run_comparison(n_clicks, params, strategy_a, strategy_b, strategy_c, series):
    if n_clicks == 0:
        return html.Div()

    if not params or not params.get('market_id'):
        return html.Div("请先选择事件和市场")

    strategy_configs = []
    threshold_map = {'dir_005': 0.005, 'dir_01': 0.01, 'dir_015': 0.015}

    if strategy_a:
        strategy_configs.append({
            'name': f'策略A (阈值{threshold_map[strategy_a]})',
            'params': {'price_threshold': threshold_map[strategy_a]}
        })
    if strategy_b:
        strategy_configs.append({
            'name': f'策略B (阈值{threshold_map[strategy_b]})',
            'params': {'price_threshold': threshold_map[strategy_b]}
        })
    if strategy_c:
        strategy_configs.append({
            'name': f'策略C (阈值{threshold_map[strategy_c]})',
            'params': {'price_threshold': threshold_map[strategy_c]}
        })

    results = ComparisonEngine.run_comparison(params, strategy_configs, series)

    if not results:
        return html.Div("对比运行失败，请检查参数")

    fig = create_comparison_chart(results)
    table = create_comparison_table(results)

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '400px'}),
        html.H5("📊 绩效指标对比", style={'margin': '15px 0 10px 0'}),
        table,
    ])