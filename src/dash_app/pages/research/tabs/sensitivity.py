# src/dash_app/pages/research/tabs/sensitivity.py
"""
策略研究 - 敏感性分析 Tab
- 单参数曲线 / 双参数网格
- 导出 CSV
"""

import pandas as pd
from dash import html, dcc, Input, Output, State, callback, no_update, ctx
import plotly.graph_objects as go
from src.dash_app.state.global_params import (
    merge as _gp_merge,
    window_type_to_engine as _wt2e,
)

from src.dash_app.utils.analysis.sensitivity import SensitivityAnalysis
from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, METRIC_SCHEMA,
    get_tunable_params, get_metric_options, fmt_metric, is_lower_better,
)
from src.dash_app.utils.research.serialize import to_python


def _param_options():
    return [{'label': PARAM_SCHEMA[k]['label'], 'value': k}
            for k in get_tunable_params()]


def render_sensitivity_tab():
    return html.Div([
        html.Div([
            html.P("单参数曲线 / 双参数网格。",
                   style={'fontSize': '13px', 'color': '#495057',
                          'marginBottom': '10px'}),

            dcc.RadioItems(
                id='research-sensitivity-mode',
                options=[{'label': ' 📈 单参数曲线', 'value': 'single'},
                         {'label': ' 🔥 双参数网格', 'value': 'grid'}],
                value='single', inline=True,
                style={'marginBottom': '12px', 'fontSize': '13px'},
            ),

            html.Div([
                html.Div([
                    html.Label('分析参数', style={'fontWeight': 'bold',
                                                  'fontSize': '13px'}),
                    dcc.Dropdown(id='research-sensitivity-param',
                                 options=_param_options(),
                                 value='price_threshold', clearable=False,
                                 style={'width': '100%'}),
                ], style={'width': '32%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('追踪指标', style={'fontWeight': 'bold',
                                                  'fontSize': '13px'}),
                    dcc.Dropdown(id='research-sensitivity-metric',
                                 options=get_metric_options(),
                                 value='total_return', clearable=False,
                                 style={'width': '100%'}),
                ], style={'width': '32%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('扫描点数', style={'fontWeight': 'bold',
                                                  'fontSize': '13px'}),
                    dcc.Input(id='research-sensitivity-npoints',
                              type='number', value=10, min=3, max=30, step=1,
                              style={'width': '80px', 'padding': '4px',
                                     'fontSize': '13px'}),
                ], style={'width': '28%', 'display': 'inline-block'}),
            ], id='research-sensitivity-single-controls'),

            html.Div([
                html.Div([
                    html.Label('X 参数', style={'fontWeight': 'bold',
                                                'fontSize': '13px'}),
                    dcc.Dropdown(id='research-grid-param-x',
                                 options=_param_options(),
                                 value='price_threshold', clearable=False,
                                 style={'width': '100%'}),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('Y 参数', style={'fontWeight': 'bold',
                                                'fontSize': '13px'}),
                    dcc.Dropdown(id='research-grid-param-y',
                                 options=_param_options(),
                                 value='capacity', clearable=False,
                                 style={'width': '100%'}),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('追踪指标', style={'fontWeight': 'bold',
                                                  'fontSize': '13px'}),
                    dcc.Dropdown(id='research-grid-metric',
                                 options=get_metric_options(),
                                 value='total_return', clearable=False,
                                 style={'width': '100%'}),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('网格大小', style={'fontWeight': 'bold',
                                                  'fontSize': '13px'}),
                    html.Div([
                        dcc.Input(id='research-grid-nx', type='number',
                                  value=5, min=3, max=10, step=1,
                                  style={'width': '50px', 'padding': '4px',
                                         'fontSize': '13px',
                                         'display': 'inline-block'}),
                        html.Span(' × ', style={'margin': '0 4px'}),
                        dcc.Input(id='research-grid-ny', type='number',
                                  value=5, min=3, max=10, step=1,
                                  style={'width': '50px', 'padding': '4px',
                                         'fontSize': '13px',
                                         'display': 'inline-block'}),
                    ]),
                ], style={'width': '24%', 'display': 'inline-block'}),
            ], id='research-sensitivity-grid-controls',
               style={'display': 'none'}),

            html.Div(id='research-sensitivity-range-hint', style={
                'fontSize': '12px', 'color': '#6c757d',
                'marginTop': '10px', 'marginBottom': '10px',
                'minHeight': '18px',
            }),

            html.Div([
                html.Button('🔬 运行分析',
                            id='research-sensitivity-run-btn', n_clicks=0,
                            style={'padding': '10px 20px',
                                   'backgroundColor': '#00b894',
                                   'color': 'white', 'border': 'none',
                                   'borderRadius': '6px', 'fontSize': '14px',
                                   'fontWeight': 'bold',
                                   'cursor': 'pointer'}),
                html.Button('📥 导出结果',
                            id='research-sensitivity-export-btn', n_clicks=0,
                            style={'padding': '10px 20px',
                                   'backgroundColor': '#6c757d',
                                   'color': 'white', 'border': 'none',
                                   'borderRadius': '6px', 'fontSize': '14px',
                                   'fontWeight': 'bold',
                                   'cursor': 'pointer',
                                   'marginLeft': '10px'}),
            ]),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '8px'}),

        dcc.Loading(
            id='research-sensitivity-loading',
            type='default', color='#00b894',
            children=[html.Div(id='research-sensitivity-results',
                               style={'marginTop': '15px'})],
        ),
        dcc.Store(id='research-sensitivity-results-store'),
        dcc.Download(id='research-sensitivity-download'),
    ])


