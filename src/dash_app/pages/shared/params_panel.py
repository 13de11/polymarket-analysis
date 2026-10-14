# src/dash_app/pages/shared/params_panel.py
"""
统一参数面板生成器

从 PARAM_SCHEMA 生成参数 UI，供处理层页面（信号回测 / 策略研究）复用。

命名规则：
    组件 ID = f"{prefix}-{PARAM_SCHEMA[key]['id']}"
"""

from dash import html, dcc
import pandas as pd

from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, get_params_by_group,
)
from src.dash_app.utils.data_loader import (
    get_elon_tweet_events,
    get_target_markets_batch,
)


def _make_id(prefix: str, key: str) -> str:
    return f"{prefix}-{PARAM_SCHEMA[key]['id']}"


def get_component_id(prefix: str, key: str) -> str:
    return _make_id(prefix, key)


def _make_control(prefix: str, key: str, override=None):
    """按 schema 生成单个参数控件。override 不为 None 时覆盖默认值。"""
    schema = PARAM_SCHEMA[key]
    cid = _make_id(prefix, key)
    ui = schema.get('ui', 'input')
    default = override if override is not None else schema.get('default')

    if ui == 'slider':
        return dcc.Slider(
            id=cid,
            min=schema['min'], max=schema['max'],
            step=schema['step'], value=default,
            marks=_make_slider_marks(schema),
            tooltip={'placement': 'bottom', 'always_visible': False},
        )

    if ui == 'radio':
        return dcc.RadioItems(
            id=cid,
            options=_make_radio_options(schema),
            value=default,
            inline=True,
            style={'fontSize': '12px'},
        )

    if ui == 'dropdown':
        return dcc.Dropdown(
            id=cid,
            options=_make_dropdown_options(schema),
            value=default,
            clearable=False,
            style={'width': '100%', 'fontSize': '12px'},
        )

    return dcc.Input(
        id=cid,
        type='text',
        value=str(default) if default is not None else '',
        debounce=False,
        style={'width': '100%', 'padding': '4px', 'fontSize': '12px'},
    )


