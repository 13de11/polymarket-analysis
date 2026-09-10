import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from dash import Dash, html, dcc, callback, Input, Output

app = Dash(__name__, suppress_callback_exceptions=True)  # ← 移除 routes_pathname_prefix
server = app.server

print("🔥🔥🔥 app.py 被加载了！🔥🔥🔥")

# 导入页面
from src.dash_app.pages import price_tweet_analysis

app.layout = html.Div([
    html.Div([
        html.Label("选择系列:", style={'fontWeight': 'bold'}),
        dcc.RadioItems(
            id='series-selector',
            options=[
                {'label': ' 7天事件', 'value': '7d'},
                {'label': ' 48小时事件', 'value': '48h'},
            ],
            value='7d',
            inline=True
        ),
        html.Div(id='series-label', children='当前显示: 7天'),
    ], style={'padding': '10px', 'backgroundColor': '#f1f3f5', 'marginBottom': '10px'}),
    html.Div(id='page-content', children='请访问 /analysis'),
])

@callback(
    Output('series-label', 'children'),
    Input('series-selector', 'value')
)
def update_series_label(series):
    print(f"✅✅✅ 系列切换成功！值: {series} ✅✅✅")
    return f'当前显示: {series}'

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)