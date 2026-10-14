"""
策略研究模块入口
"""

from src.dash_app.pages.research.layout import layout
from src.dash_app.pages.research import filter_panel   # noqa
from src.dash_app.pages.research.tabs import comparison  # noqa
from src.dash_app.pages.research.tabs import sensitivity  # noqa

__all__ = ['layout']
