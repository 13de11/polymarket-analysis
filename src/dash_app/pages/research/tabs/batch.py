# src/dash_app/pages/research/tabs/batch.py
"""
策略研究 - 批量研究 Tab（小版本）

对当前系列的全部事件跑一遍已启用的策略，输出：
- 聚合表：每策略的收益均值/中位数/标准差/胜事件率
- 逐事件表：事件 × 策略 的收益矩阵

策略复用「策略对比」Tab 里配置好的卡片（A/B/C）。
"""

from dash import html, dcc, Input, Output, State, callback, no_update

from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
)
from src.dash_app.utils.research.batch import BatchEngine
from src.dash_app.utils.research.strategy_config import StrategyConfig
from src.dash_app.utils.ui.table import td, table as tbl


STRATEGY_COLORS = {'a': '#3498db', 'b': '#e74c3c', 'c': '#2ecc71'}


def render_batch_tab():
    return html.Div([
        html.Div([
            html.P("对当前系列的全部事件跑一遍「策略对比」里已启用的策略。",
                   style={'fontSize': '13px', 'color': '#495057',
                          'marginBottom': '6px'}),
            html.P("⚠️ 小版本：事件范围固定为「全系列」，策略复用 A/B/C 卡片。",
                   style={'fontSize': '12px', 'color': '#856404',
                          'marginBottom': '10px'}),
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
        ], style={'padding': '15px', 'backgroundColor': '#f8f9fa',
                  'borderRadius': '8px'}),
        dcc.Loading(
            id='research-batch-loading',
            type='default', color='#6c5ce7',
            children=[html.Div(id='research-batch-results',
                               style={'marginTop': '15px'})],
        ),
    ])


# ==================== 回调 ====================

@callback(
    Output('research-batch-results', 'children'),
    Input('research-batch-run-btn', 'n_clicks'),
    State('research-params-store', 'data'),
    State('series-selector', 'value'),
    State('research-strategy-a-store', 'data'),
    State('research-strategy-b-store', 'data'),
    State('research-strategy-c-store', 'data'),
    prevent_initial_call=True,
)
def run_batch(n_clicks, base_params, series, sa, sb, sc):
    if not n_clicks:
        return html.Div()
    if not base_params:
        return _warn("请先在左侧选择事件和市场（作为参数模板）")

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
        return _warn("至少启用一个策略（在「策略对比」Tab 里勾选）")

    # 2. 取当前系列全部事件 + 目标市场
    pairs = _get_all_pairs(series)
    if not pairs:
        return _warn(f"系列 {series} 下没有可用的事件+市场组合")

    # 3. 跑批量
    try:
        result = BatchEngine.run_batch(
            base_params, configs, pairs, series=series,
        )
    except Exception as e:
        return _warn(f"批量研究失败：{type(e).__name__}: {e}")

    if not result or not result.get('per_event'):
        return _warn("批量研究无结果")

    # 4. 渲染
    return _render_results(result, configs)


# ==================== 辅助 ====================

def _get_all_pairs(series):
    events = get_elon_tweet_events(series)
    if events is None or events.empty:
        return []
    ids = events['id'].tolist()
    targets = get_target_markets_batch(ids)
    pairs = []
    for eid in ids:
        t = targets.get(eid)
        if t:
            pairs.append((eid, t['id']))
    return pairs


def _warn(msg):
    return html.Div(msg, style={
        'padding': '12px 16px', 'backgroundColor': '#fff3cd',
        'borderLeft': '4px solid #f39c12', 'borderRadius': '4px',
        'fontSize': '13px', 'color': '#856404',
    })


def _render_results(result, configs):
    aggregate = result.get('aggregate', {})
    per_event = result.get('per_event', {})

    return html.Div([
        html.H5(f"📊 聚合统计（{result['n_pairs']} 个事件）",
                style={'margin': '10px 0'}),
        _render_aggregate_table(aggregate, configs),

        html.H5(f"📋 逐事件收益（%）",
                style={'margin': '20px 0 10px 0'}),
        _render_per_event_table(per_event, configs),
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


def _render_per_event_table(per_event, configs):
    headers = ['事件 ID', '市场 ID'] + [c.name for c in configs]
    rows = []
    for eid, ev in per_event.items():
        cells = [
            td(str(eid)),
            td(str(ev['market_id'])),
        ]
        for cfg in configs:
            s = ev['strategies'].get(cfg.name, {})
            if s.get('status') != 'ok':
                cells.append(td('—',
                                color='#e74c3c'))
            else:
                v = s['metrics'].get('total_return')
                if v is None:
                    cells.append(td('—'))
                else:
                    color = '#28a745' if v > 0 else \
                            '#e74c3c' if v < 0 else '#6c757d'
                    cells.append(td(f"{v:+.2f}%", color=color,
                                    fontWeight='bold'))
        rows.append(html.Tr(cells))
    return tbl(headers, rows)