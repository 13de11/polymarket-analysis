import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dash import Dash, html, dcc, callback, Input, Output

app = Dash(__name__, suppress_callback_exceptions=True)

print("🔥🔥🔥 app_new.py 被加载了！🔥🔥🔥")

from src.dash_app.pages import price_tweet_analysis
from src.dash_app.pages import home
from src.dash_app.pages import insights_dashboard
from src.dash_app.pages import prediction_backtest

app.layout = html.Div([
    dcc.Location(id='url'),
    html.Div([

        html.Div([
            html.H3("📊 导航", style={'marginTop': 0, 'padding': '15px 0'}),

            html.Div([
                html.Label("选择系列:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                dcc.RadioItems(
                    id='series-selector',
                    options=[
                        {'label': ' 7天事件', 'value': '7d'},
                        {'label': ' 48小时事件', 'value': '48h'},
                    ],
                    value='7d',
                    inline=True,
                    style={'marginTop': '6px', 'fontSize': '13px'}
                ),
                html.Div(
                    "当前显示: 7天推文事件",
                    id='series-label',
                    style={'fontSize': '11px', 'color': '#6c757d', 'marginTop': '4px'}
                ),
            ], style={
                'padding': '10px 12px',
                'backgroundColor': '#f1f3f5',
                'borderRadius': '6px',
                'marginBottom': '15px'
            }),

            html.Ul([
                html.Li(dcc.Link("🏠 首页", href="/"), style={'listStyle': 'none', 'padding': '8px 0'}),
                html.Li(dcc.Link("📈 价格-推文分析", href="/analysis"), style={'listStyle': 'none', 'padding': '8px 0'}),
                html.Li(dcc.Link("📊 数据分析中心", href="/insights"), style={'listStyle': 'none', 'padding': '8px 0'}),
                html.Li(dcc.Link("📈 预测回测", href="/backtest"), style={'listStyle': 'none', 'padding': '8px 0'}),
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

        html.Div([
            html.H1("📊 Polymarket 数据分析平台", style={'textAlign': 'center', 'padding': '10px 0', 'margin': 0}),
            html.Hr(style={'margin': '10px 0'}),
            html.Div(id='page-content', style={'padding': '20px'})
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

@callback(
    Output('series-label', 'children'),
    Input('series-selector', 'value')
)
def update_series_label(series):
    print(f"✅✅✅ 系列切换成功！值: {series} ✅✅✅")
    labels = {'7d': '当前显示: 7天推文事件', '48h': '当前显示: 48小时推文事件'}
    return labels.get(series, '当前显示: 7天推文事件')

@callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    print(f"📄 渲染页面: {pathname}")
    if pathname == '/analysis':
        return price_tweet_analysis.layout()
    elif pathname == '/insights':
        return insights_dashboard.layout()
    elif pathname == '/backtest':
        return prediction_backtest.layout()
    else:
        return home.layout()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)