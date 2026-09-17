"""
策略研究 - 敏感性分析 Tab
"""

from dash import html, dcc, Input, Output, State, callback
import plotly.graph_objects as go
from typing import Dict, Any
import numpy as np

from src.dash_app.utils.analysis.sensitivity import SensitivityAnalysis


def render_sensitivity_tab():
    """渲染敏感性分析 Tab UI"""
    return html.Div([
        html.Div([
            html.P("分析参数变化对回测结果的影响：", style={'fontSize': '14px'}),
            html.Div([
                html.Div([
                    html.Label("分析参数:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='research-sensitivity-param',
                        options=[
                            {'label': '价格阈值', 'value': 'price_threshold'},
                            {'label': '容差', 'value': 'capacity'},
                            {'label': '距离阈值', 'value': 'distance_threshold'},
                            {'label': '惯性', 'value': 'inertia'},
                            {'label': '动量系数', 'value': 'momentum_coef'},
                        ],
                        value='price_threshold',
                        style={'width': '100%'}
                    ),
                ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                html.Div([
                    html.Label("追踪指标:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='research-sensitivity-metric',
                        options=[
                            {'label': '总收益率', 'value': 'total_return'},
                            {'label': '夏普比率', 'value': 'sharpe_ratio'},
                            {'label': '胜率', 'value': 'win_rate'},
                            {'label': '最大回撤', 'value': 'max_drawdown_pct'},
                        ],
                        value='total_return',
                        style={'width': '100%'}
                    ),
                ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                html.Div([
                    html.Label("参数范围:", style={'fontWeight': 'bold'}),
                    html.Div([
                        dcc.Input(
                            id='research-sensitivity-min',
                            type='number', value=0.001, step=0.001,
                            style={'width': '40%', 'display': 'inline-block', 'marginRight': '5px'}
                        ),
                        dcc.Input(
                            id='research-sensitivity-max',
                            type='number', value=0.02, step=0.001,
                            style={'width': '40%', 'display': 'inline-block'}
                        ),
                    ]),
                    html.P("步长: 自动计算 (10个点)",
                           style={'fontSize': '12px', 'color': '#6c757d', 'margin': '4px 0 0 0'})
                ], style={'width': '30%', 'display': 'inline-block'}),
            ], style={'marginBottom': '15px'}),
            html.Button(
                '🔬 运行分析',
                id='research-sensitivity-run-btn',
                n_clicks=0,
                style={
                    'padding': '10px 20px',
                    'backgroundColor': '#00b894',
                    'color': 'white',
                    'border': 'none',
                    'borderRadius': '6px',
                    'fontSize': '14px',
                    'fontWeight': 'bold',
                    'cursor': 'pointer'
                }
            ),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),
        html.Div(id='research-sensitivity-results', style={'marginTop': '15px'}),
    ])


def create_sensitivity_chart(result: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()

    results = result['results']
    param_name = result['param_name']
    metric_key = result['metric_key']

    valid = [r for r in results if r.get('metric_value') is not None]
    if not valid:
        return go.Figure()

    x_vals = [r['param_value'] for r in valid]
    y_vals = [r['metric_value'] for r in valid]

    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals, mode='lines+markers', name='敏感性曲线',
        line=dict(color='#00b894', width=2),
        marker=dict(size=8, color='#00b894'),
        hovertemplate='参数: %{x:.4f}<br>指标: %{y:.2f}<extra></extra>'
    ))

    if result.get('best_value'):
        best = result['best_value']
        fig.add_annotation(
            x=best['param_value'], y=best['metric_value'],
            text=f"最优 {best['param_value']:.4f}",
            showarrow=True, arrowhead=2, ax=20, ay=-30,
            font=dict(color='#00b894', size=12)
        )

    metric_labels = {
        'total_return': '总收益率 (%)',
        'sharpe_ratio': '夏普比率',
        'win_rate': '胜率 (%)',
        'max_drawdown_pct': '最大回撤 (%)',
    }

    fig.update_layout(
        title=f'参数敏感性分析: {param_name} → {metric_labels.get(metric_key, metric_key)}',
        xaxis_title=param_name,
        yaxis_title=metric_labels.get(metric_key, metric_key),
        hovermode='x',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )

    return fig


@callback(
    Output('research-sensitivity-results', 'children'),
    Input('research-sensitivity-run-btn', 'n_clicks'),
    State('research-params-store', 'data'),
    State('research-sensitivity-param', 'value'),
    State('research-sensitivity-metric', 'value'),
    State('research-sensitivity-min', 'value'),
    State('research-sensitivity-max', 'value'),
    State('series-selector', 'value'),
)
def run_research_sensitivity(n_clicks, params, param_name, metric_key, min_val, max_val, series):
    if n_clicks == 0:
        return html.Div()

    if not params or not params.get('market_id'):
        return html.Div("请先在左侧选择事件和市场")

    param_values = np.linspace(min_val, max_val, 10).tolist()
    param_values = [round(v, 4) for v in param_values]

    result = SensitivityAnalysis.run_sensitivity_analysis(
        params, param_name, param_values, metric_key, series
    )

    if not result or not result['results']:
        return html.Div("分析运行失败，请检查参数")

    fig = create_sensitivity_chart(result)
    best = result.get('best_value')

    best_info = html.Div()
    if best:
        best_info = html.Div([
            html.Strong("✅ 最优参数: "),
            html.Span(f"{param_name} = {best['param_value']:.4f}", style={'color': '#00b894', 'fontWeight': 'bold'}),
            html.Span(f" → {metric_key}: {best['metric_value']:.2f}", style={'fontWeight': 'bold'}),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5', 'borderRadius': '6px', 'marginTop': '10px'})

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '400px'}),
        best_info,
    ])