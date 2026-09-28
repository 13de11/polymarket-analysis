# src/dash_app/utils/ui/table.py
"""
Dash 表格工具 - 统一表头/单元格样式

用法：
    from src.dash_app.utils.ui.table import td, table
    rows = [html.Tr([td('a'), td('b', color='red', fontWeight='bold')])]
    return table(['列1', '列2'], rows)

规则：
- 表头 th / 单元格 td 都默认 textAlign='center'
- td 支持任意 kwargs 直接传给 style（color / fontWeight / fontSize ...）
- 所有列对齐一致，不再出现"标题居中、内容靠左"的问题
"""

from dash import html


def th(label, **style_kwargs):
    """表头单元格：默认居中"""
    style = {'textAlign': 'center'}
    style.update(style_kwargs)
    return html.Th(label, style=style)


def td(content, **style_kwargs):
    """数据单元格：默认居中；style_kwargs 直接进 style"""
    style = {'textAlign': 'center'}
    style.update(style_kwargs)
    return html.Td(content, style=style)


def table(headers, rows, font_size='13px'):
    """构建表格

    Args:
        headers: list[str] 表头文本
        rows: list[html.Tr] 由 html.Tr + td 组成的数据行
        font_size: 字号
    """
    return html.Table([
        html.Thead(html.Tr([th(h) for h in headers])),
        html.Tbody(rows),
    ], style={
        'width': '100%',
        'borderCollapse': 'collapse',
        'fontSize': font_size,
    })