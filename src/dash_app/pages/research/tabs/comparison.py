# src/dash_app/pages/research/tabs/comparison.py
"""
策略研究 - 策略对比 Tab
- 动态参数覆盖
- 参数摘要列
- 导出指标表 / 交易明细 CSV
"""

import pandas as pd
from dash import html, dcc, Input, Output, State, callback, ctx, no_update
import plotly.graph_objects as go

from src.dash_app.utils.comparison.engine import ComparisonEngine
from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, METRIC_SCHEMA, fmt_metric,
)
from src.dash_app.utils.research.strategy_config import (
    StrategyConfig, get_strategy_options,
    get_strategy_param_keys, get_all_override_param_keys,
)
from src.dash_app.utils.research.serialize import to_python
from src.dash_app.utils.ui.table import td, table as tbl


STRATEGY_COLORS = {'a': '#3498db', 'b': '#e74c3c', 'c': '#2ecc71'}
DEFAULT_CARD_OVERRIDES = {
    'a': {'price_threshold': 0.005},
    'b': {'price_threshold': 0.010},
    'c': {},
}
DEFAULT_ENABLED = {'a', 'b'}


# ========== UI ==========

def _create_override_row(idx_lower, param_key):
    schema = PARAM_SCHEMA[param_key]
    defaults = DEFAULT_CARD_OVERRIDES.get(idx_lower, {})
    is_default = param_key in defaults
    default_val = defaults.get(param_key, schema['default'])
    base_id = f'strategy-{idx_lower}-{param_key}'

    row_children = [
        dcc.Checklist(
            id=f'{base_id}-enable',
            options=[{'label': '', 'value': 'on'}],
            value=['on'] if is_default else [],
            style={'display': 'inline-block', 'width': '18px',
                   'marginRight': '4px', 'verticalAlign': 'middle'},
        ),
        html.Label(schema['label'], style={
            'display': 'inline-block', 'width': '72px',
            'fontSize': '11px', 'color': '#495057',
            'verticalAlign': 'middle',
        }),
    ]

    if schema['type'] == 'bool':
        row_children.append(dcc.RadioItems(
            id=f'{base_id}-value',
            options=[{'label': ' 开', 'value': True},
                     {'label': ' 关', 'value': False}],
            value=default_val, inline=True,
            style={'display': 'inline-block', 'fontSize': '11px',
                   'verticalAlign': 'middle'},
        ))
    else:
        row_children.append(dcc.Input(
            id=f'{base_id}-value', type='number', value=default_val,
            step=schema.get('step', 1), debounce=True,
            style={'width': '62px', 'fontSize': '11px',
                   'padding': '1px 4px', 'border': '1px solid #ced4da',
                   'borderRadius': '3px'},
        ))

    return html.Div(row_children, id=f'{base_id}-row',
                    style={'marginBottom': '2px', 'lineHeight': '1.7'})


def _create_strategy_card(idx_lower, default_name):
    color = STRATEGY_COLORS[idx_lower]
    enabled = ['on'] if idx_lower in DEFAULT_ENABLED else []
    all_params = get_all_override_param_keys()

    return html.Div([
        html.Div([
            dcc.Checklist(
                id=f'strategy-{idx_lower}-enable',
                options=[{'label': '', 'value': 'on'}],
                value=enabled,
                style={'display': 'inline-block', 'marginRight': '6px',
                       'verticalAlign': 'middle'},
            ),
            dcc.Input(
                id=f'strategy-{idx_lower}-name', type='text',
                value=default_name, debounce=True,
                style={'width': '96px', 'fontSize': '13px',
                       'fontWeight': 'bold', 'padding': '2px 4px',
                       'border': '1px solid #ced4da', 'borderRadius': '3px'},
            ),
            html.Span('●', style={'color': color, 'fontSize': '20px',
                                  'marginLeft': '6px',
                                  'verticalAlign': 'middle'}),
        ], style={'marginBottom': '8px'}),

        html.Label('策略类型', style={'fontSize': '11px', 'color': '#6c757d'}),
        dcc.Dropdown(
            id=f'strategy-{idx_lower}-type',
            options=get_strategy_options(),
            value='direction_signal', clearable=False,
            style={'fontSize': '12px', 'marginBottom': '8px'},
        ),

        html.Label('参数覆盖（不勾则用左侧基础值）', style={
            'fontSize': '11px', 'color': '#6c757d',
            'display': 'block', 'marginBottom': '4px',
        }),
        html.Div([_create_override_row(idx_lower, p) for p in all_params]),

        dcc.Store(id=f'research-strategy-{idx_lower}-store'),
    ], style={
        'flex': '1', 'minWidth': '210px',
        'border': f'2px solid {color}', 'borderRadius': '6px',
        'padding': '10px', 'backgroundColor': '#fdfdfd',
    })


