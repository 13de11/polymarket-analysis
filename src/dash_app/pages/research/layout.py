"""
策略研究 - 页面布局

Phase 3：左侧改用共享参数面板 create_shared_panel（param-* 前缀），
与 /backtest 页复用同一套组件 ID 和事件/市场联动回调。
"""

from dash import html, dcc

from src.dash_app.pages.shared.params_panel import create_shared_panel
from src.dash_app.pages.research.tabs.comparison import render_comparison_tab
from src.dash_app.pages.research.tabs.sensitivity import render_sensitivity_tab
from src.dash_app.pages.research.tabs.batch import render_batch_tab


def layout(global_params=None):
    return html.Div([
        html.Div([
            html.H2("🔬 策略研究", style={'marginBottom': 2}),
            html.P("参数对比与敏感性分析",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        html.Div([
            # 左侧：共享参数面板 + research-params-store
            html.Div([
                create_shared_panel(global_params=global_params),
                dcc.Store(id='research-params-store', data={}),
            ], className='backtest-left', style={
                'width': '28%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'paddingRight': '20px',
                'boxSizing': 'border-box',
            }),

            # 右侧：结果区
            html.Div([
                html.Div([
                    html.H4("📊 研究结果", style={'margin': 0, 'color': '#2c3e50'}),
                ], style={'borderBottom': '2px solid #6c5ce7', 'paddingBottom': '10px', 'marginBottom': '15px'}),

                dcc.Tabs(
                    id='research-tabs', value='comparison',
                    children=[
                        dcc.Tab(label='📊 策略对比', value='comparison',
                                children=render_comparison_tab()),
                        dcc.Tab(label='📊 敏感性分析', value='sensitivity',
                                children=render_sensitivity_tab()),
                        dcc.Tab(label='📦 批量研究', value='batch',
                                children=render_batch_tab()),
                    ],
                    style={'marginBottom': '15px'},
                ),

            ], className='backtest-right', style={
                'width': '70%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'boxSizing': 'border-box',
                'minHeight': '400px',
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),
    ], style={'padding': '10px 20px'})
