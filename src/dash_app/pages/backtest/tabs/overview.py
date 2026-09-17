"""
绩效概览 Tab
- 资金曲线 + 绩效卡片
"""

from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd

from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.utils.metrics.calculator import format_metrics_for_display


def render_overview_tab(params, series='7d'):
    """渲染绩效概览 Tab"""
    if not params or not params.get('market_id'):
        return html.Div([
            html.P("📊 绩效指标将在此显示", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
            html.P("请配置参数并点击「运行回测」", style={'color': '#6c757d', 'textAlign': 'center'})
        ]), "请选择事件和市场，点击「运行回测」"

    result = run_backtest(params, series)
    if result is None:
        return html.Div([
            html.P("❌ 回测运行失败，请检查参数",
                   style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '40px 0'})
        ]), "回测运行失败"

    metrics = result.get('metrics', {})
    equity_curve = result.get('equity_curve', [])
    formatted = format_metrics_for_display(metrics)

    core_metrics = ['最终权益', '总收益率', '总交易次数', '胜率', '盈亏比', '最大回撤', '夏普比率', '平均持仓']
    cards = []
    for key in core_metrics:
        if key in formatted:
            cards.append(html.Div([
                html.Div(key, style={'fontSize': '12px', 'color': '#7f8c8d'}),
                html.Div(formatted[key], style={'fontSize': '20px', 'fontWeight': 'bold'})
            ], style={'textAlign': 'center', 'minWidth': '80px', 'padding': '8px 12px',
                      'backgroundColor': '#f8f9fa', 'borderRadius': '6px'}))

    if equity_curve:
        fig_equity = create_equity_curve_chart(equity_curve)
    else:
        fig_equity = go.Figure()

    content = html.Div([
        html.Div([
            html.H5("📈 资金曲线", style={'margin': '10px 0'}),
            dcc.Graph(figure=fig_equity, style={'height': '300px'})
        ]),
        html.H5("📊 绩效指标", style={'margin': '15px 0 10px 0'}),
        html.Div(cards, style={
            'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px', 'justifyContent': 'center'
        }),
    ])

    status = f"✅ 回测完成 | 总交易: {metrics.get('total_trades', 0)} | 胜率: {metrics.get('win_rate', 0):.1f}% | 总收益: {metrics.get('total_return', 0):.2f}%"
    return content, status


def create_equity_curve_chart(equity_curve: list) -> go.Figure:
    """创建资金曲线图"""
    if not equity_curve:
        return go.Figure()

    df = pd.DataFrame(equity_curve)
    if df.empty:
        return go.Figure()

    # 缓存后 timestamp 可能是 ISO 字符串，转回 datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['equity'],
        name='权益曲线',
        line=dict(color='#2c3e50', width=2),
        fill='tozeroy',
        fillcolor='rgba(44, 62, 80, 0.1)'
    ))

    if not df.empty:
        initial = df['equity'].iloc[0]
        fig.add_hline(y=initial, line_dash="dash", line_color="gray", annotation_text="初始资金")

    fig.update_layout(
        title='资金曲线',
        xaxis_title='时间',
        yaxis_title='权益 ($)',
        hovermode='x',
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    fig.update_xaxes(
        tickformat='%m-%d %H:%M',
        hoverformat='%Y-%m-%d %H:%M:%S'
    )

    return fig