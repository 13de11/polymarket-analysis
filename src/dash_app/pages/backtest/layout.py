"""
分析工作台 - 页面布局

Phase B：去掉左侧固定面板，全宽 tab，配置区由 render_tab_content 动态生成。
"""
from dash import html, dcc


def layout(global_params=None):
    return html.Div([

        html.Div([
            html.H2("📊 分析工作台", style={'marginBottom': 2}),
            html.P("信号预览 · 绩效回测 · 策略对比 · 敏感性 · 批量研究",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        # 全宽：tabs + content + stores
        html.Div([
            dcc.Tabs(
                id='backtest-tabs', value='preview',
                children=[
                    dcc.Tab(label='🔍 信号预览', value='preview'),
                    dcc.Tab(label='📊 绩效概览', value='overview'),
                    dcc.Tab(label='📋 交易明细', value='trades'),
                    dcc.Tab(label='📈 策略评估', value='evaluation'),
                    dcc.Tab(label='🔬 策略对比', value='comparison'),
                    dcc.Tab(label='📊 敏感性分析', value='sensitivity'),
                    dcc.Tab(label='📦 批量研究', value='batch'),
                ],
                style={'marginBottom': '15px'},
            ),
            html.P(id='backtest-status-text',
                   style={'fontSize': '12px', 'color': '#7f8c8d',
                          'margin': '0 0 10px 0'}),
            dcc.Loading(
                id='loading-backtest', type='default', color='#3498db',
                children=[html.Div(id='backtest-tab-content',
                                   style={'minHeight': '500px'})],
            ),
            dcc.Store(id='backtest-result-store', data={}),
            dcc.Store(id='research-params-store', data={}),
        ]),

    ], style={'padding': '10px 20px'})