def _make_slider_marks(schema):
    lo, hi = schema['min'], schema['max']
    if schema['type'] == 'int':
        step = max(1, (hi - lo) // 5)
        vals = list(range(lo, hi + 1, step))
        return {v: str(v) for v in vals[:6]}
    if lo == hi:
        return {lo: f"{lo:g}"}
    span = hi - lo
    vals = [lo + span * i / 3 for i in range(4)]
    return {round(v, 6): f"{v:g}" for v in vals}


def _make_radio_options(schema):
    if schema['type'] == 'bool':
        return [{'label': ' 开', 'value': True},
                {'label': ' 关', 'value': False}]
    labels = schema.get('option_labels', {})
    return [{'label': f" {labels.get(o, o)}", 'value': o}
            for o in schema['options']]


def _make_dropdown_options(schema):
    labels = schema.get('option_labels', {})
    return [{'label': labels.get(o, o), 'value': o}
            for o in schema['options']]


def create_schema_section(prefix: str, group: str,
                          extra_children=None, overrides=None):
    """
    渲染一组参数

    Args:
        prefix: 组件 ID 前缀
        group: 'dimension' | 'signal' | 'execution'
        extra_children: 附加到该组的额外 Dash 组件列表
        overrides: {schema_key: value}，覆盖组件的默认值
    """
    overrides = overrides or {}
    keys = get_params_by_group(group)
    rows = []
    for key in keys:
        schema = PARAM_SCHEMA[key]
        rows.append(html.Div([
            html.Label(schema['label'],
                       style={'fontSize': '12px',
                              'fontWeight': 'bold',
                              'display': 'block',
                              'marginBottom': '2px'}),
            _make_control(prefix, key, overrides.get(key)),
        ], style={'marginBottom': '10px'}))

    if extra_children:
        rows.extend(extra_children)

    return html.Div(rows)


# ==================== 共享参数面板（param-* 前缀） ====================

def create_shared_panel(global_params=None, series='7d', prefix='param'):
    """
    创建共享参数面板（默认 param-* 前缀）

    /backtest 用 prefix='param'；/research 的 comparison tab 用 prefix='cmp'
    实现自包含配置区——每个页面/tab 用自己的前缀，组件 ID 不冲突。
    事件/市场下拉从 data_loader 填充；schema 参数从 PARAM_SCHEMA 生成。
    页面自行添加按钮和页面特有组件（如 research 的策略卡片）。

    Args:
        global_params: dict|None，从 global-params store 读取，用于预填组件值
        series: '7d'|'48h'，决定事件列表范围

    组件 ID 清单（Phase 2/3 切换时各页面回调统一引用这些 ID）:
        param-event-selector       事件下拉
        param-market-selector      市场下拉
        param-price-type           价格类型
        param-window-type          窗口类型
        param-window-custom        自定义窗口小时数
        param-window-custom-container  自定义窗口容器（显隐）
        param-capacity             容差
        param-price-threshold      价格变动阈值
        param-distance-threshold   距离变动阈值
        param-inertia              惯性重置
        param-momentum-enable      动量修正开关
        param-momentum-coef        动量系数
        param-signal-mode          信号显示模式
        param-initial-capital      初始资金
        param-position-mode        开仓模式
        param-position-size        每次投入
        param-range                回测区间
        param-range-custom         自定义区间滑块
        param-range-custom-container   自定义区间容器（显隐）
    """
    events_df = get_elon_tweet_events(series)
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

    default_event = None
    if global_params and global_params.get('event_id') in event_ids:
        default_event = global_params['event_id']
    elif not events_df.empty:
        default_event = events_df.iloc[-1]['id']

    overrides = {}
    if global_params:
        for k, v in global_params.items():
            if v is not None:
                overrides[k] = v

    custom_hours = str(global_params.get('window_custom_hours') or '') if global_params else ''
    range_custom = list(global_params.get('backtest_range_custom') or [0, 100]) if global_params else [0, 100]

    return html.Div([

        html.Div([
            html.H4("📊 参数配置", style={'margin': 0, 'color': '#2c3e50'}),
            html.P("按顺序配置四步参数",
                   style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '4px 0 0 0'}),
        ], style={'borderBottom': '2px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '15px'}),

        # ---- 数据选择 ----
        html.Details([
            html.Summary("📊 数据选择",
                         style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            html.Div([
                html.Div([
                    html.Label("事件:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id=f'{prefix}-event-selector',
                        options=event_options,
                        value=default_event,
                        placeholder='请选择事件',
                        style={'width': '100%', 'marginTop': '3px'},
                    ),
                    html.Div("要回测的历史事件",
                             style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                ], style={'marginBottom': '10px'}),
                html.Div([
                    html.Label("目标市场:", style={'fontWeight': 'bold', 'fontSize': '13px'}),
                    dcc.Dropdown(
                        id=f'{prefix}-market-selector',
                        options=[],
                        placeholder='请先选择事件',
                        style={'width': '100%', 'marginTop': '3px'},
                    ),
                    html.Div("具体推文区间市场，决定中位数锚点",
                             style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                ], style={'marginBottom': '0'}),
            ], style={'padding': '8px 0 4px 0'}),
        ], open=True, style={'marginBottom': '12px'}),

        # ---- 观察维度 ----
        html.Details([
            html.Summary("🎚️ 观察维度",
                         style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            create_schema_section(
                prefix, 'dimension',
                overrides=overrides,
                extra_children=[
                    html.Div([
                        dcc.Input(
                            id=f'{prefix}-window-custom',
                            type='text',
                            value=custom_hours,
                            placeholder='自定义小时数',
                            style={'width': '60%', 'display': 'inline-block', 'marginTop': '4px'},
                        ),
                        html.Span(" 小时",
                                  style={'fontSize': '12px', 'color': '#7f8c8d', 'marginLeft': '4px'}),
                    ], id=f'{prefix}-window-custom-container',
                       style={'marginTop': '4px', 'display': 'none'}),
                ],
            ),
        ], style={'marginBottom': '12px'}),

        # ---- 信号参数 ----
        html.Details([
            html.Summary("🧠 信号参数",
                         style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            create_schema_section(prefix, 'signal', overrides=overrides),
        ], style={'marginBottom': '12px'}),

        # ---- 评价假设 ----
        html.Details([
            html.Summary("💰 评价假设",
                         style={'fontWeight': 'bold', 'fontSize': '14px', 'cursor': 'pointer'}),
            create_schema_section(
                prefix, 'execution',
                overrides=overrides,
                extra_children=[
                    html.Div([
                        dcc.RangeSlider(
                            id=f'{prefix}-range-custom',
                            min=0, max=100, step=5,
                            value=range_custom,
                            marks={0: '0%', 25: '25%', 50: '50%',
                                   75: '75%', 100: '100%'},
                            tooltip={'placement': 'bottom', 'always_visible': False},
                        ),
                        html.Div("按事件时长百分比选择回测时段",
                                 style={'fontSize': '11px', 'color': '#7f8c8d', 'marginTop': '2px'}),
                    ], id=f'{prefix}-range-custom-container',
                       style={'display': 'none', 'marginTop': '8px'}),
                ],
            ),
        ], style={'marginBottom': '20px'}),

        # 操作按钮由各页面自行添加
    ], style={
        'backgroundColor': 'white', 'padding': '15px', 'borderRadius': '8px',
        'border': '1px solid #e9ecef', 'height': 'fit-content',
    })


def render_event_market_row(global_params=None, series='7d'):
    """
    紧凑的事件+市场选择行（横向，供 research tab 顶部使用）

    与 create_shared_panel 共用 param-event-selector / param-market-selector ID。
    只包含事件+市场，不含信号参数（research tab 自带策略卡片/扫参等专属控件）。
    """
    events_df = get_elon_tweet_events(series)
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

    default_event = None
    if global_params and global_params.get('event_id') in event_ids:
        default_event = global_params['event_id']
    elif not events_df.empty:
        default_event = events_df.iloc[-1]['id']

    return html.Div([
        html.Div([
            html.Label("事件:", style={'fontWeight': 'bold', 'fontSize': '13px',
                                        'marginRight': '8px'}),
            dcc.Dropdown(
                id='param-event-selector',
                options=event_options,
                value=default_event,
                placeholder='选择事件',
                style={'width': '300px', 'display': 'inline-block',
                       'fontSize': '12px'},
            ),
            html.Label("市场:", style={'fontWeight': 'bold', 'fontSize': '13px',
                                        'marginLeft': '15px', 'marginRight': '8px'}),
            dcc.Dropdown(
                id='param-market-selector',
                options=[],
                placeholder='选择市场',
                style={'width': '200px', 'display': 'inline-block',
                       'fontSize': '12px'},
            ),
        ], style={'display': 'flex', 'alignItems': 'center', 'gap': '4px'}),
    ], style={'padding': '10px 15px', 'backgroundColor': '#f8f9fa',
              'borderRadius': '6px', 'marginBottom': '10px'})