def render_comparison_tab():
    return html.Div([
        html.Div([
            html.P(
                "每个策略 = 左侧基础参数 + 卡片中勾选的覆盖项。",
                style={'fontSize': '13px', 'color': '#495057',
                       'marginBottom': '10px'},
            ),
            html.Div([
                _create_strategy_card('a', '策略A'),
                _create_strategy_card('b', '策略B'),
                _create_strategy_card('c', '策略C'),
            ], style={'display': 'flex', 'gap': '10px',
                      'marginBottom': '15px', 'flexWrap': 'wrap'}),
            html.Div([
                html.Button('🚀 运行对比',
                            id='research-comparison-run-btn', n_clicks=0,
                            style=_btn_style('#6c5ce7')),
                html.Button('📥 导出指标表',
                            id='research-comparison-export-metrics-btn',
                            n_clicks=0,
                            style={**_btn_style('#6c757d'),
                                   'marginLeft': '10px'}),
                html.Button('📥 导出交易明细',
                            id='research-comparison-export-trades-btn',
                            n_clicks=0,
                            style={**_btn_style('#6c757d'),
                                   'marginLeft': '6px'}),
            ]),
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '8px'}),
        dcc.Loading(
            id='research-comparison-loading',
            type='default', color='#6c5ce7',
            children=[html.Div(id='research-comparison-results',
                               style={'marginTop': '15px'})],
        ),
        dcc.Store(id='research-comparison-results-store'),
        dcc.Download(id='research-comparison-download'),
    ])


def _btn_style(color):
    return {
        'padding': '10px 20px', 'backgroundColor': color,
        'color': 'white', 'border': 'none', 'borderRadius': '6px',
        'fontSize': '14px', 'fontWeight': 'bold', 'cursor': 'pointer',
    }


# ========== 卡片同步 ==========

def _register_card_sync(idx_lower):
    prefix = f'strategy-{idx_lower}'
    store_id = f'research-strategy-{idx_lower}-store'
    all_params = get_all_override_param_keys()

    inputs = [
        Input(f'{prefix}-enable', 'value'),
        Input(f'{prefix}-name', 'value'),
        Input(f'{prefix}-type', 'value'),
    ]
    for p in all_params:
        inputs.append(Input(f'{prefix}-{p}-enable', 'value'))
        inputs.append(Input(f'{prefix}-{p}-value', 'value'))

    def _make_fn():
        def sync(*args):
            enabled, name, stype = args[0], args[1], args[2] or 'direction_signal'
            rest = args[3:]
            allowed = set(get_strategy_param_keys(stype))
            params = {}
            for i, p in enumerate(all_params):
                en, val = rest[i * 2], rest[i * 2 + 1]
                if en and p in allowed and val is not None:
                    params[p] = val
            return {
                'enabled': bool(enabled),
                'name': name or f'策略{idx_lower.upper()}',
                'strategy_type': stype,
                'params': params,
            }
        sync.__name__ = f'_sync_{idx_lower}'
        return sync

    callback(Output(store_id, 'data'), *inputs)(_make_fn())


