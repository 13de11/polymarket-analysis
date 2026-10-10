# src/dash_app/pages/research/tabs/batch.py
"""
策略研究 - 批量研究 Tab（事件多选版）

对选中事件跑一遍「策略对比」里已启用的策略，输出：
- 聚合表：每策略的收益均值/中位数/标准差/胜事件率
- 事件 × 策略 收益矩阵热力图
- 逐事件明细 DataTable（排序/分页/导出）

策略复用「策略对比」Tab 里配置好的卡片（A/B/C）。
"""

from dash import html, dcc, Input, Output, State, callback, ctx, no_update
import plotly.graph_objects as go

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
)
from src.dash_app.utils.research.batch import BatchEngine
from src.dash_app.utils.research.strategy_config import StrategyConfig
from src.dash_app.utils.ui.table import td, table as tbl

from src.dash_app.state.global_params import (
    merge as _gp_merge,
    window_type_to_engine as _wt2e,
)


STRATEGY_COLORS = {'a': '#3498db', 'b': '#e74c3c', 'c': '#2ecc71'}


def render_batch_tab():
    return html.Div([
        html.Div([
            html.P("对选中事件跑一遍「策略对比」里已启用的策略。",
                   style={'fontSize': '13px', 'color': '#495057',
                          'marginBottom': '10px'}),

            html.Label("选择事件（默认全选）：",
                       style={'fontWeight': 'bold',
                              'fontSize': '13px',
                              'marginBottom': '4px',
                              'display': 'block'}),
            dcc.Dropdown(
                id='research-batch-event-selector',
                options=[],
                value=[],
                multi=True,
                placeholder='加载中...',
                style={'width': '100%', 'marginBottom': '10px'},
            ),

            html.Button(
                '🚀 运行批量研究',
                id='research-batch-run-btn',
                n_clicks=0,
                style={
                    'padding': '10px 24px', 'backgroundColor': '#6c5ce7',
                    'color': 'white', 'border': 'none',
                    'borderRadius': '6px', 'fontSize': '14px',
                    'fontWeight': 'bold', 'cursor': 'pointer',
                },
            ),

            # ---- 跳转区（跑完批量后可用）----
            html.Div([
                html.Label("把某个事件带入信号回测深挖：",
                           style={'fontSize': '12px',
                                  'color': '#495057',
                                  'marginRight': '8px',
                                  'verticalAlign': 'middle'}),
                dcc.Dropdown(
                    id='research-batch-jump-event',
                    options=[],
                    value=None,
                    placeholder='选择事件',
                    clearable=True,
                    style={'width': '280px',
                           'display': 'inline-block',
                           'verticalAlign': 'middle',
                           'marginRight': '8px'},
                ),
                html.Button(
                    '→ 带入信号回测',
                    id='research-batch-jump-btn',
                    n_clicks=0,
                    disabled=True,
                    style={
                        'padding': '6px 14px', 'fontSize': '12px',
                        'backgroundColor': '#3498db', 'color': 'white',
                        'border': 'none', 'borderRadius': '4px',
                        'cursor': 'pointer',
                        'verticalAlign': 'middle',
                    },
                ),
            ], id='research-batch-jump-area',
               style={'display': 'none', 'marginTop': '12px'}),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '8px'}),
        dcc.Loading(
            id='research-batch-loading',
            type='default', color='#6c5ce7',
            children=[html.Div(id='research-batch-results',
                               style={'marginTop': '15px'})],
        ),
    ])


# ==================== 回调：事件列表刷新 ====================

@callback(
    Output('research-batch-event-selector', 'options'),
    Output('research-batch-event-selector', 'value'),
    Input('series-selector', 'value'),
)
def _populate_batch_events(series):
    """系列变化时刷新事件下拉列表，默认全选"""
    pairs, slug_map = _get_all_pairs(series or '7d')
    options = []
    values = []
    for eid, _ in pairs:
        slug = slug_map.get(eid, '')
        label = _short_slug(slug, max_len=50) if slug else str(eid)
        options.append({'label': label, 'value': eid})
        values.append(eid)
    return options, values


# ==================== 回调：运行批量 ====================

