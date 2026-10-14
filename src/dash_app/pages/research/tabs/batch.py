# src/dash_app/pages/research/tabs/batch.py
"""
策略研究 - 批量研究 Tab

两种模式：
- 多事件 × 目标市场（每事件一个目标市场）
- 单事件 × 多子市场（同一事件下的多个市场）

输出：
- 聚合表
- 标签 × 策略 收益矩阵热力图
- 逐条明细 DataTable（排序 / 分页 / 导出）
"""

import pandas as pd
from dash import (html, dcc, Input, Output, State, callback,
                  ctx, no_update)
import plotly.graph_objects as go

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
    get_markets_by_event,
)
from src.dash_app.utils.research.batch import BatchEngine
from src.dash_app.utils.research.strategy_config import StrategyConfig
from src.dash_app.utils.ui.table import td, table as tbl
from src.dash_app.pages.shared.params_panel import create_shared_panel


STRATEGY_COLORS = {'a': '#3498db', 'b': '#e74c3c', 'c': '#2ecc71'}


def render_batch_tab(global_params=None, series='7d'):
    return html.Div([
        # ---- batch-* 配置区（信号参数 + 交易设置，不含事件/市场）----
        create_shared_panel(global_params=global_params, series=series,
                            prefix='batch', include_event_market=False),
        dcc.Store(id='batch-params-store', data={}),

        html.Div([
            html.P("选择研究模式后运行。模式A=多事件；模式B=单事件多子市场。",
                   style={'fontSize': '13px', 'color': '#495057',
                          'marginBottom': '10px'}),

            # ---- 模式单选 ----
            dcc.RadioItems(
                id='research-batch-mode',
                options=[
                    {'label': ' 多事件 × 目标市场',
                     'value': 'multi_event'},
                    {'label': ' 单事件 × 多子市场',
                     'value': 'multi_market'},
                ],
                value='multi_event',
                inline=True,
                style={'marginBottom': '12px', 'fontSize': '13px'},
            ),

            # ---- 模式 A 控件 ----
            html.Div([
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
            ], id='research-batch-controls-A'),

            # ---- 模式 B 控件 ----
            html.Div([
                html.Label("选择事件：",
                           style={'fontWeight': 'bold',
                                  'fontSize': '13px',
                                  'marginBottom': '4px',
                                  'display': 'block'}),
                dcc.Dropdown(
                    id='research-batch-event-single',
                    options=[],
                    value=None,
                    clearable=False,
                    placeholder='选择事件',
                    style={'width': '100%', 'marginBottom': '10px'},
                ),
                html.Label("选择子市场（默认全选）：",
                           style={'fontWeight': 'bold',
                                  'fontSize': '13px',
                                  'marginBottom': '4px',
                                  'display': 'block'}),
                dcc.Dropdown(
                    id='research-batch-market-selector',
                    options=[],
                    value=[],
                    multi=True,
                    placeholder='加载中...',
                    style={'width': '100%', 'marginBottom': '10px'},
                ),
            ], id='research-batch-controls-B',
               style={'display': 'none'}),

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

            # ---- 跳转区（模式 A 用事件，模式 B 用市场；功能挂起中）----
            html.Div([
                html.Label("（实验）选择一条结果带入信号回测：",
                           style={'fontSize': '12px',
                                  'color': '#adb5bd',
                                  'marginRight': '8px',
                                  'verticalAlign': 'middle'}),
                dcc.Dropdown(
                    id='research-batch-jump-event',
                    options=[],
                    value=None,
                    placeholder='选择',
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
                        'backgroundColor': '#adb5bd', 'color': 'white',
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


# ==================== 回调：模式切换 ====================

@callback(
    Output('research-batch-controls-A', 'style'),
    Output('research-batch-controls-B', 'style'),
    Input('research-batch-mode', 'value'),
)
def _toggle_batch_mode(mode):
    if mode == 'multi_market':
        return {'display': 'none'}, {'display': 'block'}
    return {'display': 'block'}, {'display': 'none'}


# ==================== 回调：事件列表刷新 ====================

@callback(
    Output('research-batch-event-selector', 'options'),
    Output('research-batch-event-selector', 'value'),
    Output('research-batch-event-single', 'options'),
    Output('research-batch-event-single', 'value'),
    Input('series-selector', 'value'),
)
def _populate_batch_events(series):
    """系列变化 → 刷新两个事件下拉。模式A多选默认全选；模式B单选默认最后一个。"""
    pairs, slug_map = _get_all_pairs(series or '7d')
    options = []
    values = []
    for eid, _ in pairs:
        slug = slug_map.get(eid, '')
        label = _short_slug(slug, max_len=50) if slug else str(eid)
        options.append({'label': label, 'value': eid})
        values.append(eid)

    single_value = values[-1] if values else None
    return options, values, options, single_value


# ==================== 回调：模式 B 事件 → 市场 ====================

@callback(
    Output('research-batch-market-selector', 'options'),
    Output('research-batch-market-selector', 'value'),
    Input('research-batch-event-single', 'value'),
)
def _populate_batch_markets(event_id):
    """模式 B：事件变化 → 刷新市场多选，默认全选。"""
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


# ==================== 回调：运行批量 ====================

@callback(
    Output('research-batch-results', 'children'),
    Output('research-batch-jump-event', 'options'),
    Output('research-batch-jump-event', 'value'),
    Output('research-batch-jump-area', 'style'),
    Input('research-batch-run-btn', 'n_clicks'),
    State('research-batch-mode', 'value'),
    State('batch-params-store', 'data'),
    State('series-selector', 'value'),
    State('research-strategy-a-store', 'data'),
    State('research-strategy-b-store', 'data'),
    State('research-strategy-c-store', 'data'),
    State('research-batch-event-selector', 'value'),
    State('research-batch-event-single', 'value'),
    State('research-batch-market-selector', 'value'),
    prevent_initial_call=True,
)
def run_batch(n_clicks, mode, base_params, series, sa, sb, sc,
              selected_events, single_event, selected_markets):
    _hidden = {'display': 'none', 'marginTop': '12px'}
    _shown = {'display': 'block', 'marginTop': '12px'}

    if not n_clicks:
        return (no_update, no_update, no_update, no_update)
    if not base_params:
        return (_warn("请先在上方配置信号参数和交易设置（作为参数模板）"),
                [], None, _hidden)

    series = series or '7d'
    mode = mode or 'multi_event'

    # 1. 策略
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

    # 2. 构造 pairs + label_map
    if mode == 'multi_market':
        pairs, label_map = _build_multi_market_pairs(
            single_event, selected_markets)
        if not pairs:
            return (_warn("请选择一个事件及至少一个子市场"),
                    [], None, _hidden)
    else:
        pairs, label_map = _build_multi_event_pairs(
            series, selected_events)
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

    # 4. 跳转下拉选项（功能挂起，只为 UI 完整性）
    jump_options = []
    for key in result['per_event'].keys():
        jump_options.append({'label': label_map.get(key, key),
                             'value': key})

    return (_render_results(result, configs, label_map, mode),
            jump_options, None, _shown)


# ==================== 辅助：pairs 构造 ====================

def _build_multi_event_pairs(series, selected_events):
    """模式 A：多事件 × 各自目标市场。
    返回 (pairs, label_map)；label_map key = "eid:mid"
    """
    all_pairs, slug_map = _get_all_pairs(series)
    if not all_pairs:
        return [], {}
    if selected_events:
        selected_set = set(selected_events)
        pairs = [(eid, mid) for eid, mid in all_pairs
                 if eid in selected_set]
    else:
        pairs = all_pairs

    label_map = {}
    for eid, mid in pairs:
        slug = slug_map.get(eid, '')
        label_map[f"{eid}:{mid}"] = (
            _short_slug(slug, max_len=30) if slug else str(eid))
    return pairs, label_map


def _build_multi_market_pairs(event_id, selected_markets):
    """模式 B：单事件 × 多子市场。
    返回 (pairs, label_map)；label_map key = "eid:mid"
    """
    if not event_id or not selected_markets:
        return [], {}
    pairs = [(event_id, mid) for mid in selected_markets]

    markets = get_markets_by_event(event_id)
    range_map = {}
    if markets is not None and not markets.empty:
        for _, row in markets.iterrows():
            r_start = int(row['range_start'])
            r_end = (int(row['range_end'])
                     if not pd.isna(row['range_end'])
                     and row['range_end'] is not None
                     else '∞')
            range_map[row['id']] = f"{r_start}-{r_end}"

    label_map = {}
    for eid, mid in pairs:
        label_map[f"{eid}:{mid}"] = range_map.get(mid, str(mid))
    return pairs, label_map


# ==================== 辅助：通用 ====================

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


# ==================== 渲染 ====================

def _render_results(result, configs, label_map, mode):
    aggregate = result.get('aggregate', {})
    per_event = result.get('per_event', {})

    return html.Div([
        html.H5(f"📊 聚合统计（{result['n_pairs']} 条记录）",
                style={'margin': '10px 0'}),
        _render_aggregate_table(aggregate, configs),

        html.H5("🔥 标签 × 策略 收益矩阵",
                style={'margin': '20px 0 10px 0'}),
        html.Div("每格 = 该策略在该条记录上的总收益率（绿正红负）",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '6px'}),
        dcc.Graph(figure=_create_matrix_heatmap(
            per_event, configs, label_map)),

        html.H5("📋 逐条明细",
                style={'margin': '20px 0 10px 0'}),
        html.Div("💡 点表头排序 · 右上可导出 CSV",
                 style={'fontSize': '12px', 'color': '#6c757d',
                        'marginBottom': '6px'}),
        _create_detail_datatable(per_event, configs, label_map),
    ])


def _render_aggregate_table(aggregate, configs):
    headers = ['策略', '有效条数', '收益均值', '收益中位数',
               '收益标准差', '正条率', '夏普均值', '胜率均值']
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


def _create_matrix_heatmap(per_event, configs, label_map):
    keys = list(per_event.keys())
    if not keys:
        return go.Figure()

    y_labels = [label_map.get(k, str(k)) for k in keys]
    x_labels = [c.name for c in configs]

    z = []
    text = []
    for k in keys:
        row = []
        row_text = []
        for cfg in configs:
            s = per_event[k]['strategies'].get(cfg.name, {})
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
        x=x_labels, y=y_labels, z=z,
        text=text, texttemplate="%{text}",
        textfont={"size": 11, "color": "#2c3e50"},
        colorscale='RdYlGn',
        zmin=-vmax, zmax=vmax, zmid=0,
        colorbar=dict(title='收益%', thickness=12),
        hovertemplate=(
            '标签: %{y}<br>策略: %{x}<br>'
            '收益: %{z:.2f}%<extra></extra>'
        ),
    ))

    fig.update_layout(
        height=max(280, len(keys) * 32 + 140),
        margin=dict(l=180, r=80, t=20, b=40),
        yaxis=dict(autorange='reversed', tickfont=dict(size=11)),
        xaxis=dict(side='top', tickfont=dict(size=12)),
    )
    return fig


def _create_detail_datatable(per_event, configs, label_map):
    from dash import dash_table

    rows = []
    for key, ev in per_event.items():
        row = {
            'label': label_map.get(key, str(key)),
            'event_id': ev['event_id'],
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
        {'name': '标签', 'id': 'label'},
        {'name': '事件 ID', 'id': 'event_id'},
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
            {'if': {'column_id': 'label'},
             'textAlign': 'left', 'minWidth': '180px'},
            {'if': {'column_id': 'event_id'},
             'minWidth': '80px'},
            {'if': {'column_id': 'market_id'},
             'minWidth': '90px'},
        ],
    )


# ==================== 回调：跳转按钮 enable/disable ====================

@callback(
    Output('research-batch-jump-btn', 'disabled'),
    Input('research-batch-jump-event', 'value'),
)
def _toggle_jump_btn(value):
    return not bool(value)


# ==================== 回调：跳转到信号回测（挂起）====================

from dash import ALL  # noqa: E402
from src.dash_app.state.global_params import (
    merge as _gp_merge,
    window_type_to_engine as _wt2e,
)


@callback(
    Output('global-params', 'data', allow_duplicate=True),
    Output('url', 'pathname', allow_duplicate=True),
    Input('research-batch-jump-btn', 'n_clicks'),
    State('research-batch-jump-event', 'value'),
    State('research-params-store', 'data'),
    State('global-params', 'data'),
    prevent_initial_call=True,
)
def import_batch_to_backtest(n_clicks, key, research_params, global_params):
    """挂起中：跨页带参功能失效，仅保留代码。"""
    if not n_clicks or not key:
        return no_update, no_update
    p = _gp_merge(global_params)
    if research_params:
        for k in ('price_type', 'window_type', 'window_custom_hours',
                  'initial_capital', 'position_mode', 'position_size',
                  'backtest_range', 'backtest_range_custom'):
            if research_params.get(k) is not None:
                p[k] = research_params[k]
        wt = research_params.get('window_type')
        if wt:
            eng = _wt2e(wt, research_params.get('window_custom_hours'))
            p.update(eng)
    try:
        eid, mid = key.split(':', 1)
        p['event_id'] = eid
        p['market_id'] = mid
    except ValueError:
        pass
    return p, '/backtest'