def _register_param_visibility(idx_lower):
    all_params = get_all_override_param_keys()
    outputs = [Output(f'strategy-{idx_lower}-{p}-row', 'style')
               for p in all_params]

    def _make_vis():
        def update(stype):
            allowed = set(get_strategy_param_keys(stype or 'direction_signal'))
            return tuple(
                {'marginBottom': '2px', 'lineHeight': '1.7'}
                if p in allowed else {'display': 'none'}
                for p in all_params
            )
        update.__name__ = f'_vis_{idx_lower}'
        return update

    callback(*outputs,
             Input(f'strategy-{idx_lower}-type', 'value'),
             prevent_initial_call=False)(_make_vis())


for _idx in ['a', 'b', 'c']:
    _register_card_sync(_idx)
    _register_param_visibility(_idx)


# ========== 运行对比 ==========

@callback(
    Output('research-comparison-results', 'children'),
    Output('research-comparison-results-store', 'data'),
    Input('research-comparison-run-btn', 'n_clicks'),
    State('research-params-store', 'data'),
    State('series-selector', 'value'),
    State('research-strategy-a-store', 'data'),
    State('research-strategy-b-store', 'data'),
    State('research-strategy-c-store', 'data'),
    prevent_initial_call=True,
)
def run_research_comparison(n_clicks, params, series, sa, sb, sc):
    if not n_clicks:
        return no_update, no_update
    if not params or not params.get('market_id'):
        return _warn("请先在左侧选择事件和市场"), None

    configs = []
    for il, sd in [('a', sa), ('b', sb), ('c', sc)]:
        if not sd or not sd.get('enabled'):
            continue
        configs.append(StrategyConfig(
            name=sd.get('name') or f'策略{il.upper()}',
            strategy_type=sd.get('strategy_type', 'direction_signal'),
            params=sd.get('params', {}),
            color=STRATEGY_COLORS.get(il),
        ))

    if not configs:
        return _warn("至少启用一个策略"), None

    try:
        results = ComparisonEngine.run_comparison(params, configs, series or '7d')
    except Exception as e:
        return _warn(f"运行失败：{type(e).__name__}: {e}"), None

    if not results:
        return _warn("对比运行失败，请检查参数"), None

    return _render_results(results), _results_to_store(results)


def _warn(msg):
    return html.Div(msg, style={
        'padding': '12px 16px', 'backgroundColor': '#fff3cd',
        'borderLeft': '4px solid #f39c12', 'borderRadius': '4px',
        'fontSize': '13px', 'color': '#856404',
    })


def _summarize_params(params):
    if not params:
        return ''
    return ', '.join(
        f"{PARAM_SCHEMA.get(k, {}).get('label', k)}={v}"
        for k, v in params.items()
    )


def _results_to_store(results):
    strategies = []
    for name, r in results.items():
        cfg = r.get('config') or {}
        strategies.append({
            'name': name,
            'status': r.get('status'),
            'error': r.get('error'),
            'params': to_python(cfg.get('params') or {}),
            'params_summary': _summarize_params(cfg.get('params') or {}),
            'metrics': to_python(r.get('metrics') or {}),
            'trades': to_python(r.get('trades') or []),
            'elapsed_sec': r.get('elapsed_sec', 0),
        })
    return {'strategies': strategies}


def _render_results(results):
    errors = {k: v for k, v in results.items() if v.get('status') == 'error'}
    oks = {k: v for k, v in results.items() if v.get('status') == 'ok'}
    children = []

    for name, r in errors.items():
        children.append(html.Div([
            html.Strong(f"⚠️ {name} 运行失败："),
            html.Span(r.get('error') or '未知错误'),
        ], style={
            'padding': '8px 12px', 'backgroundColor': '#fdecea',
            'borderLeft': '4px solid #e74c3c', 'borderRadius': '4px',
            'marginBottom': '8px', 'fontSize': '13px', 'color': '#c0392b',
        }))

    if oks:
        children.append(dcc.Graph(figure=_create_comparison_chart(oks),
                                  style={'height': '400px'}))
        children.append(html.H5("📊 绩效指标对比",
                                style={'margin': '15px 0 10px 0',
                                       'color': '#2c3e50'}))
        children.append(_create_comparison_table(oks))

    return html.Div(children)