@callback(
    Output('research-batch-results', 'children'),
    Output('research-batch-jump-event', 'options'),
    Output('research-batch-jump-event', 'value'),
    Output('research-batch-jump-area', 'style'),
    Input('research-batch-run-btn', 'n_clicks'),
    State('research-params-store', 'data'),
    State('series-selector', 'value'),
    State('research-strategy-a-store', 'data'),
    State('research-strategy-b-store', 'data'),
    State('research-strategy-c-store', 'data'),
    State('research-batch-event-selector', 'value'),
    prevent_initial_call=True,
)
def run_batch(n_clicks, base_params, series, sa, sb, sc, selected_events):
    _hidden = {'display': 'none', 'marginTop': '12px'}
    _shown = {'display': 'block', 'marginTop': '12px'}

    if not n_clicks:
        return (no_update, no_update, no_update, no_update)
    if not base_params:
        return (_warn("请先在左侧选择事件和市场（作为参数模板）"),
                [], None, _hidden)

    series = series or '7d'

    # 1. 收集已启用的策略
    configs = []
    for idx, sd in [('a', sa), ('b', sb), ('c', sc)]:
        if not sd or not sd.get('enabled'):
            continue
        configs.append(StrategyConfig(
            name=sd.get('name') or f'策略{idx.upper()}',
            strategy_type=sd.get('strategy_type', 'direction_signal'),
            params=sd.get('params', {}),
            color=STRATEGY_COLORS.get(idx),
        ))
    if not configs:
        return (_warn("至少启用一个策略（在「策略对比」Tab 里勾选）"),
                [], None, _hidden)

    # 2. 取事件 + 市场
    all_pairs, slug_map = _get_all_pairs(series)
    if not all_pairs:
        return (_warn(f"系列 {series} 下没有可用的事件+市场组合"),
                [], None, _hidden)

    if selected_events:
        selected_set = set(selected_events)
        pairs = [(eid, mid) for eid, mid in all_pairs
                 if eid in selected_set]
    else:
        pairs = all_pairs

    if not pairs:
        return (_warn("请至少选择一个事件"), [], None, _hidden)

    # 3. 跑批量
    try:
        result = BatchEngine.run_batch(
            base_params, configs, pairs, series=series,
        )
    except Exception as e:
        return (_warn(f"批量研究失败：{type(e).__name__}: {e}"),
                [], None, _hidden)

    if not result or not result.get('per_event'):
        return (_warn("批量研究无结果"), [], None, _hidden)

    # 4. 渲染 + 准备跳转下拉
    jump_options = []
    for eid in result['per_event'].keys():
        slug = slug_map.get(eid, '')
        label = _short_slug(slug, max_len=50) if slug else str(eid)
        jump_options.append({'label': label, 'value': eid})

    return (_render_results(result, configs, slug_map),
            jump_options,
            None,
            _shown)


# ==================== 辅助 ====================

def _get_all_pairs(series):
    """返回 (pairs, slug_map)：
    - pairs: [(event_id, market_id), ...]
    - slug_map: {event_id: slug}
    """
    events = get_elon_tweet_events(series)
    if events is None or events.empty:
        return [], {}

    slug_map = dict(zip(events['id'], events['slug']))
    ids = events['id'].tolist()
    targets = get_target_markets_batch(ids)
    pairs = []
    for eid in ids:
        t = targets.get(eid)
        if t:
            pairs.append((eid, t['id']))
    return pairs, slug_map


def _short_slug(slug, max_len=30):
    """把 slug 压缩成短标签"""
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


def _render_results(result, configs, slug_map):
    aggregate = result.get('aggregate', {})
    per_event = result.get('per_event', {})

    return html.Div([
        html.H5(f"📊 聚合统计（{result['n_pairs']} 个事件）",
                style={'margin': '10px 0'}),
        _render_aggregate_table(aggregate, configs),

        html.H5("🔥 事件 × 策略 收益矩阵",
                style={'margin': '20px 0 10px 0'}),
        html.Div("每格 = 该策略在该事件上的总收益率（绿正红负）",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '6px'}),
        dcc.Graph(figure=_create_matrix_heatmap(
            per_event, configs, slug_map)),

        html.H5("📋 逐事件明细",
                style={'margin': '20px 0 10px 0'}),
        html.Div("💡 点表头排序 · 右上可导出 CSV",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '6px'}),
        _create_per_event_datatable(per_event, configs, slug_map),
    ])


def _render_aggregate_table(aggregate, configs):
    headers = ['策略', '有效事件', '收益均值', '收益中位数',
               '收益标准差', '正事件率', '夏普均值', '胜率均值']
    rows = []
    for cfg in configs:
        agg = aggregate.get(cfg.name)
        if not agg or 'error' in agg:
            rows.append(html.Tr([
                td(cfg.name, fontWeight='bold'),
                td(agg.get('error', '—') if agg else '—'),
                td(''), td(''), td(''), td(''), td(''), td(''),
            ]))
            continue
        rows.append(html.Tr([
            td([html.Span('●', style={'color': cfg.color,
                                      'marginRight': '4px'}),
                html.Span(cfg.name, style={'fontWeight': 'bold'})]),
            td(f"{agg['n_ok']}/{agg['n_events']}"),
            td(f"{agg['mean_return']:+.2f}%"),
            td(f"{agg['median_return']:+.2f}%"),
            td(f"{agg['std_return']:.2f}%"),
            td(f"{agg['win_event_rate']:.1f}%"),
            td(f"{agg['mean_sharpe']:.2f}"),
            td(f"{agg['mean_win_rate']:.1f}%"),
        ]))
    return tbl(headers, rows)


