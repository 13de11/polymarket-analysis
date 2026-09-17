"""
策略研究模块入口
"""

from src.dash_app.pages.research.layout import layout
from src.dash_app.pages.research import filter_panel   # noqa
from src.dash_app.pages.research.tabs import comparison  # noqa
from src.dash_app.pages.research.tabs import sensitivity  # noqa

__all__ = ['layout']


def register_callbacks(app):
    """注册研究页的参数面板回调（需要 app 实例）"""
    from src.dash_app.pages.research.filter_panel import register_research_callbacks
    register_research_callbacks(app)