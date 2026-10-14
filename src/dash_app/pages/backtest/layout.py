"""
预测回测系统 - 页面布局

回退到左右布局：左侧参数面板 + 右侧 4 tab。
param-* 组件在左侧常驻，不随 tab 切换销毁。
"""
from dash import html, dcc

from src.dash_app.pages.shared.params_panel import create_shared_panel


def layout(global_params=None):
    return html.Div([

        html.Div([
            html.H2("📈 预测回测", style={'marginBottom': 2}),
            html.P("基于推文热度的方向预测与模拟交易回测",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        html.Div([
            # 左侧：参数面板 + 运行按钮
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
                html.Div("点击「运行回测」跑完整回测，刷新所有 Tab",
                         style={'fontSize': '11px', 'color': '#7f8c8d',
                                'textAlign': 'center'}),
            ], className='backtest-left', style={
                'width': '28%', 'display': 'inline-block',
                'verticalAlign': 'top', 'paddingRight': '20px',
                'boxSizing': 'border-box',
            }),

            # 右侧：4 tab + content + stores
            html.Div([
                html.Div([
                    html.H4("📊 回测结果", style={'margin': 0, 'color': '#2c3e50'}),
                    html.P(id='backtest-status-text',
                           style={'fontSize': '12px', 'color': '#7f8c8d',
                                  'margin': '4px 0 0 0'}),
                ], style={'borderBottom': '2px solid #3498db',
                          'paddingBottom': '10px', 'marginBottom': '15px'}),
                dcc.Tabs(
                    id='backtest-tabs', value='preview',
                    children=[
                        dcc.Tab(label='🔍 信号预览', value='preview'),
                        dcc.Tab(label='📊 绩效概览', value='overview'),
                        dcc.Tab(label='📋 交易明细', value='trades'),
                        dcc.Tab(label='📈 策略评估', value='evaluation'),
                    ],
                    style={'marginBottom': '15px'},
                ),
                dcc.Loading(
                    id='loading-backtest', type='default', color='#3498db',
                    children=[html.Div(id='backtest-tab-content',
                                       style={'minHeight': '400px'})],
                ),
                dcc.Store(id='backtest-result-store', data={}),
            ], className='backtest-right', style={
                'width': '70%', 'display': 'inline-block',
                'verticalAlign': 'top', 'boxSizing': 'border-box',
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),

    ], style={'padding': '10px 20px'})
