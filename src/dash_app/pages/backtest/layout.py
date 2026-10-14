"""
分析工作台 - 页面布局

Phase B 修订：配置面板在页面顶部可折叠区（html.Details），
backtest tab 只显示只读摘要 + 结果，research tab 显示各自专属控件。
配置面板的 param-* 组件常驻（不随 tab 切换销毁），联动回调无需 tab 触发。
"""
from dash import html, dcc

from src.dash_app.pages.shared.params_panel import create_shared_panel


def layout(global_params=None):
    return html.Div([

        html.Div([
            html.H2("📊 分析工作台", style={'marginBottom': 2}),
            html.P("信号预览 · 绩效回测 · 策略对比 · 敏感性 · 批量研究",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        # 可折叠配置面板（所有 tab 共享，配完可收起）
        html.Details([
            html.Summary("⚙️ 参数配置（点击展开/收起）",
                         style={'cursor': 'pointer', 'fontWeight': 'bold',
                                'fontSize': '14px', 'padding': '10px 15px',
                                'backgroundColor': '#e8f4fd', 'borderRadius': '6px',
                                'border': '1px solid #b8d4e8'}),
            html.Div([
                create_shared_panel(global_params=global_params),
                html.Div([
                    html.Button('🚀 运行回测', id='param-run-btn', n_clicks=0, style={
                        'width': '100%', 'padding': '10px',
                        'backgroundColor': '#28a745', 'color': 'white',
                        'border': 'none', 'borderRadius': '6px',
                        'fontSize': '14px', 'fontWeight': 'bold', 'cursor': 'pointer',
                    }),
                ], style={'display': 'flex', 'marginBottom': '8px'}),
                html.Div("配完点「运行回测」后可收起此区域，下方 tab 显示只读摘要 + 结果",
                         style={'fontSize': '11px', 'color': '#7f8c8d',
                                'textAlign': 'center'}),
            ], style={'marginTop': '10px'}),
        ], open=True, style={'marginBottom': '15px'}),

        # 全宽 tabs + content + stores
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
