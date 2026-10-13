# src/dash_app/ui/theme.py
"""
全站主题色 / 字号 / 间距常量

用法：
    from src.dash_app.ui.theme import COLOR_TEXT, FONT_SIZE_SM
    html.Div("...", style={'color': COLOR_TEXT, 'fontSize': FONT_SIZE_SM})

设计原则：
- 只定义「会用很多次」的值，不追求面面俱到
- 颜色命名按用途，不按色值（COLOR_SUCCESS 比 GREEN 好）
- 新写的代码优先用这些常量；旧代码改到哪里顺手替换到哪里
"""

# ==================== 颜色：主色 ====================

COLOR_PRIMARY = '#6c5ce7'          # 主品牌紫（研究模块）
COLOR_PRIMARY_BLUE = '#3498db'     # 主品牌蓝（回测模块）
COLOR_PRIMARY_GREEN = '#00b894'    # 成功 / 敏感性分析
COLOR_PRIMARY_ORANGE = '#f39c12'   # 警告 / 提示

# ==================== 颜色：语义 ====================

COLOR_SUCCESS = '#28a745'          # 成功 / 盈利 / 正数
COLOR_DANGER = '#e74c3c'           # 错误 / 亏损 / 负数
COLOR_WARNING = '#f39c12'          # 警告 / 中等
COLOR_INFO = '#3498db'             # 信息 / 中性高亮

# ==================== 颜色：文本 ====================

COLOR_TEXT = '#2c3e50'             # 主要文本（标题）
COLOR_TEXT_BODY = '#495057'        # 正文
COLOR_TEXT_MUTED = '#6c757d'       # 次要文本（说明、标签）
COLOR_TEXT_LIGHT = '#adb5bd'       # 极淡文本（禁用、占位）

# ==================== 颜色：背景 / 边框 ====================

COLOR_WHITE = '#ffffff'
COLOR_BG_PAGE = '#ffffff'          # 页面主背景
COLOR_BG_LIGHT = '#f8f9fa'         # 浅灰背景（卡片、面板）
COLOR_BG_MUTED = '#f1f3f5'         # 略深灰背景（说明块）
COLOR_BG_WARN = '#fff3cd'          # 警告背景
COLOR_BG_ERROR = '#fdecea'         # 错误背景
COLOR_BG_SUCCESS = '#e8f8f5'       # 成功背景
COLOR_BORDER = '#e9ecef'           # 边框
COLOR_BORDER_STRONG = '#dee2e6'    # 强调边框

# ==================== 字号 ====================

FONT_SIZE_XS = '11px'
FONT_SIZE_SM = '12px'
FONT_SIZE_MD = '13px'
FONT_SIZE_BASE = '14px'
FONT_SIZE_LG = '16px'
FONT_SIZE_XL = '20px'
FONT_SIZE_XXL = '24px'

# ==================== 间距 ====================

PAD_XS = '4px 8px'
PAD_SM = '8px 12px'
PAD_MD = '10px 15px'
PAD_LG = '15px'

GAP_SM = '10px'
GAP_MD = '15px'
GAP_LG = '20px'

# ==================== 圆角 / 阴影 ====================

RADIUS_SM = '4px'
RADIUS = '6px'
RADIUS_LG = '8px'

SHADOW = '0 1px 3px rgba(0,0,0,0.1)'