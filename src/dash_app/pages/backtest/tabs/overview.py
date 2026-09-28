# src/dash_app/pages/backtest/tabs/overview.py
"""
绩效概览 Tab
- 资金曲线 + 绩效卡片（核心 / 盈亏细节）
- 从 store 读缓存结果，不再自己跑回测
"""

from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd

from src.dash_app.utils.metrics.calculator import format_metrics_for_display


def render_overview_tab(cached_result):
    """渲染绩效概览 Tab，返回 (content, status)"""
    if not cached_result or not cached_result.get('metrics'):
        return html.Div("暂无回测结果",
                        style={'color': '#6c757d', 'textAlign': 'center',
                               'padding': '40px 0'}), "暂无回测结果"

    metrics = cached_result.get('metrics', {})
    equity_curve = cached_result.get('equity_curve', [])
    formatted = format_metrics_for_display(metrics)

    core_metrics = [
        '最终权益', '总收益率', '总交易次数', '胜率',
        '盈亏比', '最大回撤', '夏普比率', '平均持仓',
    ]
    detail_metrics = [
        '总盈亏', '平均盈利', '平均亏损', '最大盈利', '最大亏损',
    ]

    def _make_card(key):
        return html.Div([
            html.Div(key, style={'fontSize': '12px', 'color': '#7f8c8d'}),
            html.Div(formatted[key], style={'fontSize': '20px',
                                            'fontWeight': 'bold'}),
        ], style={'textAlign': 'center', 'minWidth': '80px',
                  'padding': '8px 12px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '6px'})

    core_cards = [_make_card(k) for k in core_metrics if k in formatted]
    detail_cards = [_make_card(k) for k in detail_metrics if k in formatted]

    if equity_curve:
        fig_equity = create_equity_curve_chart(equity_curve)
    else:
        fig_equity = go.Figure()

    content = html.Div([
        html.Div([
            html.H5("📈 资金曲线", style={'margin': '10px 0'}),
            dcc.Graph(figure=fig_equity, style={'height': '300px'}),
        ]),
        html.H5("📊 核心绩效", style={'margin': '15px 0 10px 0'}),
        html.Div(core_cards, style={
            'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px',
            'justifyContent': 'center',
        }),
        html.H5("💰 盈亏细节", style={'margin': '20px 0 10px 0'}),
        html.Div(detail_cards, style={
            'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px',
            'justifyContent': 'center',
        }),
    ])

    status = (f"✅ 回测完成 | 总交易: {metrics.get('total_trades', 0)} | "
              f"胜率: {metrics.get('win_rate', 0):.1f}% | "
              f"总收益: {metrics.get('total_return', 0):.2f}%")
    return content, status


def create_equity_curve_chart(equity_curve: list) -> go.Figure:
    if not equity_curve:
        return go.Figure()

    df = pd.DataFrame(equity_curve)
    if df.empty:
        return go.Figure()

    df['timestamp'] = pd.to_datetime(df['timestamp'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['equity'], name='权益曲线',
        line=dict(color='#2c3e50', width=2),
        fill='tozeroy', fillcolor='rgba(44, 62, 80, 0.1)',
    ))

    if not df.empty:
        initial = df['equity'].iloc[0]
        fig.add_hline(y=initial, line_dash="dash", line_color="gray",
                      annotation_text="初始资金")

    fig.update_layout(
        title='资金曲线', xaxis_title='时间', yaxis_title='权益 ($)',
        hovermode='x', height=300,
        margin=dict(l=40, r=40, t=40, b=40),
    )
    fig.update_xaxes(tickformat='%m-%d %H:%M',
                     hoverformat='%Y-%m-%d %H:%M:%S')
    return fig