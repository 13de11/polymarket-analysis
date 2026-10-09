# src/dash_app/pages/shared/params_panel.py
"""
统一参数面板生成器

从 PARAM_SCHEMA 生成参数 UI，供处理层页面（信号回测 / 策略研究）复用。

对象选择（事件/市场）比较特殊，单独手写；
其他三组（维度 / 信号 / 评价）由 schema 驱动生成。

组件 ID 格式：{prefix}-{id_suffix}
其中 id_suffix 对大多数参数就是 key 本身，少数需要重命名（见 ID_SUFFIX）。
"""

from dash import html, dcc

from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, get_params_by_group,
)


# 参数 key → 组件 ID 后缀（处理特殊命名）
# 未列出的 key 会自动把下划线换成连字符
ID_SUFFIX = {
    'backtest_range': 'range',
}

# 不在 schema 自动生成中出现的 key（由 extra_children 手写提供）
SKIP_KEYS = {'window_custom_hours'}


def _make_id(prefix: str, key: str) -> str:
    suffix = ID_SUFFIX.get(key, key.replace('_', '-'))
    return f"{prefix}-{suffix}"


def get_component_id(prefix: str, key: str) -> str:
    """供回调统一获取组件 ID"""
    return _make_id(prefix, key)


# ==================== 单个参数控件 ====================

def _make_control(prefix: str, key: str):
    """按 schema 生成单个参数控件"""
    schema = PARAM_SCHEMA[key]
    cid = _make_id(prefix, key)
    ui = schema.get('ui', 'input')
    default = schema.get('default')

    if ui == 'slider':
        marks = _make_slider_marks(schema)
        return dcc.Slider(
            id=cid,
            min=schema['min'], max=schema['max'],
            step=schema['step'], value=default,
            marks=marks,
            tooltip={'placement': 'bottom', 'always_visible': False},
        )

    if ui == 'radio':
        options = _make_radio_options(schema)
        return dcc.RadioItems(
            id=cid,
            options=options,
            value=default,
            inline=True,
            style={'fontSize': '12px'},
        )

    if ui == 'dropdown':
        options = _make_dropdown_options(schema)
        return dcc.Dropdown(
            id=cid,
            options=options,
            value=default,
            clearable=False,
            style={'width': '100%', 'fontSize': '12px'},
        )

    # input
    return dcc.Input(
        id=cid,
        type='text',
        value=str(default) if default is not None else '',
        debounce=False,
        style={'width': '100%', 'padding': '4px', 'fontSize': '12px'},
    )


def _make_slider_marks(schema):
    """Sliders 的刻度标记"""
    lo, hi = schema['min'], schema['max']
    # 默认给 3~5 个 mark
    if schema['type'] == 'int':
        step = max(1, (hi - lo) // 6)
        vals = list(range(lo, hi + 1, step))
        return {v: str(v) for v in vals[:7]}
    # float
    return {lo: f"{lo:g}", hi: f"{hi:g}"}


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


# ==================== 分组渲染 ====================

def create_schema_section(prefix: str, group: str,
                          extra_children=None):
    """
    渲染一组参数

    Args:
        prefix: 组件 ID 前缀
        group: 'dimension' | 'signal' | 'execution'
        extra_children: 附加到该组的额外 Dash 组件列表
    """
    keys = get_params_by_group(group)
    rows = []
    for key in keys:
        if key in SKIP_KEYS:
            continue
        schema = PARAM_SCHEMA[key]
        rows.append(html.Div([
            html.Label(schema['label'],
                       style={'fontSize': '12px',
                              'fontWeight': 'bold',
                              'display': 'block',
                              'marginBottom': '2px'}),
            _make_control(prefix, key),
        ], style={'marginBottom': '10px'}))

    if extra_children:
        rows.extend(extra_children)

    return html.Div(rows)


# ==================== 折叠组 ====================

def _details(summary: str, children, open_=False, color='#6c5ce7'):
    return html.Details([
        html.Summary(summary, style={
            'fontWeight': 'bold', 'fontSize': '14px',
            'cursor': 'pointer',
        }),
        html.Div(children, style={'padding': '8px 0 4px 0'}),
    ], open=open_, style={'marginBottom': '12px'})