# ========== 模式切换 ==========

@callback(
    Output('research-sensitivity-single-controls', 'style'),
    Output('research-sensitivity-grid-controls', 'style'),
    Input('research-sensitivity-mode', 'value'),
)
def _toggle_mode(mode):
    if mode == 'grid':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'block'}, {'display': 'none'}


@callback(
    Output('research-sensitivity-range-hint', 'children'),
    Input('research-sensitivity-mode', 'value'),
    Input('research-sensitivity-param', 'value'),
    Input('research-sensitivity-metric', 'value'),
    Input('research-grid-param-x', 'value'),
    Input('research-grid-param-y', 'value'),
    Input('research-grid-metric', 'value'),
)
def _update_range_hint(mode, p_single, m_single, p_x, p_y, m_grid):
    def dir_text(mk):
        d = METRIC_SCHEMA.get(mk, {}).get('direction')
        return ' · 本指标越大越好' if d == 'max' else \
               ' · 本指标越小越好' if d == 'min' else ''

    if mode == 'grid':
        if not p_x or not p_y or p_x not in PARAM_SCHEMA or p_y not in PARAM_SCHEMA:
            return ''
        sx, sy = PARAM_SCHEMA[p_x], PARAM_SCHEMA[p_y]
        return (f"X: {sx['label']} {sx['min']}~{sx['max']} · "
                f"Y: {sy['label']} {sy['min']}~{sy['max']}{dir_text(m_grid)}")
    if not p_single or p_single not in PARAM_SCHEMA:
        return ''
    s = PARAM_SCHEMA[p_single]
    return (f"范围 {s['min']} ~ {s['max']}（步长 {s['step']}）"
            f"{dir_text(m_single)}")


# ========== 运行分析 ==========

