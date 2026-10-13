# src/dash_app/pages/insights/_blocks.py
"""
数据分析中心 - 通用 UI 块
"""

from dash import html

from src.dash_app.ui.theme import (
    COLOR_BG_MUTED, COLOR_TEXT_BODY, FONT_SIZE_SM,
    PAD_SM, RADIUS_SM,
)


def info_block(how_to_read, meaning):
    """
    说明块：如何阅读 + 统计意义

    Args:
        how_to_read: str，如何阅读的说明
        meaning: str，统计意义
    """
    return html.Div([
        html.Strong("📖 如何阅读："),
        html.Span(how_to_read, style={'color': COLOR_TEXT_BODY,
                                      'fontSize': FONT_SIZE_SM}),
        html.Br(),
        html.Strong("💡 统计意义："),
        html.Span(meaning, style={'color': COLOR_TEXT_BODY,
                                  'fontSize': FONT_SIZE_SM}),
    ], style={
        'padding': PAD_SM,
        'backgroundColor': COLOR_BG_MUTED,
        'borderRadius': RADIUS_SM,
        'marginTop': '8px',
    })