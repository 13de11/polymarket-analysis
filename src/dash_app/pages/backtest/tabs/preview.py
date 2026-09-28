# src/dash_app/pages/backtest/tabs/preview.py
"""
信号预览 Tab
- 主图：价格 + 推文 + 方向信号 + 中位数
- 副图：估算总量 + 中位数参考
- 统计卡片
"""

from dash import html, dcc
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src.dash_app.utils.backtest.runner import build_signal_context


def render_preview_tab(params, series='7d'):
    """渲染信号预览 Tab，返回 (content, stats)"""
    if not params or not params.get('market_id'):
        return html.Div([
            html.P("📊 信号预览图将在此显示",
                   style={'color': '#6c757d', 'textAlign': 'center',
                          'padding': '40px 0'}),
            html.P("请选择事件和市场，点击「更新信号预览」",
                   style={'color': '#6c757d', 'textAlign': 'center'})
        ]), {'total_signals': 0}

    fig, stats = generate_signal_preview(params, series)
    stats_cards = stats.get('_cards', html.Div("无统计数据"))

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '600px'}),
        html.Div(stats_cards, style={
            'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px',
            'padding': '15px', 'backgroundColor': '#f8f9fa',
            'borderRadius': '6px', 'marginTop': '15px',
        }),
    ]), stats


def generate_signal_preview(params, series='7d'):
    """生成信号预览图表和统计"""
    ctx = build_signal_context(params)
    if ctx is None:
        return go.Figure(), {'total_signals': 0}

    signal_df = ctx['signal_df']
    generator = ctx['generator']
    median = ctx['median']

    stats_df = generator.apply_display_filter(signal_df, 'start')
    stats = generator.get_signal_stats(stats_df)
    display_df = generator.apply_display_filter(
        signal_df, params.get('signal_mode', 'full'))

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.08, row_heights=[0.65, 0.35],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
    )

    # ---- 上图：价格 ----
    fig.add_trace(go.Scatter(
        x=signal_df['timestamp'], y=signal_df['price'],
        name='目标价格', line=dict(color='#e74c3c', width=2),
        hovertemplate='价格: %{y:.4f}<extra></extra>',
    ), row=1, col=1, secondary_y=False)

    # ---- 上图：推文柱 ----
    fig.add_trace(go.Bar(
        x=signal_df['timestamp'], y=signal_df['tweet_count'],
        name='推文数',
        marker=dict(color='rgba(255, 100, 50, 0.3)'),
        hovertemplate='推文: %{y}<extra></extra>',
    ), row=1, col=1, secondary_y=True)


    # ---- 信号散点（一次加，不用循环 annotation）----
    up_df = display_df[display_df['signal'] == '↑']
    down_df = display_df[display_df['signal'] == '↓']
    flat_df = display_df[display_df['signal'] == '→']

    if not up_df.empty:
        fig.add_trace(go.Scatter(
            x=up_df['timestamp'], y=up_df['price'],
            mode='markers', name='↑ 看涨',
            marker=dict(symbol='triangle-up', size=10, color='#2ecc71'),
            hovertemplate='↑ %{x}<br>价格: %{y:.4f}<extra></extra>',
        ), row=1, col=1, secondary_y=False)

    if not down_df.empty:
        fig.add_trace(go.Scatter(
            x=down_df['timestamp'], y=down_df['price'],
            mode='markers', name='↓ 看跌',
            marker=dict(symbol='triangle-down', size=10, color='#e74c3c'),
            hovertemplate='↓ %{x}<br>价格: %{y:.4f}<extra></extra>',
        ), row=1, col=1, secondary_y=False)

    if not flat_df.empty:
        fig.add_trace(go.Scatter(
            x=flat_df['timestamp'], y=flat_df['price'],
            mode='markers', name='→ 看平',
            marker=dict(symbol='circle', size=5, color='#95a5a6'),
            hovertemplate='→ %{x}<br>价格: %{y:.4f}<extra></extra>',
        ), row=1, col=1, secondary_y=False)

    # ---- 下图：估算总量 vs 实际累计推文 ----
    if 'total_estimate' in signal_df.columns:
        fig.add_trace(go.Scatter(
            x=signal_df['timestamp'], y=signal_df['total_estimate'],
            name='估算总量 (avg_rate × 剩余小时)',
            line=dict(color='#8e44ad', width=2),
            hovertemplate='估算: %{y:.0f}<extra></extra>',
        ), row=2, col=1)

        cum_tweets = signal_df['tweet_count'].cumsum()
        fig.add_trace(go.Scatter(
            x=signal_df['timestamp'], y=cum_tweets,
            name='实际累计推文',
            line=dict(color='#f39c12', width=2),
            hovertemplate='累计推文: %{y:.0f}<extra></extra>',
        ), row=2, col=1)

        fig.add_hline(
            y=median, line_dash='dash', line_color='#3498db',
            annotation_text=f"中位数 {median:.1f}",
            annotation_position='right',
            row=2, col=1,
        )

    fig.update_layout(
        title=dict(text="信号预览 - 价格 + 信号 (上) / 估算总量 vs 实际累计推文 (下)",
                   font=dict(size=14)),
        legend=dict(orientation='h', yanchor='top', y=1.02,
                    xanchor='center', x=0.5),
        hovermode='x unified', height=600,
        margin=dict(l=50, r=50, t=80, b=50),
    )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格", secondary_y=False, row=1, col=1)
    fig.update_yaxes(title_text="推文数", secondary_y=True, row=1, col=1)
    fig.update_yaxes(title_text="推文总量", row=2, col=1)

    # ---- 统计卡片 ----
    stats_cards = html.Div([
        _stat_card("📊 信号总数", str(stats.get('total_signals', 0)), '#2c3e50'),
        _stat_card("▲ 看涨", str(stats.get('up_count', 0)), '#2ecc71'),
        _stat_card("▼ 看跌", str(stats.get('down_count', 0)), '#e74c3c'),
        _stat_card("→ 看平", str(stats.get('flat_count', 0)), '#95a5a6'),
        _stat_card("🎯 方向准确率",
                   f"{stats.get('overall_accuracy', 0) * 100:.1f}%",
                   '#3498db', big=True),
        _stat_card("▲ 上涨准确率",
                   f"{stats.get('up_accuracy', 0) * 100:.1f}%", '#2ecc71'),
        _stat_card("▼ 下跌准确率",
                   f"{stats.get('down_accuracy', 0) * 100:.1f}%", '#e74c3c'),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '20px',
              'justifyContent': 'center'})

    stats['_cards'] = stats_cards
    return fig, stats


def _stat_card(label, value, color, big=False):
    return html.Div([
        html.Strong(label, style={'fontSize': '12px'}),
        html.Div(value, style={
            'fontSize': '20px' if big else '18px',
            'color': color, 'fontWeight': 'bold',
        }),
    ], style={'textAlign': 'center', 'minWidth': '90px'})