@callback(
    Output('research-sensitivity-results', 'children'),
    Output('research-sensitivity-results-store', 'data'),
    Input('research-sensitivity-run-btn', 'n_clicks'),
    State('research-sensitivity-mode', 'value'),
    State('research-params-store', 'data'),
    State('research-sensitivity-param', 'value'),
    State('research-sensitivity-metric', 'value'),
    State('research-sensitivity-npoints', 'value'),
    State('research-grid-param-x', 'value'),
    State('research-grid-param-y', 'value'),
    State('research-grid-metric', 'value'),
    State('research-grid-nx', 'value'),
    State('research-grid-ny', 'value'),
    State('series-selector', 'value'),
    prevent_initial_call=True,
)
def run_research_sensitivity(n_clicks, mode, params, p_single, m_single,
                             n_points, p_x, p_y, m_grid, nx, ny, series):
    if not n_clicks:
        return no_update, no_update
    if not params or not params.get('market_id'):
        return _warn("请先在左侧选择事件和市场"), None

    series = series or '7d'

    if mode == 'grid':
        result = SensitivityAnalysis.run_grid_analysis(
            params, p_x, p_y, metric_key=m_grid,
            n_points_x=int(nx or 5), n_points_y=int(ny or 5), series=series,
        )
        if result.get('error'):
            return _warn(f"分析失败：{result['error']}"), None
        best_params = _extract_best_params(result, single=False)
        return (_render_grid_results(result, best_params),
                {'mode': 'grid', 'result': to_python(result),
                 'best_params': best_params})

    result = SensitivityAnalysis.run_sensitivity_analysis(
        params, p_single, param_values=None,
        metric_key=m_single, series=series, n_points=int(n_points or 10),
    )
    if result.get('error'):
        return _warn(f"分析失败：{result['error']}"), None
    best_params = _extract_best_params(result, single=True)
    return (_render_single_results(result, best_params),
            {'mode': 'single', 'result': to_python(result),
             'best_params': best_params})

def _extract_best_params(result, single):
    """从敏感性结果里提取最优参数组合（用于跳转到信号回测）"""
    best = result.get('best_value') if single else result.get('best_cell')
    if not best:
        return None

    if single:
        return {result['param_name']: best['param_value']}
    else:
        return {
            result['param_x']: best['x'],
            result['param_y']: best['y'],
        }

def _warn(msg):
    return html.Div(msg, style={
        'padding': '12px 16px', 'backgroundColor': '#fff3cd',
        'borderLeft': '4px solid #f39c12', 'borderRadius': '4px',
        'fontSize': '13px', 'color': '#856404',
    })


# ========== 渲染：单参数 ==========

def _render_single_results(result, best_params=None):
    fig = _create_sensitivity_chart(result)
    best = result.get('best_value')
    children = [dcc.Graph(figure=fig, style={'height': '400px'})]

    if best:
        p = result['param_name']
        m = result['metric_key']
        direction = result.get('direction')
        hint = '最小' if direction == 'min' else '最大'
        children.append(html.Div([
            html.Div([
                html.Strong(f"✅ 最优参数（{hint}）："),
                html.Span(
                    f"{PARAM_SCHEMA[p]['label']} = "
                    f"{best['param_value']:.4f}",
                    style={'color': '#00b894', 'fontWeight': 'bold',
                           'marginLeft': '4px'},
                ),
                html.Span(
                    f" → {METRIC_SCHEMA[m]['label']}: "
                    f"{fmt_metric(m, best['metric_value'])}",
                    style={'fontWeight': 'bold', 'marginLeft': '8px'},
                ),
            ], style={'display': 'inline-block',
                      'verticalAlign': 'middle'}),
            html.Button(
                '→ 带入信号回测',
                id='research-sensitivity-import-btn',
                n_clicks=0,
                disabled=not best_params,
                style={
                    'padding': '6px 14px', 'fontSize': '12px',
                    'backgroundColor': '#3498db', 'color': 'white',
                    'border': 'none', 'borderRadius': '4px',
                    'cursor': 'pointer', 'marginLeft': '15px',
                    'verticalAlign': 'middle',
                },
            ),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5',
                  'borderRadius': '6px', 'marginTop': '10px'}))
    else:
        children.append(html.Div(
            "没有有效数据点（可能是数据不足）",
            style={'padding': '10px', 'color': '#856404',
                   'backgroundColor': '#fff3cd', 'borderRadius': '6px',
                   'marginTop': '10px'},
        ))
    return html.Div(children)


