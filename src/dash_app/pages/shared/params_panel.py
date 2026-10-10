# src/dash_app/pages/shared/params_panel.py
"""
统一参数面板生成器

从 PARAM_SCHEMA 生成参数 UI，供处理层页面（信号回测 / 策略研究）复用。

命名规则：
    组件 ID = f"{prefix}-{PARAM_SCHEMA[key]['id']}"
"""

from dash import html, dcc

from src.dash_app.utils.research.params_schema import (
    PARAM_SCHEMA, get_params_by_group,
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