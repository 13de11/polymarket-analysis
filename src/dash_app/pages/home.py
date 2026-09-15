"""
首页 - 项目概览
"""
from dash import html, dcc
from datetime import datetime


def _feature_card(title, desc, href):
    """功能卡片（可点击跳转）"""
    return dcc.Link([
        html.Div([
            html.H4(title, style={'margin': '0 0 8px 0'}),
            html.P(desc, style={'fontSize': '13px', 'color': '#6c757d', 'margin': 0})
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


def layout():
    return html.Div([
        html.H2("🏠 欢迎使用 Polymarket 数据分析平台"),
        html.Hr(),

        # ---- 功能入口卡片 ----
        html.Div([
            html.P("本平台提供以下功能模块：", style={'fontSize': '16px', 'marginBottom': '15px'}),
            html.Div([
                _feature_card(
                    "📈 价格-推文分析",
                    "查看单个事件内各市场随推文的价格变化趋势，识别命中市场与推文密度的关系。",
                    '/analysis'
                ),
                _feature_card(
                    "📊 数据分析中心",
                    "历史事件的命中模式、推文热度图谱、区间存活时长等聚合分析。",
                    '/insights'
                ),
                _feature_card(
                    "📈 预测回测",
                    "基于推文热度的方向预测策略，支持参数调优、策略对比和敏感性分析。",
                    '/backtest'
                ),
            ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '15px'}),
        ], style={'padding': '20px', 'backgroundColor': 'white', 'borderRadius': '8px', 'border': '1px solid #e9ecef'}),

        html.Hr(),

        # ---- 状态信息 ----
        html.Div([
            html.P("📊 数据库状态: 已连接", style={'color': '#28a745', 'margin': '4px 0'}),
            html.P("📂 数据来源: Polymarket + Twitter", style={'color': '#6c757d', 'margin': '4px 0'}),
            html.P(f"🕐 最后更新: {datetime.now().strftime('%Y-%m-%d')}", style={'color': '#6c757d', 'margin': '4px 0'}),
        ], style={'fontSize': '14px'})
    ])