def _create_comparison_chart(results):
    fig = go.Figure()
    for name, r in results.items():
        curve = r.get('equity_curve') or []
        if not curve or not isinstance(curve[0], dict):
            continue
        color = (r.get('config') or {}).get('color') or '#888'
        fig.add_trace(go.Scatter(
            x=[p.get('timestamp') for p in curve],
            y=[p.get('equity') for p in curve],
            name=name, line=dict(color=color, width=2),
        ))
    fig.update_layout(
        title='策略资金曲线对比', xaxis_title='时间', yaxis_title='权益 ($)',
        hovermode='x', height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02,
                    xanchor='center', x=0.5),
    )
    return fig


def _create_comparison_table(results):
    headers = ['策略', '参数覆盖', '状态', '交易次数', '胜率', '盈亏比',
               '总收益', '最大回撤', '夏普', '耗时(s)']
    rows = []
    for name, r in results.items():
        m = r.get('metrics') or {}
        cfg = r.get('config') or {}
        color = cfg.get('color') or '#333'
        summary = _summarize_params(cfg.get('params') or {})
        rows.append(html.Tr([
            td([html.Span('●', style={'color': color,
                                      'marginRight': '4px'}),
                html.Span(name, style={'fontWeight': 'bold'})]),
            td(summary or '—', fontSize='11px', color='#6c757d'),
            td(r.get('status', '—')),
            td(fmt_metric('total_trades', m.get('total_trades', 0))),
            td(fmt_metric('win_rate', m.get('win_rate', 0))),
            td(fmt_metric('profit_factor', m.get('profit_factor', 0))),
            td(fmt_metric('total_return', m.get('total_return', 0))),
            td(fmt_metric('max_drawdown_pct',
                          m.get('max_drawdown_pct', 0))),
            td(fmt_metric('sharpe_ratio', m.get('sharpe_ratio', 0))),
            td(f"{r.get('elapsed_sec', 0):.2f}"),
        ]))
    return tbl(headers, rows)


# ========== 导出 ==========

@callback(
    Output('research-comparison-download', 'data'),
    Input('research-comparison-export-metrics-btn', 'n_clicks'),
    Input('research-comparison-export-trades-btn', 'n_clicks'),
    State('research-comparison-results-store', 'data'),
    prevent_initial_call=True,
)
def export_comparison(n_metrics, n_trades, store_data):
    if not store_data or not store_data.get('strategies'):
        return no_update

    if ctx.triggered_id == 'research-comparison-export-metrics-btn':
        rows = []
        for s in store_data['strategies']:
            m = s.get('metrics') or {}
            rows.append({
                '策略': s['name'],
                '参数覆盖': s.get('params_summary', ''),
                '状态': s['status'],
                '交易次数': m.get('total_trades'),
                '胜率(%)': m.get('win_rate'),
                '盈亏比': m.get('profit_factor'),
                '总收益(%)': m.get('total_return'),
                '最大回撤(%)': m.get('max_drawdown_pct'),
                '夏普': m.get('sharpe_ratio'),
                '耗时(s)': s.get('elapsed_sec'),
            })
        df = pd.DataFrame(rows)
        return dcc.send_data_frame(df.to_csv, 'strategy_metrics.csv',
                                   index=False, encoding='utf-8-sig')

    rows = []
    for s in store_data['strategies']:
        for t in s.get('trades') or []:
            row = {'策略': s['name']}
            row.update(t)
            rows.append(row)
    if not rows:
        df = pd.DataFrame(columns=['策略', '提示'])
        df.loc[0] = ['(无交易)', '所选策略均无已完成交易']
    else:
        df = pd.DataFrame(rows)
    return dcc.send_data_frame(df.to_csv, 'strategy_trades.csv',
                               index=False, encoding='utf-8-sig')