# src/dash_app/pages/research/tabs/sensitivity.py
"""
策略研究 - 敏感性分析 Tab

三种模式：
- 单参 · 单市场：沿一个参数在单个市场上扫描
- 单参 · 多市场：沿一个参数在多个市场上扫描，Y 轴为平均指标
- 双参 · 单市场：两个参数的笛卡尔积热力图
"""

import pandas as pd
from dash import (html, dcc, Input, Output, State, callback,
                  no_update)
import plotly.graph_objects as go

from src.dash_app.utils.analysis.sensitivity import SensitivityAnalysis
from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
    get_markets_by_event,
)
from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, METRIC_SCHEMA,
    get_tunable_params, get_metric_options, fmt_metric,
    is_lower_better,
)
from src.dash_app.utils.research.serialize import to_python
from src.dash_app.pages.shared.params_panel import create_shared_panel


def _param_options():
    return [{'label': PARAM_SCHEMA[k]['label'], 'value': k}
            for k in get_tunable_params()]


def render_sensitivity_tab(global_params=None, series='7d'):
    return html.Div([
        # ---- sens-* 配置区（扫参基准）----
        create_shared_panel(global_params=global_params, series=series,
                            prefix='sens'),
        dcc.Store(id='sens-params-store', data={}),

        html.Div([
            html.P("选择扫描模式和范围，运行分析。",
                   style={'fontSize': '13px', 'color': '#495057',
                          'marginBottom': '10px'}),

            # ---- 扫描模式 ----
            dcc.RadioItems(
                id='research-sensitivity-mode',
                options=[
                    {'label': ' 📈 单参数曲线', 'value': 'single'},
                    {'label': ' 🔥 双参数网格', 'value': 'grid'},
                ],
                value='single',
                inline=True,
                style={'marginBottom': '8px', 'fontSize': '13px'},
            ),

            # ---- 扫描范围 ----
            dcc.RadioItems(
                id='research-sensitivity-scope',
                options=[
                    {'label': ' 单市场', 'value': 'single_market'},
                    {'label': ' 多市场集合', 'value': 'multi_market'},
                ],
                value='single_market',
                inline=True,
                style={'marginBottom': '12px', 'fontSize': '13px'},
            ),

            # ---- 单市场：单参数控件 ----
            html.Div([
                html.Div([
                    html.Label('分析参数',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-sensitivity-param',
                        options=_param_options(),
                        value='price_threshold',
                        clearable=False,
                        style={'width': '100%'},
                    ),
                ], style={'width': '32%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('追踪指标',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-sensitivity-metric',
                        options=get_metric_options(),
                        value='total_return',
                        clearable=False,
                        style={'width': '100%'},
                    ),
                ], style={'width': '32%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('扫描点数',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Input(
                        id='research-sensitivity-npoints',
                        type='number', value=10, min=3, max=30, step=1,
                        style={'width': '80px', 'padding': '4px',
                               'fontSize': '13px'},
                    ),
                ], style={'width': '28%', 'display': 'inline-block'}),
            ], id='research-sensitivity-single-controls'),

            # ---- 双参数网格控件 ----
            html.Div([
                html.Div([
                    html.Label('X 参数',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-grid-param-x',
                        options=_param_options(),
                        value='price_threshold',
                        clearable=False,
                        style={'width': '100%'},
                    ),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('Y 参数',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-grid-param-y',
                        options=_param_options(),
                        value='capacity',
                        clearable=False,
                        style={'width': '100%'},
                    ),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('追踪指标',
                               style={'fontWeight': 'bold',
                                      'fontSize': '13px'}),
                    dcc.Dropdown(
                        id='research-grid-metric',
                        options=get_metric_options(),
                        value='total_return',
                        clearable=False,
                        style={'width': '100%'},
                    ),
                ], style={'width': '24%', 'display': 'inline-block',
                          'paddingRight': '10px'}),
                html.Div([
                    html.Label('网格大小',
                               style={'fontWeight': 'bold',
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

            # ---- 多市场：选择器 ----
            html.Div([
                html.P("多市场模式下：Y 轴 = 所有市场的平均指标；"
                       "辅助线 = 正收益市场占比",
                       style={'fontSize': '12px', 'color': '#6c757d',
                              'marginBottom': '8px'}),

                # 多市场：研究模式
                dcc.RadioItems(
                    id='research-mm-mode',
                    options=[
                        {'label': ' 多事件 × 目标市场',
                         'value': 'multi_event'},
                        {'label': ' 单事件 × 多子市场',
                         'value': 'multi_market'},
                    ],
                    value='multi_event',
                    inline=True,
                    style={'marginBottom': '10px', 'fontSize': '13px'},
                ),

                # 多事件控件
                html.Div([
                    html.Label('选择事件（默认全选）：',
                               style={'fontWeight': 'bold',
                                      'fontSize': '12px',
                                      'marginBottom': '4px',
                                      'display': 'block'}),
                    dcc.Dropdown(
                        id='research-mm-event-selector',
                        options=[], value=[], multi=True,
                        placeholder='加载中...',
                        style={'width': '100%', 'marginBottom': '10px'},
                    ),
                ], id='research-mm-controls-A'),

                # 单事件多市场控件
                html.Div([
                    html.Label('选择事件：',
                               style={'fontWeight': 'bold',
                                      'fontSize': '12px',
                                      'marginBottom': '4px',
                                      'display': 'block'}),
                    dcc.Dropdown(
                        id='research-mm-event-single',
                        options=[], value=None, clearable=False,
                        placeholder='选择事件',
                        style={'width': '100%', 'marginBottom': '10px'},
                    ),
                    html.Label('选择子市场（默认全选）：',
                               style={'fontWeight': 'bold',
                                      'fontSize': '12px',
                                      'marginBottom': '4px',
                                      'display': 'block'}),
                    dcc.Dropdown(
                        id='research-mm-market-selector',
                        options=[], value=[], multi=True,
                        placeholder='加载中...',
                        style={'width': '100%', 'marginBottom': '10px'},
                    ),
                ], id='research-mm-controls-B',
                   style={'display': 'none'}),

                # 多市场下的参数控件
                html.Div([
                    html.Div([
                        html.Label('分析参数',
                                   style={'fontWeight': 'bold',
                                          'fontSize': '13px'}),
                        dcc.Dropdown(
                            id='research-mm-param',
                            options=_param_options(),
                            value='price_threshold',
                            clearable=False,
                            style={'width': '100%'},
                        ),
                    ], style={'width': '32%', 'display': 'inline-block',
                              'paddingRight': '10px'}),
                    html.Div([
                        html.Label('追踪指标',
                                   style={'fontWeight': 'bold',
                                          'fontSize': '13px'}),
                        dcc.Dropdown(
                            id='research-mm-metric',
                            options=get_metric_options(),
                            value='total_return',
                            clearable=False,
                            style={'width': '100%'},
                        ),
                    ], style={'width': '32%', 'display': 'inline-block',
                              'paddingRight': '10px'}),
                    html.Div([
                        html.Label('扫描点数',
                                   style={'fontWeight': 'bold',
                                          'fontSize': '13px'}),
                        dcc.Input(
                            id='research-mm-npoints',
                            type='number', value=10, min=3, max=20, step=1,
                            style={'width': '80px', 'padding': '4px',
                                   'fontSize': '13px'},
                        ),
                    ], style={'width': '28%', 'display': 'inline-block'}),
                ]),
            ], id='research-sensitivity-multi-controls',
               style={'display': 'none'}),

            # 提示
            html.Div(id='research-sensitivity-range-hint', style={
                'fontSize': '12px', 'color': '#6c757d',
                'marginTop': '10px', 'marginBottom': '10px',
                'minHeight': '18px',
            }),

            html.Div([
                html.Button('🔬 运行分析',
                            id='research-sensitivity-run-btn',
                            n_clicks=0,
                            style={'padding': '10px 20px',
                                   'backgroundColor': '#00b894',
                                   'color': 'white', 'border': 'none',
                                   'borderRadius': '6px',
                                   'fontSize': '14px',
                                   'fontWeight': 'bold',
                                   'cursor': 'pointer'}),
                html.Button('📥 导出结果',
                            id='research-sensitivity-export-btn',
                            n_clicks=0,
                            style={'padding': '10px 20px',
                                   'backgroundColor': '#6c757d',
                                   'color': 'white', 'border': 'none',
                                   'borderRadius': '6px',
                                   'fontSize': '14px',
                                   'fontWeight': 'bold',
                                   'cursor': 'pointer',
                                   'marginLeft': '10px'}),
            ]),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '8px'}),

        html.Div(id='research-sensitivity-results',
                 style={'marginTop': '15px'}),
        dcc.Store(id='research-sensitivity-results-store'),
        dcc.Download(id='research-sensitivity-download'),
    ])


# ==================== 模式/范围切换 ====================

@callback(
    Output('research-sensitivity-single-controls', 'style'),
    Output('research-sensitivity-grid-controls', 'style'),
    Output('research-sensitivity-multi-controls', 'style'),
    Input('research-sensitivity-mode', 'value'),
    Input('research-sensitivity-scope', 'value'),
)
def _toggle_mode(mode, scope):
    hidden = {'display': 'none'}
    shown = {'display': 'block'}

    if scope == 'multi_market':
        # 多市场只支持单参数
        return hidden, hidden, shown

    if mode == 'grid':
        return hidden, shown, hidden
    return shown, hidden, hidden


@callback(
    Output('research-mm-controls-A', 'style'),
    Output('research-mm-controls-B', 'style'),
    Input('research-mm-mode', 'value'),
)
def _toggle_mm_mode(mode):
    if mode == 'multi_market':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'block'}, {'display': 'none'}


# ==================== 多市场：事件/市场联动 ====================

@callback(
    Output('research-mm-event-selector', 'options'),
    Output('research-mm-event-selector', 'value'),
    Output('research-mm-event-single', 'options'),
    Output('research-mm-event-single', 'value'),
    Input('series-selector', 'value'),
)
def _populate_mm_events(series):
    events = get_elon_tweet_events(series or '7d')
    if events is None or events.empty:
        return [], [], [], None

    slug_map = dict(zip(events['id'], events['slug']))
    options = []
    values = []
    for eid in events['id'].tolist():
        slug = slug_map.get(eid, '')
        label = _short_slug(slug, max_len=50) if slug else str(eid)
        options.append({'label': label, 'value': eid})
        values.append(eid)

    single_value = values[-1] if values else None
    return options, values, options, single_value


@callback(
    Output('research-mm-market-selector', 'options'),
    Output('research-mm-market-selector', 'value'),
    Input('research-mm-event-single', 'value'),
)
def _populate_mm_markets(event_id):
    if not event_id:
        return [], []
    markets = get_markets_by_event(event_id)
    if markets is None or markets.empty:
        return [], []
    options = []
    values = []
    for _, row in markets.iterrows():
        r_start = int(row['range_start'])
        r_end = (int(row['range_end'])
                 if not pd.isna(row['range_end'])
                 and row['range_end'] is not None
                 else '∞')
        options.append({'label': f"{r_start}-{r_end}", 'value': row['id']})
        values.append(row['id'])
    return options, values


# ==================== 提示文字 ====================

@callback(
    Output('research-sensitivity-range-hint', 'children'),
    Input('research-sensitivity-mode', 'value'),
    Input('research-sensitivity-scope', 'value'),
    Input('research-sensitivity-param', 'value'),
    Input('research-sensitivity-metric', 'value'),
    Input('research-grid-param-x', 'value'),
    Input('research-grid-param-y', 'value'),
    Input('research-grid-metric', 'value'),
    Input('research-mm-param', 'value'),
    Input('research-mm-metric', 'value'),
)
def _update_range_hint(mode, scope, p_single, m_single,
                       p_x, p_y, m_grid, p_mm, m_mm):
    def dir_text(mk):
        d = METRIC_SCHEMA.get(mk, {}).get('direction')
        return (' · 越大越好' if d == 'max'
                else ' · 越小越好' if d == 'min' else '')

    if scope == 'multi_market':
        if not p_mm or p_mm not in PARAM_SCHEMA:
            return ''
        s = PARAM_SCHEMA[p_mm]
        return (f"范围 {s['min']} ~ {s['max']}（步长 {s['step']}）"
                f"{dir_text(m_mm)}")

    if mode == 'grid':
        if not p_x or not p_y or p_x not in PARAM_SCHEMA or p_y not in PARAM_SCHEMA:
            return ''
        sx, sy = PARAM_SCHEMA[p_x], PARAM_SCHEMA[p_y]
        return (f"X: {sx['label']} {sx['min']}~{sx['max']} · "
                f"Y: {sy['label']} {sy['min']}~{sy['max']}"
                f"{dir_text(m_grid)}")

    if not p_single or p_single not in PARAM_SCHEMA:
        return ''
    s = PARAM_SCHEMA[p_single]
    return (f"范围 {s['min']} ~ {s['max']}（步长 {s['step']}）"
            f"{dir_text(m_single)}")


# ==================== 运行分析 ====================

@callback(
    Output('research-sensitivity-results', 'children'),
    Output('research-sensitivity-results-store', 'data'),
    Input('research-sensitivity-run-btn', 'n_clicks'),
    State('research-sensitivity-mode', 'value'),
    State('research-sensitivity-scope', 'value'),
    State('sens-params-store', 'data'),
    State('research-sensitivity-param', 'value'),
    State('research-sensitivity-metric', 'value'),
    State('research-sensitivity-npoints', 'value'),
    State('research-grid-param-x', 'value'),
    State('research-grid-param-y', 'value'),
    State('research-grid-metric', 'value'),
    State('research-grid-nx', 'value'),
    State('research-grid-ny', 'value'),
    State('research-mm-mode', 'value'),
    State('research-mm-event-selector', 'value'),
    State('research-mm-event-single', 'value'),
    State('research-mm-market-selector', 'value'),
    State('research-mm-param', 'value'),
    State('research-mm-metric', 'value'),
    State('research-mm-npoints', 'value'),
    State('series-selector', 'value'),
    prevent_initial_call=True,
)
def run_research_sensitivity(
    n_clicks, mode, scope, params,
    p_single, m_single, n_points,
    p_x, p_y, m_grid, nx, ny,
    mm_mode, mm_events, mm_single, mm_markets,
    mm_param, mm_metric, mm_npoints,
    series,
):
    if not n_clicks:
        return no_update, no_update
    if not params or not params.get('market_id'):
        return _warn("请先在上方配置区选择事件和市场"), None

    series = series or '7d'

    # ---- 多市场 ----
    if scope == 'multi_market':
        pairs = _build_mm_pairs(mm_mode, series, mm_events,
                                mm_single, mm_markets)
        if not pairs:
            return _warn("请至少选择一个市场"), None

        result = SensitivityAnalysis.run_sensitivity_multi_market(
            params, mm_param, param_values=None,
            metric_key=mm_metric, market_pairs=pairs,
            series=series, n_points=int(mm_npoints or 10),
        )
        if result.get('error'):
            return _warn(f"分析失败：{result['error']}"), None
        return (_render_multi_results(result),
                {'mode': 'multi', 'result': to_python(result)})

    # ---- 双参数网格 ----
    if mode == 'grid':
        result = SensitivityAnalysis.run_grid_analysis(
            params, p_x, p_y, metric_key=m_grid,
            n_points_x=int(nx or 5), n_points_y=int(ny or 5),
            series=series,
        )
        if result.get('error'):
            return _warn(f"分析失败：{result['error']}"), None
        return (_render_grid_results(result),
                {'mode': 'grid', 'result': to_python(result)})

    # ---- 单参单市场 ----
    result = SensitivityAnalysis.run_sensitivity_analysis(
        params, p_single, param_values=None,
        metric_key=m_single, series=series,
        n_points=int(n_points or 10),
    )
    if result.get('error'):
        return _warn(f"分析失败：{result['error']}"), None
    return (_render_single_results(result),
            {'mode': 'single', 'result': to_python(result)})


def _build_mm_pairs(mode, series, events, single_event, markets):
    if mode == 'multi_market':
        if not single_event or not markets:
            return []
        return [(single_event, mid) for mid in markets]

    # multi_event
    all_events = get_elon_tweet_events(series)
    if all_events is None or all_events.empty:
        return []
    ids = all_events['id'].tolist()
    if events:
        selected = set(events)
        ids = [eid for eid in ids if eid in selected]
    targets = get_target_markets_batch(ids)
    pairs = []
    for eid in ids:
        t = targets.get(eid)
        if t:
            pairs.append((eid, t['id']))
    return pairs


def _short_slug(slug, max_len=30):
    if not slug:
        return ''
    s = slug.replace('elon-musk-of-tweets-', '')
    if len(s) > max_len:
        s = s[:max_len - 1] + '…'
    return s


def _warn(msg):
    return html.Div(msg, style={
        'padding': '12px 16px', 'backgroundColor': '#fff3cd',
        'borderLeft': '4px solid #f39c12', 'borderRadius': '4px',
        'fontSize': '13px', 'color': '#856404',
    })


# ==================== 渲染：单市场单参 ====================

def _render_single_results(result):
    fig = _create_sensitivity_chart(result)
    best = result.get('best_value')
    children = [dcc.Graph(figure=fig, style={'height': '400px'})]

    if best:
        p = result['param_name']
        m = result['metric_key']
        hint = '最小' if result.get('direction') == 'min' else '最大'
        children.append(html.Div([
            html.Strong(f"✅ 最优参数（{hint}）："),
            html.Span(
                f"{PARAM_SCHEMA[p]['label']} = {best['param_value']:.4f}",
                style={'color': '#00b894', 'fontWeight': 'bold',
                       'marginLeft': '4px'}),
            html.Span(
                f" → {METRIC_SCHEMA[m]['label']}: "
                f"{fmt_metric(m, best['metric_value'])}",
                style={'fontWeight': 'bold', 'marginLeft': '8px'}),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5',
                  'borderRadius': '6px', 'marginTop': '10px'}))
    else:
        children.append(html.Div(
            "没有有效数据点（可能是数据不足）",
            style={'padding': '10px', 'color': '#856404',
                   'backgroundColor': '#fff3cd', 'borderRadius': '6px',
                   'marginTop': '10px'}))
    return html.Div(children)


def _create_sensitivity_chart(result):
    fig = go.Figure()
    valid = [r for r in result['results']
             if r.get('metric_value') is not None]
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


# ==================== 渲染：多市场 ====================

def _render_multi_results(result):
    fig = _create_multi_chart(result)
    best = result.get('best_value')

    children = [
        html.Div(
            f"扫描 {result.get('n_markets', 0)} 个市场",
            style={'fontSize': '12px', 'color': '#6c757d',
                   'marginBottom': '6px'}),
        dcc.Graph(figure=fig, style={'height': '420px'}),
    ]

    if best:
        p = result['param_name']
        m = result['metric_key']
        hint = '最小' if result.get('direction') == 'min' else '最大'
        children.append(html.Div([
            html.Strong(f"✅ 最优参数（{hint}）："),
            html.Span(
                f"{PARAM_SCHEMA[p]['label']} = {best['param_value']:.4f}",
                style={'color': '#00b894', 'fontWeight': 'bold',
                       'marginLeft': '4px'}),
            html.Span(
                f" → 平均{METRIC_SCHEMA[m]['label']}: "
                f"{fmt_metric(m, best['metric_value'])}",
                style={'fontWeight': 'bold', 'marginLeft': '8px'}),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5',
                  'borderRadius': '6px', 'marginTop': '10px'}))
    else:
        children.append(html.Div(
            "没有有效数据点",
            style={'padding': '10px', 'color': '#856404',
                   'backgroundColor': '#fff3cd', 'borderRadius': '6px',
                   'marginTop': '10px'}))

    return html.Div(children)


def _create_multi_chart(result):
    fig = go.Figure()
    valid = [r for r in result['results']
             if r.get('mean_metric') is not None]
    if not valid:
        return fig

    x_vals = [r['param_value'] for r in valid]
    y_mean = [float(r['mean_metric']) for r in valid]
    y_win = [float(r['win_rate']) if r.get('win_rate') is not None
             else None for r in valid]

    fig.add_trace(go.Scatter(
        x=x_vals, y=y_mean, mode='lines+markers',
        name='平均指标',
        line=dict(color='#00b894', width=2),
        marker=dict(size=8, color='#00b894'),
        hovertemplate='%{x:.4f}<br>平均: %{y:.4f}<extra></extra>',
        yaxis='y1',
    ))

    if any(v is not None for v in y_win):
        fig.add_trace(go.Scatter(
            x=x_vals, y=y_win, mode='lines+markers',
            name='正收益市场占比 (%)',
            line=dict(color='#3498db', width=1.5, dash='dot'),
            marker=dict(size=6, color='#3498db'),
            hovertemplate='%{x:.4f}<br>占比: %{y:.1f}%<extra></extra>',
            yaxis='y2',
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

    fig.update_layout(
        title=f'{p_label} → 平均{m_label}（多市场）',
        xaxis_title=p_label,
        yaxis=dict(title=f'平均{m_label}'),
        yaxis2=dict(title='正收益市场占比 (%)',
                    overlaying='y', side='right',
                    range=[0, 105],
                    showgrid=False),
        hovermode='x unified', height=420,
        margin=dict(l=60, r=80, t=50, b=50),
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='center', x=0.5),
    )
    return fig


# ==================== 渲染：双参数网格 ====================

def _render_grid_results(result):
    fig = _create_grid_chart(result)
    best = result.get('best_cell')
    children = [dcc.Graph(figure=fig, style={'height': '500px'})]

    if best:
        p_x, p_y = result['param_x'], result['param_y']
        m = result['metric_key']
        hint = '最小' if result.get('direction') == 'min' else '最大'
        children.append(html.Div([
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
        style={'fontSize': '12px', 'color': '#6c757d',
               'marginTop': '6px'}))
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


# ==================== 导出 ====================

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

    if mode == 'multi':
        rows = []
        for r in result['results']:
            rows.append({
                'param_value': r['param_value'],
                'mean_metric': r.get('mean_metric'),
                'median_metric': r.get('median_metric'),
                'std_metric': r.get('std_metric'),
                'win_rate(%)': r.get('win_rate'),
                'n_ok': r.get('n_ok'),
                'n_total': r.get('n_total'),
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.rename(columns={
                'param_value':
                    PARAM_SCHEMA[result['param_name']]['label']})
        return dcc.send_data_frame(df.to_csv,
                                   'sensitivity_multi_market.csv',
                                   index=False, encoding='utf-8-sig')

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
            df = df.rename(columns={
                'param_value':
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