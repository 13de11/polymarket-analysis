"""
首页 - 项目概览
"""
from dash import html

def layout():
    return html.Div([
        html.H2("🏠 欢迎使用 Polymarket 数据分析平台"),
        html.Hr(),
        html.Div([
            html.P("本平台提供以下功能模块：", style={'fontSize': '16px'}),
            html.Ul([
                html.Li([
                    html.Strong("📈 价格-推文分析"),
                    html.Span("：三轴图展示价格、每小时推文数、累计推文数的趋势关系")
                ], style={'margin': '8px 0'}),
                html.Li([
                    html.Strong("📈 预测回测"),
                    html.Span("：基于推文热度的方向预测与模拟交易回测系统")
                ], style={'margin': '8px 0'}),
            ], style={'fontSize': '15px', 'lineHeight': '1.8'}),
        ], style={'padding': '20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),
        html.Hr(),
        html.Div([
            html.P("📊 数据库状态: 已连接", style={'color': '#28a745'}),
            html.P("📂 数据来源: Polymarket + Twitter", style={'color': '#6c757d'}),
            html.P(f"🕐 最后更新: 2026-08-20", style={'color': '#6c757d'}),
        ], style={'fontSize': '14px'})
    ])