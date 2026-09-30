# src/dash_app/pages/backtest/tabs/evaluation.py
"""
策略评估 Tab
- 多窗口方向准确率
- 持仓周期分析
- 策略 vs 基线（含小字解释）
"""

from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from src.dash_app.utils.backtest.runner import build_signal_context
from src.dash_app.utils.metrics.accuracy import calculate_multi_window_accuracy
from src.dash_app.utils.metrics.hold_period import calculate_hold_period_analysis
from src.dash_app.utils.backtest.baseline import buy_and_hold, random_signal
from src.dash_app.utils.ui.table import td, table as tbl


def render_evaluation(params, cached_result):
    if not cached_result:
        return html.Div("暂无回测结果",
                        style={'color': '#6c757d', 'textAlign': 'center',
                               'padding': '40px 0'}), "暂无回测结果"

    trades = cached_result.get('trades', [])
    equity_curve = cached_result.get('equity_curve', [])
    metrics = cached_result.get('metrics', {})

    if not equity_curve:
        return html.Div("无回测数据",
                        style={'color': '#6c757d', 'textAlign': 'center',
                               'padding': '40px 0'}), "无回测数据"

    # ---- 1. 多窗口方向准确率 ----
    ctx = build_signal_context(params)
    if ctx is not None:
        acc_result = calculate_multi_window_accuracy(
            ctx['signal_df'], windows=(1, 6, 12, 24))
        acc_section = _render_accuracy_section(acc_result)
        price_series = ctx['signal_df']['price']
    else:
        acc_section = html.Div("无法计算（数据不足）",
                               style={'color': '#6c757d',
                                      'padding': '10px'})
        price_series = pd.Series(
            [e['price'] for e in equity_curve if 'price' in e])

    # ---- 2. 持仓周期 ----
    hold_df = calculate_hold_period_analysis(trades)
    if not hold_df.empty:
        hold_rows = [
            html.Tr([
                td(str(row['bucket'])),
                td(f"{row['win_rate']:.1f}%"),
                td(f"${row['avg_return']:.2f}"),
                td(str(int(row['count']))),
            ])
            for _, row in hold_df.iterrows()
        ]
        hold_table = tbl(
            ['持仓时长', '胜率', '平均收益', '样本数'], hold_rows)

        hold_fig = go.Figure()
        hold_fig.add_trace(go.Bar(
            x=hold_df['bucket'].astype(str),
            y=hold_df['win_rate'], name='胜率 (%)',
            marker_color='#3498db',
            text=hold_df['count'].astype(str),
            textposition='outside',
        ))
        hold_fig.update_layout(
            title='持仓周期胜率分布',
            xaxis_title='持仓时长', yaxis_title='胜率 (%)',
            height=300, margin=dict(l=50, r=50, t=50, b=50),
        )
    else:
        hold_table = html.Div("无交易记录", style={'color': '#6c757d'})
        hold_fig = go.Figure().add_annotation(text="无交易记录",
                                              showarrow=False)

    # ---- 3. 基线对比 ----
    strategy_return = metrics.get('total_return', 0)
    price_df_full = pd.DataFrame({'price': price_series.values})

    bh = buy_and_hold(price_df_full,
                      initial_capital=params.get('initial_capital', 100))

    initial_cap = params.get('initial_capital', 100)
    random_returns = []
    for seed in range(20):
        rs = random_signal(price_df_full, n_signals=10, seed=seed,
                           initial_capital=initial_cap)
        random_returns.append(rs['total_return'])
    if random_returns:
        random_avg = float(np.mean(random_returns))
        random_std = float(np.std(random_returns))
    else:
        random_avg, random_std = 0.0, 0.0

    baseline_cards = html.Div([
        _baseline_card(
            "🎯 当前策略", strategy_return,
            hint="按方向信号 ↑买 / ↓卖，每次投入固定金额",
        ),
        _baseline_card(
            "📈 全买持有", bh['total_return'],
            hint="事件开始全仓买入，持有到结束",
        ),
        _baseline_card(
            "🎲 随机信号 (20次)", random_avg, std=random_std,
            hint="随机 10 个 ↑/↓ 信号，按同规则交易，重复 20 次取均值",
        ),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px'})

    content = html.Div([
        acc_section,
        html.Div([
            html.H5("📊 策略 vs 基线", style={'margin': '20px 0 10px 0'}),
            baseline_cards,
        ]),
        _render_distribution_section(trades),
        html.Div([
            html.H5("⏱️ 持仓周期分析", style={'margin': '20px 0 10px 0'}),
            dcc.Graph(figure=hold_fig),
            html.Div(hold_table, style={'marginTop': '15px',
                                        'overflowX': 'auto'}),
        ]),
        html.Div([
            html.Strong("📖 如何阅读："),
            html.Br(),
            html.Span("• 多窗口准确率：信号发出后 N 小时内价格是否朝预测方向变化。",
                      style={'fontSize': '12px', 'color': '#495057'}),
            html.Br(),
            html.Span("• 策略 vs 基线：策略收益高于基线说明有超额收益。",
                      style={'fontSize': '12px', 'color': '#495057'}),
            html.Br(),
            html.Span("• 交易分布：看盈利/亏损的分布形状（少数大赚 vs 多数小赚）。",
                      style={'fontSize': '12px', 'color': '#495057'}),
            html.Br(),
            html.Span("• 持仓周期：按持仓时长分桶，看不同时长下的胜率和平均收益。",
                      style={'fontSize': '12px', 'color': '#495057'}),
        ], style={'padding': '10px 15px', 'backgroundColor': '#f1f3f5',
                  'borderRadius': '6px', 'marginTop': '20px'}),
    ])

    return content, "✅ 策略评估已加载"


def _render_accuracy_section(acc_result):
    if not acc_result:
        return html.Div("无数据", style={'color': '#6c757d'})

    rows = []
    for window in sorted(acc_result.keys()):
        d = acc_result[window]
        rows.append(html.Tr([
            td(f"{window}h"),
            td(f"{d['up_acc'] * 100:.1f}%"),
            td(f"{d['down_acc'] * 100:.1f}%"),
            td(f"{d['overall'] * 100:.1f}%", fontWeight='bold'),
            td(str(d['samples'])),
        ]))

    return html.Div([
        html.H5("🎯 多窗口方向准确率", style={'margin': '10px 0'}),
        html.Div("信号发出后 N 小时内价格是否朝预测方向变化",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '8px'}),
        tbl(['窗口', '▲ 上涨准确率', '▼ 下跌准确率', '综合', '样本数'], rows),
    ])


def _baseline_card(label, value, std=None, hint=None):
    children = [
        html.Div(label, style={'fontSize': '12px', 'color': '#6c757d'}),
        html.Div(f"{value:+.2f}%", style={
            'fontSize': '24px', 'fontWeight': 'bold',
            'color': '#28a745' if value > 0 else '#e74c3c',
        }),
    ]
    if std is not None:
        children.append(html.Div(f"± {std:.2f}%",
                                 style={'fontSize': '11px',
                                        'color': '#95a5a6'}))
    if hint:
        children.append(html.Div(
            hint,
            style={'fontSize': '10px', 'color': '#adb5bd',
                   'marginTop': '8px', 'lineHeight': '1.35',
                   'textAlign': 'left'},
        ))
    return html.Div(children, style={
        'textAlign': 'center', 'padding': '15px',
        'backgroundColor': 'white', 'borderRadius': '6px',
        'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
        'flex': '1', 'minWidth': '200px',
    })

def _render_distribution_section(trades):
    """交易分布：盈亏金额 + 持仓时长，两张直方图"""
    completed = [t for t in trades
                 if t.get('result') != 'pending'
                 and t.get('profit') is not None]
    if not completed:
        return html.Div()

    profits = [float(t['profit']) for t in completed
               if t.get('profit') is not None]
    hold_hours = [float(t['hold_hours']) for t in completed
                  if t.get('hold_hours') is not None]

    # ---- 盈亏金额分布 ----
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p < 0]
    flats = [p for p in profits if p == 0]

    fig_profit = go.Figure()
    if wins:
        fig_profit.add_trace(go.Histogram(
            x=wins, name=f'盈利 ({len(wins)})',
            marker_color='#2ecc71', opacity=0.75,
        ))
    if losses:
        fig_profit.add_trace(go.Histogram(
            x=losses, name=f'亏损 ({len(losses)})',
            marker_color='#e74c3c', opacity=0.75,
        ))
    if flats:
        fig_profit.add_trace(go.Histogram(
            x=flats, name=f'平盘 ({len(flats)})',
            marker_color='#f39c12', opacity=0.75,
        ))
    fig_profit.add_vline(x=0, line_dash='dash', line_color='#95a5a6')
    fig_profit.update_layout(
        title='盈亏金额分布',
        xaxis_title='盈亏 ($)', yaxis_title='笔数',
        barmode='overlay', height=300,
        margin=dict(l=50, r=20, t=50, b=40),
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='center', x=0.5),
    )

    # ---- 持仓时长分布 ----
    fig_hold = go.Figure()
    if hold_hours:
        fig_hold.add_trace(go.Histogram(
            x=hold_hours, name='持仓',
            marker_color='#3498db', opacity=0.85,
        ))
    fig_hold.update_layout(
        title='持仓时长分布',
        xaxis_title='持仓 (小时)', yaxis_title='笔数',
        height=300, showlegend=False,
        margin=dict(l=50, r=20, t=50, b=40),
    )

    return html.Div([
        html.H5("📊 交易分布", style={'margin': '20px 0 10px 0'}),
        html.Div([
            html.Div(
                dcc.Graph(figure=fig_profit, style={'height': '300px'}),
                style={'flex': '1', 'minWidth': 0},
            ),
            html.Div(
                dcc.Graph(figure=fig_hold, style={'height': '300px'}),
                style={'flex': '1', 'minWidth': 0},
            ),
        ], style={'display': 'flex', 'gap': '10px',
                  'flexWrap': 'nowrap'}),
    ])