def _create_sensitivity_chart(result):
    fig = go.Figure()
    valid = [r for r in result['results'] if r.get('metric_value') is not None]
    if not valid:
        return fig

    x_vals = [r['param_value'] for r in valid]
    y_vals = [float(r['metric_value']) for r in valid]

    fig.add_trace(go.Scatter(
        x=x_vals, y=y_vals, mode='lines+markers',
        line=dict(color='#00b894', width=2),
        marker=dict(size=8, color='#00b894'),
        hovertemplate='%{x:.4f}<br>%{y:.4f}<extra></extra>',
        name='敏感性曲线',
    ))

    best = result.get('best_value')
    if best:
        fig.add_annotation(
            x=best['param_value'], y=float(best['metric_value']),
            text=f"最优 {best['param_value']:.4f}",
            showarrow=True, arrowhead=2, ax=20, ay=-30,
            font=dict(color='#00b894', size=12),
        )

    p, m = result['param_name'], result['metric_key']
    p_label = PARAM_SCHEMA[p]['label']
    m_label = METRIC_SCHEMA[m]['label']
    m_unit = METRIC_SCHEMA[m].get('unit', '')
    y_title = m_label + (f' ({m_unit})' if m_unit else '')

    fig.update_layout(
        title=f'{p_label} → {m_label}',
        xaxis_title=p_label, yaxis_title=y_title,
        hovermode='x', height=400,
        margin=dict(l=50, r=50, t=50, b=50),
    )
    return fig


# ========== 渲染：双参数 ==========

def _render_grid_results(result, best_params=None):
    fig = _create_grid_chart(result)
    best = result.get('best_cell')
    children = [dcc.Graph(figure=fig, style={'height': '500px'})]

    if best:
        p_x, p_y = result['param_x'], result['param_y']
        m = result['metric_key']
        hint = '最小' if result.get('direction') == 'min' else '最大'
        children.append(html.Div([
            html.Div([
                html.Strong(f"✅ 最优组合（{hint}）："),
                html.Span(
                    f"{PARAM_SCHEMA[p_x]['label']} = {best['x']:.4f}, "
                    f"{PARAM_SCHEMA[p_y]['label']} = {best['y']:.4f}",
                    style={'color': '#00b894', 'fontWeight': 'bold',
                           'marginLeft': '4px'}),
                html.Span(
                    f" → {METRIC_SCHEMA[m]['label']}: "
                    f"{fmt_metric(m, best['metric_value'])}",
                    style={'fontWeight': 'bold', 'marginLeft': '8px'}),
            ], style={'display': 'inline-block',
                      'verticalAlign': 'middle'}),
            html.Button(
                '→ 带入信号回测',
                id='research-sensitivity-import-btn',
                n_clicks=0,
                disabled=not best_params,
                style={
                    'padding': '6px 14px', 'fontSize': '12px',
                    'backgroundColor': '#3498db', 'color': 'white',
                    'border': 'none', 'borderRadius': '4px',
                    'cursor': 'pointer', 'marginLeft': '15px',
                    'verticalAlign': 'middle',
                },
            ),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5',
                  'borderRadius': '6px', 'marginTop': '10px'}))
    else:
        children.append(html.Div(
            "没有有效数据点",
            style={'padding': '10px', 'color': '#856404',
                   'backgroundColor': '#fff3cd', 'borderRadius': '6px',
                   'marginTop': '10px'}))

    children.append(html.Div(
        f"网格 {len(result['y_values'])}×{len(result['x_values'])}，"
        f"耗时 {result.get('elapsed_sec', 0):.2f}s",
        style={'fontSize': '12px', 'color': '#6c757d', 'marginTop': '6px'}))
    return html.Div(children)


