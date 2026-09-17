"""
策略研究 - 页面布局
"""

from dash import html, dcc

from src.dash_app.pages.research.filter_panel import create_research_panel
from src.dash_app.pages.research.tabs.comparison import render_comparison_tab
from src.dash_app.pages.research.tabs.sensitivity import render_sensitivity_tab


def layout():
    return html.Div([
        html.Div([
            html.H2("🔬 策略研究", style={'marginBottom': 2}),
            html.P("参数对比与敏感性分析",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        html.Div([
            # 左侧参数面板
            html.Div([
                create_research_panel()
            ], className='backtest-left', style={
                'width': '28%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'paddingRight': '20px',
                'boxSizing': 'border-box'
            }),

            # 右侧结果区
            html.Div([
                html.Div([
                    html.H4("📊 研究结果", style={'margin': 0, 'color': '#2c3e50'}),
                ], style={'borderBottom': '2px solid #6c5ce7', 'paddingBottom': '10px', 'marginBottom': '15px'}),

                dcc.Tabs(
                    id='research-tabs',
                    value='comparison',
                    children=[
                        dcc.Tab(label='📊 策略对比', value='comparison'),
                        dcc.Tab(label='📊 敏感性分析', value='sensitivity'),
                    ],
                    style={'marginBottom': '15px'}
                ),

                html.Div([
                    html.Div(
                        render_comparison_tab(),
                        id='research-tab-comparison',
                        style={'display': 'block'}
                    ),
                    html.Div(
                        render_sensitivity_tab(),
                        id='research-tab-sensitivity',
                        style={'display': 'none'}
                    ),
                ], style={'minHeight': '400px'}),

            ], className='backtest-right', style={
                'width': '70%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'boxSizing': 'border-box'
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),
    ], style={'padding': '10px 20px'})

from dash import callback, Output, Input

@callback(
    Output('research-tab-comparison', 'style'),
    Output('research-tab-sensitivity', 'style'),
    Input('research-tabs', 'value'),
)
def switch_research_tab(tab):
    if tab == 'comparison':
        return {'display': 'block'}, {'display': 'none'}
    return {'display': 'none'}, {'display': 'block'}