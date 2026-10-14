# src/dash_app/pages/research/layout.py
"""
策略研究 - 页面布局

Phase C：取消左侧固定共享面板，全宽 tabs。
每个 tab 自包含配置区（comparison 用 cmp-*，sensitivity/batch 下一轮改）。
"""

from dash import html, dcc

from src.dash_app.pages.research.tabs.comparison import render_comparison_tab
from src.dash_app.pages.research.tabs.sensitivity import render_sensitivity_tab
from src.dash_app.pages.research.tabs.batch import render_batch_tab


def layout(global_params=None, series='7d'):
    return html.Div([
        html.Div([
            html.H2("🔬 策略研究", style={'marginBottom': 2}),
            html.P("参数对比与敏感性分析",
                   style={'color': '#6c757d', 'fontSize': '14px',
                          'marginTop': 0}),
        ], style={'marginBottom': 15}),

        dcc.Tabs(
            id='research-tabs', value='comparison',
            children=[
                dcc.Tab(label='📊 策略对比', value='comparison',
                        children=render_comparison_tab(
                            global_params=global_params, series=series)),
                dcc.Tab(label='📊 敏感性分析', value='sensitivity',
                        children=render_sensitivity_tab(
                            global_params=global_params, series=series)),
                dcc.Tab(label='📦 批量研究', value='batch',
                        children=render_batch_tab(
                            global_params=global_params, series=series)),
            ],
            style={'marginBottom': '15px'},
        ),

        # research-params-store 临时保留（sensitivity/batch 下一轮改自包含后删）
        dcc.Store(id='research-params-store', data={}),
    ], style={'padding': '10px 20px'})
