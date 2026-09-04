import sys
import os

# 只添加项目根目录，不添加 src
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

import dash
from dash import Dash, html, dcc

app = Dash(__name__, use_pages=False, suppress_callback_exceptions=True)
server = app.server

# ========== 手动注册所有页面 ==========
from src.dash_app.pages import home
from src.dash_app.pages import price_tweet_analysis
from src.dash_app.pages import prediction_backtest
from src.dash_app.pages import insights_dashboard

app.layout = html.Div([
    dcc.Location(id='url'),
    html.Div([
        # 左侧导航
        html.Div([
            html.H3("📊 导航", style={'marginTop': 0, 'padding': '15px 0'}),
            html.Ul([
                html.Li(dcc.Link("🏠 首页", href="/"), style={'listStyle': 'none', 'padding': '8px 0'}),
                html.Li(dcc.Link("📈 价格-推文分析", href="/analysis"), style={'listStyle': 'none', 'padding': '8px 0'}),
                html.Li(dcc.Link("📊 数据分析中心", href="/insights"), style={'listStyle': 'none', 'padding': '8px 0'}),  # 新增
                html.Li(dcc.Link("📈 预测回测", href="/backtest"), style={'listStyle': 'none', 'padding': '8px 0', 'fontWeight': 'bold'}),
            ], style={'padding': 0, 'margin': 0})
        ], style={
            'width': '220px',
            'backgroundColor': '#f8f9fa',
            'padding': '20px 15px',
            'minHeight': '100vh',
            'boxSizing': 'border-box',
            'borderRight': '1px solid #dee2e6',
            'flexShrink': 0
        }),
        # 右侧内容
        html.Div([
            html.H1("📊 Polymarket 数据分析平台", style={'textAlign': 'center', 'padding': '10px 0', 'margin': 0}),
            html.Hr(style={'margin': '10px 0'}),
            html.Div([
                # 根据 URL 渲染对应页面
                html.Div(id='page-content')
            ], style={'padding': '20px'})
        ], style={
            'flex': 1,
            'padding': '0 20px',
            'boxSizing': 'border-box',
            'overflow': 'auto'
        })
    ], style={
        'display': 'flex',
        'flexDirection': 'row',
        'minHeight': '100vh'
    })
])

# ========== 页面路由回调 ==========
@app.callback(
    dash.dependencies.Output('page-content', 'children'),
    dash.dependencies.Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/analysis':
        return price_tweet_analysis.layout()
    elif pathname == '/backtest':
        return prediction_backtest.layout()
    elif pathname == '/insights':  # 新增路由
        return insights_dashboard.layout()
    else:
        return home.layout()

# ========== 注册参数面板回调 ==========
from src.dash_app.pages.prediction_backtest import register_params_callbacks
register_params_callbacks(app)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8050)