def _create_grid_chart(result):
    fig = go.Figure()
    m = result['metric_key']
    p_x, p_y = result['param_x'], result['param_y']
    colorscale = 'RdYlGn_r' if is_lower_better(m) else 'RdYlGn'

    fig.add_trace(go.Heatmap(
        x=result['x_values'], y=result['y_values'], z=result['z_matrix'],
        colorscale=colorscale,
        colorbar=dict(title=METRIC_SCHEMA[m]['label']),
        hovertemplate=(
            f"{PARAM_SCHEMA[p_x]['label']}: %{{x}}<br>"
            f"{PARAM_SCHEMA[p_y]['label']}: %{{y}}<br>"
            f"{METRIC_SCHEMA[m]['label']}: %{{z:.4f}}<extra></extra>"
        ),
    ))

    best = result.get('best_cell')
    if best:
        fig.add_trace(go.Scatter(
            x=[best['x']], y=[best['y']], mode='markers',
            marker=dict(symbol='circle-open', size=20, color='white',
                        line=dict(width=3)),
            showlegend=False, hoverinfo='skip',
        ))

    x_label = PARAM_SCHEMA[p_x]['label']
    y_label = PARAM_SCHEMA[p_y]['label']
    m_label = METRIC_SCHEMA[m]['label']

    fig.update_layout(
        title=f'{x_label} × {y_label} → {m_label}',
        xaxis_title=x_label, yaxis_title=y_label, height=500,
        margin=dict(l=60, r=60, t=60, b=60),
    )
    return fig


# ========== 导出 ==========

@callback(
    Output('research-sensitivity-download', 'data'),
    Input('research-sensitivity-export-btn', 'n_clicks'),
    State('research-sensitivity-results-store', 'data'),
    prevent_initial_call=True,
)
def export_sensitivity(n_clicks, store_data):
    if not store_data or not store_data.get('result'):
        return no_update

    mode = store_data.get('mode')
    result = store_data['result']

    if mode == 'single':
        rows = []
        for r in result['results']:
            rows.append({
                'param_value': r['param_value'],
                'metric_value': r.get('metric_value'),
                'total_return': r.get('total_return'),
                'sharpe_ratio': r.get('sharpe_ratio'),
                'win_rate': r.get('win_rate'),
                'max_drawdown_pct': r.get('max_drawdown_pct'),
                'profit_factor': r.get('profit_factor'),
                'total_trades': r.get('total_trades'),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.rename(columns={'param_value':
                                    PARAM_SCHEMA[result['param_name']]['label']})
        return dcc.send_data_frame(df.to_csv, 'sensitivity_single.csv',
                                   index=False, encoding='utf-8-sig')

    df = pd.DataFrame(
        result['z_matrix'],
        index=result['y_values'],
        columns=result['x_values'],
    )
    df.index.name = PARAM_SCHEMA[result['param_y']]['label']
    df.columns.name = PARAM_SCHEMA[result['param_x']]['label']
    header = (f"# X: {df.columns.name}, Y: {df.index.name}, "
              f"Metric: {METRIC_SCHEMA[result['metric_key']]['label']}\n")
    content = header + df.to_csv()
    return dict(content=content, filename='sensitivity_grid.csv')

# ==================== 跳转到信号回测 ====================

@callback(
    Output('global-params', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('research-sensitivity-import-btn', 'n_clicks'),
    State('research-sensitivity-results-store', 'data'),
    State('research-params-store', 'data'),
    State('global-params', 'data'),
    prevent_initial_call=True,
)
def import_sensitivity_to_backtest(n_clicks, results_store,
                                    research_params, global_params):
    """把敏感性分析的最优参数带入信号回测"""
    if not n_clicks or not results_store:
        return no_update, no_update

    best_params = results_store.get('best_params')
    if not best_params:
        return no_update, no_update

    p = _gp_merge(global_params)

    # research 公共参数
    if research_params:
        if research_params.get('event_id') is not None:
            p['event_id'] = research_params['event_id']
        if research_params.get('market_id') is not None:
            p['market_id'] = research_params['market_id']
        if research_params.get('price_type'):
            p['price_type'] = research_params['price_type']

        wt = research_params.get('window_type')
        if wt:
            p['window_type'] = wt
            eng = _wt2e(wt, research_params.get('window_custom_hours'))
            p.update(eng)

        for k in ('initial_capital', 'position_mode', 'position_size',
                  'backtest_range', 'backtest_range_custom'):
            if research_params.get(k) is not None:
                p[k] = research_params[k]

    # 最优参数
    for k, v in best_params.items():
        p[k] = v

    return p, '/backtest'