def _create_matrix_heatmap(per_event, configs, slug_map):
    """事件 × 策略 收益矩阵热力图"""
    event_ids = list(per_event.keys())
    if not event_ids:
        return go.Figure()

    y_labels = []
    for eid in event_ids:
        slug = slug_map.get(eid, '')
        y_labels.append(_short_slug(slug, max_len=24) if slug else str(eid))
    x_labels = [c.name for c in configs]

    z = []
    text = []
    for eid in event_ids:
        row = []
        row_text = []
        for cfg in configs:
            s = per_event[eid]['strategies'].get(cfg.name, {})
            if s.get('status') != 'ok':
                row.append(None)
                row_text.append('—')
            else:
                v = s['metrics'].get('total_return')
                if v is None:
                    row.append(None)
                    row_text.append('—')
                else:
                    v = float(v)
                    row.append(v)
                    row_text.append(f"{v:+.1f}%")
        z.append(row)
        text.append(row_text)

    all_vals = [v for row in z for v in row if v is not None]
    if all_vals:
        vmax = max(abs(min(all_vals)), abs(max(all_vals)))
        vmax = vmax if vmax > 0 else 1.0
    else:
        vmax = 1.0

    fig = go.Figure(go.Heatmap(
        x=x_labels,
        y=y_labels,
        z=z,
        text=text,
        texttemplate="%{text}",
        textfont={"size": 11, "color": "#2c3e50"},
        colorscale='RdYlGn',
        zmin=-vmax, zmax=vmax, zmid=0,
        colorbar=dict(title='收益%', thickness=12),
        hovertemplate=(
            '事件: %{y}<br>策略: %{x}<br>'
            '收益: %{z:.2f}%<extra></extra>'
        ),
    ))

    fig.update_layout(
        height=max(280, len(event_ids) * 32 + 140),
        margin=dict(l=160, r=80, t=20, b=40),
        yaxis=dict(autorange='reversed', tickfont=dict(size=11)),
        xaxis=dict(side='top', tickfont=dict(size=12)),
    )
    return fig


def _create_per_event_datatable(per_event, configs, slug_map):
    """逐事件明细 DataTable：可排序、分页、导出"""
    from dash import dash_table

    rows = []
    for eid, ev in per_event.items():
        slug = slug_map.get(eid, '')
        row = {
            'event_id': eid,
            'event_slug': _short_slug(slug, max_len=36) if slug else '',
            'market_id': ev['market_id'],
        }
        for cfg in configs:
            s = ev['strategies'].get(cfg.name, {})
            if s.get('status') != 'ok':
                row[cfg.name] = '—'
            else:
                v = s['metrics'].get('total_return')
                row[cfg.name] = (f"{float(v):+.2f}%"
                                 if v is not None else '—')
        rows.append(row)

    columns = [
        {'name': '事件 ID', 'id': 'event_id'},
        {'name': '事件', 'id': 'event_slug'},
        {'name': '市场 ID', 'id': 'market_id'},
    ] + [{'name': c.name, 'id': c.name} for c in configs]

    return dash_table.DataTable(
        id='research-batch-events-table',
        data=rows,
        columns=columns,
        sort_action='native',
        page_action='native',
        page_size=15,
        page_current=0,
        export_format='csv',
        export_headers='display',
        style_table={'overflowX': 'auto', 'minWidth': '100%'},
        style_header={
            'backgroundColor': '#f1f3f5', 'fontWeight': 'bold',
            'textAlign': 'center',
            'borderBottom': '1px solid #dee2e6',
            'padding': '6px 8px', 'fontSize': '12px',
        },
        style_cell={
            'textAlign': 'center', 'padding': '5px 8px',
            'fontSize': '13px', 'border': '1px solid #e9ecef',
            'whiteSpace': 'normal', 'height': 'auto',
        },
        style_cell_conditional=[
            {'if': {'column_id': 'event_slug'},
             'textAlign': 'left', 'minWidth': '220px'},
            {'if': {'column_id': 'event_id'},
             'minWidth': '80px'},
            {'if': {'column_id': 'market_id'},
             'minWidth': '90px'},
        ],
    )

@callback(
    Output('research-batch-jump-btn', 'disabled'),
    Input('research-batch-jump-event', 'value'),
)
def _toggle_jump_btn(event_id):
    return not bool(event_id)

@callback(
    Output('global-params', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('research-batch-jump-btn', 'n_clicks'),
    State('research-batch-jump-event', 'value'),
    State('research-params-store', 'data'),
    State('global-params', 'data'),
    prevent_initial_call=True,
)
def import_batch_event_to_backtest(n_clicks, event_id,
                                    research_params, global_params):
    """把批量研究里某个事件带入信号回测"""
    if not n_clicks or not event_id:
        return no_update, no_update

    p = _gp_merge(global_params)

    if research_params:
        # 只带公共参数，event_id 用批量里选的那个
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

    # 事件：用批量里选的那个
    p['event_id'] = event_id
    # 市场：清空，让 /backtest 页面按事件自动选目标市场
    p['market_id'] = None

    return p, '/backtest'