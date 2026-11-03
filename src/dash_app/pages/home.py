"""
首页 - 项目概览
"""
import os
from datetime import datetime, timezone, timedelta
from dash import html, dcc, Input, Output, callback
from src.dash_app.utils.stats_loader import get_overview_stats
from src.dash_app.utils.data_loader import run_query

try:
    from config import LIGHT_DB_PATH
except ImportError:
    LIGHT_DB_PATH = None


def _feature_card(title, desc, href):
    """功能卡片（可点击跳转）"""
    return dcc.Link([
        html.Div([
            html.H4(title, style={'margin': '0 0 8px 0'}),
            html.P(desc, style={'fontSize': '13px', 'color': '#6c757d',
                                'margin': 0})
        ], style={
            'padding': '15px',
            'backgroundColor': '#f8f9fa',
            'borderRadius': '8px',
            'border': '1px solid #e9ecef',
            'height': '100%',
            'boxSizing': 'border-box'
        })
    ], href=href, style={
        'flex': '1',
        'minWidth': '220px',
        'textDecoration': 'none',
        'color': 'inherit',
        'cursor': 'pointer'
    })


def _build_kpi_cards(series='7d'):
    """构建首页 KPI 卡片（响应 series）"""
    try:
        stats = get_overview_stats(series)
    except Exception as e:
        print(f"首页 KPI 加载失败: {e}")
        return html.Div("暂无数据", style={'color': '#6c757d'})

    def card(icon, label, value):
        return html.Div([
            html.Div(f"{icon} {label}",
                     style={'fontSize': '12px', 'color': '#6c757d'}),
            html.Div(str(value), style={'fontSize': '24px',
                                        'fontWeight': 'bold',
                                        'marginTop': '4px'})
        ], style={
            'textAlign': 'center',
            'padding': '15px',
            'backgroundColor': 'white',
            'borderRadius': '6px',
            'boxShadow': '0 1px 3px rgba(0,0,0,0.1)',
            'minWidth': '140px',
            'flex': '1'
        })

    return html.Div([
        card("📅", "总事件", stats.get('total_events', 0)),
        card("🐦", "总推文", f"{stats.get('total_tweets', 0):,}"),
        card("🎯", "命中市场", stats.get('hit_count', 0)),
        card("🔥", "最热区间", stats.get('hot_range_label', '—')),
    ], style={
        'display': 'flex',
        'flexWrap': 'wrap',
        'gap': '15px'
    })


def _get_db_last_modified():
    """数据新鲜度：价格/推文表的最新时间戳（北京时间）

    注意：不能用数据库文件 mtime——应用跑在 WAL 模式下，写入先落 -wal 文件，
    主库文件的 mtime 只在 checkpoint 时更新，会长期显示旧时间（假象）。
    """
    try:
        df = run_query("""
            SELECT MAX(ts) AS max_ts FROM (
                SELECT MAX(hour_start_utc) AS ts FROM price_hourly
                UNION ALL
                SELECT MAX(timestamp_unix_utc) AS ts FROM tweet_hourly
            )
        """)
        ts = int(df['max_ts'].iloc[0])
        bj = datetime.fromtimestamp(ts, tz=timezone.utc) + timedelta(hours=8)
        return bj.strftime('%Y-%m-%d %H:%M') + ' (北京时间)'
    except Exception:
        return '未知'


def layout():
    return html.Div([
        html.H2("🏠 欢迎使用 Polymarket 数据分析平台"),
        html.Hr(),

        # ---- KPI 数据概览 ----
        html.Div([
            html.H4(id='home-kpi-title', style={'marginBottom': '15px'}),
            html.Div(id='home-kpi-cards'),
        ]),

        # ---- 功能入口卡片 ----
        html.Div([
            html.P("本平台提供以下功能模块：",
                   style={'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div([
                _feature_card(
                    "📈 价格-推文分析",
                    "查看单个事件内各市场随推文的价格变化趋势，"
                    "识别命中市场与推文密度的关系。",
                    '/analysis'
                ),
                _feature_card(
                    "📊 数据分析中心",
                    "历史事件的命中模式、推文热度图谱、"
                    "区间存活时长等聚合分析。",
                    '/insights'
                ),
                _feature_card(
                    "📈 预测回测",
                    "单事件信号评价：信号预览、绩效概览、"
                    "交易明细、策略评估。",
                    '/backtest'
                ),
                _feature_card(
                    "🔬 策略研究",
                    "多策略对比、参数敏感性扫描、"
                    "多事件/多子市场批量研究、实验保存。",
                    '/research'
                ),
            ], style={'display': 'flex', 'flexWrap': 'wrap',
                      'gap': '15px'}),
        ], style={'padding': '20px', 'backgroundColor': 'white',
                  'borderRadius': '8px',
                  'border': '1px solid #e9ecef'}),

        html.Hr(),

        # ---- 状态信息 ----
        html.Div([
            html.P("📊 数据库状态: 已连接",
                   style={'color': '#28a745', 'margin': '4px 0'}),
            html.P("📂 数据来源: Polymarket + Twitter",
                   style={'color': '#6c757d', 'margin': '4px 0'}),
            html.P(f"🕐 数据最新: {_get_db_last_modified()}",
                   style={'color': '#6c757d', 'margin': '4px 0'}),
        ], style={'fontSize': '14px'})
    ])

from dash import Input, Output, callback, no_update


@callback(
    Output('home-kpi-cards', 'children'),
    Output('home-kpi-title', 'children'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
)
def _update_home_kpi(series, pathname):
    if pathname not in ('/', None):
        return no_update, no_update
    series = series or '7d'
    title = f"📊 平台数据概览（{'7天' if series == '7d' else '48小时'}事件）"
    return _build_kpi_cards(series), title