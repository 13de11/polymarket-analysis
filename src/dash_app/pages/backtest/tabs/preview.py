"""
信号预览 Tab
- 生成信号预览图 + 统计卡片
- 渲染预览 Tab
"""

from dash import html, dcc
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from src.dash_app.utils.data_loader import (
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_gamestart_label,
    get_window_start_timestamp,
)
from src.dash_app.utils.signal.generator import DirectionSignalGenerator


def render_preview_tab(params, series='7d'):
    """渲染信号预览 Tab，返回 (content, stats)"""
    if not params or not params.get('market_id'):
        return html.Div([
            html.P("📊 信号预览图将在此显示",
                   style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
            html.P("请选择事件和市场，点击「更新信号预览」",
                   style={'color': '#6c757d', 'textAlign': 'center'})
        ]),{'total_signals': 0}

    fig, stats = generate_signal_preview(params, series)
    stats_cards = stats.get('_cards', html.Div("无统计数据"))

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '500px'}),
        html.Div(stats_cards, style={
            'display': 'flex',
            'flexWrap': 'wrap',
            'gap': '15px',
            'padding': '15px',
            'backgroundColor': '#f8f9fa',
            'borderRadius': '6px',
            'marginTop': '15px'
        })
    ]), stats


def generate_signal_preview(params, series='7d'):
    """生成信号预览图表和统计"""
    market_id = params.get('market_id')
    price_type = params.get('price_type', 'price_last')
    event_id = params.get('event_id')

    price_df = get_price_data_for_market(market_id)
    if price_df.empty:
        return go.Figure(), {'total_signals': 0}

    tweet_df = get_tweet_data_for_event(event_id)

    combined = pd.merge(price_df, tweet_df, on='datetime_utc', how='left')
    combined['tweet_count'] = combined['tweet_count'].fillna(0)
    combined = combined.sort_values('datetime_utc').reset_index(drop=True)

    backtest_range = params.get('backtest_range', 'full')
    if backtest_range in ['pre', 'post']:
        gamestart_label = get_event_gamestart_label(event_id)
        if gamestart_label:
            gamestart_dt = pd.to_datetime(gamestart_label, utc=True)
            gamestart_ts = int(gamestart_dt.timestamp())
            if backtest_range == 'pre':
                combined = combined[combined['hour_start_utc'] < gamestart_ts]
            else:
                combined = combined[combined['hour_start_utc'] >= gamestart_ts]
            if combined.empty:
                return go.Figure(), {'total_signals': 0}

    if len(combined) < 10:
        return go.Figure(), {'total_signals': 0}

    median = get_market_median(market_id)
    remaining_hours = get_event_remaining_hours(event_id)

    window_mode = params.get('window_mode', 'rolling')
    window_param = params.get('window_param', 168)
    window_start = params.get('window_start', None)
    window_start_ts = None
    if window_mode == 'expanding' and window_start:
        window_start_ts = get_window_start_timestamp(event_id, window_start)

    signal_params = {
        'capacity': params.get('capacity', 0),
        'price_threshold': params.get('price_threshold', 0.005),
        'distance_threshold': params.get('distance_threshold', 1.5),
        'inertia_hours': params.get('inertia', 6),
        'momentum_enable': params.get('momentum_enable', True),
        'momentum_coef': params.get('momentum_coef', 0.10),
        'signal_mode': params.get('signal_mode', 'full'),
        'median': median,
        'remaining_hours': remaining_hours,
        'window_mode': window_mode,
        'window_param': window_param,
        'window_start': window_start,
        'window_start_ts': window_start_ts,
    }

    generator = DirectionSignalGenerator(signal_params)
    price_col = price_type
    price_df_renamed = combined[['datetime_utc', price_col]].rename(
        columns={'datetime_utc': 'timestamp', price_col: 'price'}
    )
    tweet_df_renamed = combined[['datetime_utc', 'tweet_count']].rename(
        columns={'datetime_utc': 'timestamp'}
    )
    signal_df = generator.generate_signals(price_df_renamed, tweet_df_renamed)

    # 统计基于 start 过滤（不重复计数）
    stats_df = generator.apply_display_filter(signal_df, 'start')
    stats = generator.get_signal_stats(stats_df)

    # 显示基于用户选模式
    display_df = generator.apply_display_filter(signal_df, params.get('signal_mode', 'full'))

    # ---- 构建图表 ----
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    fig.add_trace(
        go.Scatter(
            x=signal_df['timestamp'],
            y=signal_df['price'],
            name='目标价格',
            line=dict(color='#e74c3c', width=2),
            hovertemplate='价格: %{y:.4f}<extra></extra>'
        ),
        row=1, col=1, secondary_y=False
    )

    fig.add_trace(
        go.Bar(
            x=signal_df['timestamp'],
            y=signal_df['tweet_count'],
            name='推文数',
            marker=dict(color='rgba(255, 100, 50, 0.3)'),
            yaxis='y2',
            hovertemplate='推文: %{y}<extra></extra>'
        ),
        row=1, col=1, secondary_y=True
    )

    # 信号箭头
    for idx, row in display_df.iterrows():
        signal = row['signal']
        if signal in ['↑', '↓', '→']:
            color = '#2ecc71' if signal == '↑' else '#e74c3c' if signal == '↓' else '#95a5a6'
            symbol = '▲' if signal == '↑' else '▼' if signal == '↓' else '●'
            fig.add_annotation(
                x=row['timestamp'],
                y=row['price'],
                text=symbol,
                showarrow=False,
                font=dict(size=15, color=color),
                row=1, col=1,
                yshift=10 if signal == '↑' else -10 if signal == '↓' else 0
            )

    # 权益曲线（预览简化）
    if len(signal_df) > 0:
        equity = 100 + (signal_df['price'] / signal_df['price'].iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=signal_df['timestamp'],
                y=equity,
                name='权益曲线(模拟)',
                line=dict(color='#2c3e50', width=2),
                hovertemplate='权益: %{y:.2f}<extra></extra>'
            ),
            row=2, col=1
        )
        max_equity = equity.cummax()
        drawdown = (equity - max_equity) / max_equity * 100
        fig.add_trace(
            go.Scatter(
                x=signal_df['timestamp'],
                y=drawdown,
                name='回撤%',
                fill='tozeroy',
                line=dict(color='rgba(231, 76, 60, 0.5)', width=1),
                hovertemplate='回撤: %{y:.2f}%<extra></extra>'
            ),
            row=2, col=1
        )

    fig.update_layout(
        title=dict(text="信号预览 - 价格 + 推文 + 方向信号", font=dict(size=14)),
        legend=dict(orientation='h', yanchor='top', y=1.02, xanchor='center', x=0.5),
        hovermode='x unified',
        height=600,
        margin=dict(l=50, r=50, t=60, b=50)
    )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格", secondary_y=False, row=1, col=1)
    fig.update_yaxes(title_text="推文数", secondary_y=True, row=1, col=1)
    fig.update_yaxes(title_text="权益", row=2, col=1)

    # 统计卡片
    stats_cards = html.Div([
        html.Div([
            html.Strong("📊 信号总数"),
            html.Div(str(stats.get('total_signals', 0)), style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("▲ 看涨"),
            html.Div(str(stats.get('up_count', 0)), style={'fontSize': '20px', 'color': '#2ecc71', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("▼ 看跌"),
            html.Div(str(stats.get('down_count', 0)), style={'fontSize': '20px', 'color': '#e74c3c', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("➔ 看平"),
            html.Div(str(stats.get('flat_count', 0)), style={'fontSize': '20px', 'color': '#95a5a6', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("🎯 方向准确率"),
            html.Div(f"{stats.get('overall_accuracy', 0)*100:.1f}%", style={'fontSize': '20px', 'color': '#3498db', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '120px'}),
        html.Div([
            html.Strong("▲ 上涨准确率"),
            html.Div(f"{stats.get('up_accuracy', 0)*100:.1f}%", style={'fontSize': '16px', 'color': '#2ecc71'})
        ], style={'textAlign': 'center', 'minWidth': '100px'}),
        html.Div([
            html.Strong("▼ 下跌准确率"),
            html.Div(f"{stats.get('down_accuracy', 0)*100:.1f}%", style={'fontSize': '16px', 'color': '#e74c3c'})
        ], style={'textAlign': 'center', 'minWidth': '100px'}),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '20px', 'justifyContent': 'center'})

    stats['_cards'] = stats_cards
    return fig, stats