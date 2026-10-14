# src/dash_app/pages/research/filter_panel.py
"""
策略研究 - comparison tab 的回调

Phase C1 修订：
- save_cmp_params：只收集事件/市场/交易设置（execution 组）→ cmp-params-store
  信号参数（dimension + signal）在策略卡片各自配置，不再放顶部
- update_cmp_events：series + pathname + global-params → cmp-event-selector
- update_cmp_markets：cmp-event-selector → cmp-market-selector 联动
- toggle_cmp_range_custom：cmp-range 折叠控件显隐
- sync_research_params_from_global：临时给 sensitivity/batch 用
"""

import pandas as pd
from dash import (Input, Output, State, callback, no_update)
from src.dash_app.utils.parsing import safe_float
from src.dash_app.utils.data_loader import (
    get_elon_tweet_events, get_target_market,
    get_target_markets_batch,
)
from src.dash_app.state.global_params import merge as _gp_merge


# ==================== cmp 事件列表（series 切换时更新） ====================

@callback(
    Output('cmp-event-selector', 'options'),
    Output('cmp-event-selector', 'value'),
    Input('series-selector', 'value'),
    Input('url', 'pathname'),
    Input('global-params', 'data'),
    prevent_initial_call=False,
)
def update_cmp_events(series, pathname, global_params):
    """series 变化或页面加载时，更新 cmp-event-selector 选项"""
    if pathname != '/research':
        return no_update, no_update
    events_df = get_elon_tweet_events(series)
    if events_df.empty:
        return [], None
    event_ids = events_df['id'].tolist()
    targets_map = get_target_markets_batch(event_ids)
    event_options = []
    for _, row in events_df.iterrows():
        target = targets_map.get(row['id'])
        if target:
            r_start = int(target['range_start'])
            r_end = (int(target['range_end'])
                     if target['range_end']
                     and not pd.isna(target['range_end'])
                     else '∞')
            label = f"{row['slug']} (命中: {r_start}-{r_end})"
        else:
            label = row['slug']
        event_options.append({'label': label, 'value': row['id']})
    target_event = None
    if global_params and global_params.get('event_id') in event_ids:
        target_event = global_params['event_id']
    if target_event is None and not events_df.empty:
        target_event = events_df.iloc[-1]['id']
    return event_options, target_event


# ==================== cmp 事件→市场联动 ====================

@callback(
    Output('cmp-market-selector', 'options'),
    Output('cmp-market-selector', 'value'),
    Input('cmp-event-selector', 'value'),
    State('cmp-market-selector', 'value'),
    prevent_initial_call=False,
)
def update_cmp_markets(event_id, current_market):
    if not event_id:
        return [], None
    target = get_target_market(event_id)
    if not target:
        return [], None
    r_start = int(target['range_start'])
    r_end = (int(target['range_end'])
             if target['range_end']
             and not str(target['range_end']) == 'nan'
             else '∞')
    label = (f"{target.get('name', '目标市场')} "
             f"(命中: {r_start}-{r_end})")
    options = [{'label': label, 'value': target['id']}]
    value = current_market if current_market == target['id'] else target['id']
    return options, value


# ==================== cmp-params-store（只含事件/市场/交易设置） ====================

@callback(
    Output('cmp-params-store', 'data'),
    Input('cmp-event-selector', 'value'),
    Input('cmp-market-selector', 'value'),
    Input('cmp-initial-capital', 'value'),
    Input('cmp-position-mode', 'value'),
    Input('cmp-position-size', 'value'),
    Input('cmp-range', 'value'),
    Input('cmp-range-custom', 'value'),
    prevent_initial_call=False,
)
def save_cmp_params(event_id, market_id, initial_capital,
                    position_mode, position_size,
                    backtest_range, backtest_range_custom):
    """收集 cmp-* 顶部配置区（事件/市场/交易设置）→ cmp-params-store。
    信号参数在策略卡片各自配置，不在这里收集。"""
    if not market_id:
        return {}
    return {
        'event_id': event_id,
        'market_id': market_id,
        'price_type': 'price_last',  # 默认值，策略卡片可覆盖
        'initial_capital': safe_float(initial_capital, default=100.0,
                                      min_val=1.0),
        'position_mode': position_mode or 'fixed_amount',
        'position_size': safe_float(position_size, default=10.0,
                                    min_val=0.01),
        'backtest_range': backtest_range or 'full',
        'backtest_range_custom': backtest_range_custom,
    }


# ==================== cmp 折叠控件显隐 ====================

@callback(
    Output('cmp-range-custom-container', 'style'),
    Input('cmp-range', 'value'),
    prevent_initial_call=False,
)
def toggle_cmp_range_custom(backtest_range):
    return {'marginTop': '8px',
            'display': 'block' if backtest_range == 'custom' else 'none'}


# ==================== research-params-store（临时：sensitivity/batch 用） ====================

@callback(
    Output('research-params-store', 'data'),
    Input('global-params', 'data'),
    prevent_initial_call=False,
)
def sync_research_params_from_global(global_params):
    """临时：sensitivity/batch 仍读 research-params-store，
    从 global-params 同步。下一轮各自自包含后删除。"""
    if not global_params:
        return {}
    p = _gp_merge(global_params)
    return {k: v for k, v in p.items()
            if not k.startswith('_') and v is not None}
