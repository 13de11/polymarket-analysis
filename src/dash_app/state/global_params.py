# src/dash_app/state/global_params.py
"""
处理层共享参数 - 唯一数据结构 + 读写 helper

设计原则：
- 单一真相源：所有处理层页面（信号评价 / 策略研究）读写同一份参数
- UI 视图与引擎视图分离：UI 用 window_type 表达，引擎用 window_mode/param/start
- 保持扁平：不用嵌套 dict，因为 dcc.Store 序列化简单
"""

from typing import Any, Dict, Optional


# ==================== store id 常量 ====================

GLOBAL_PARAMS_STORE_ID = 'global-params'


# ==================== 默认值 ====================

DEFAULTS: Dict[str, Any] = {
    # ---- 对象选择 ----
    'event_id': None,              # 单事件（信号评价用）
    'market_id': None,             # 单市场
    'selected_events': [],         # 多事件（跨事件验证用）

    # ---- 观察维度（UI 用 window_type；引擎用 window_mode/param/start）----
    'price_type': 'price_last',
    'window_type': '7d',           # '7d' | 'gamestart' | 'open' | 'custom'
    'window_mode': 'rolling',      # 引擎字段：'rolling' | 'expanding'
    'window_param': 168,           # 引擎字段：rolling 的 N
    'window_start': None,          # 引擎字段：expanding 的起点类型
    'window_custom_hours': None,   # UI 字段：自定义小时数

    # ---- 信号参数 ----
    'capacity': 0.5,
    'price_threshold': 0.005,
    'distance_threshold': 1.5,
    'inertia': 6,
    'momentum_enable': True,
    'momentum_coef': 0.10,
    'signal_mode': 'start',        # 仅影响图表显示

    # ---- 评价假设（用于信号评价，不是策略参数）----
    'initial_capital': 100.0,
    'position_mode': 'fixed_amount',
    'position_size': 10.0,
    'backtest_range': 'full',
    'backtest_range_custom': [0, 100],
}


# ==================== 基础 helper ====================

def make_defaults() -> Dict[str, Any]:
    """返回一份全新的默认参数（深拷贝 list 字段）"""
    out = dict(DEFAULTS)
    out['selected_events'] = []
    out['backtest_range_custom'] = [0, 100]
    return out


def merge(update: Optional[Dict[str, Any]],
          base: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """把 update 合并到 base（默认合并到默认值上），返回新 dict。
    update 中值为 None 的键会被忽略（视为"未填"）。
    """
    result = make_defaults() if base is None else dict(base)
    if update:
        for k, v in update.items():
            if v is not None:
                result[k] = v
    return result


def has_market(params: Optional[Dict[str, Any]]) -> bool:
    """是否选了市场（信号评价必要前提）"""
    return bool(params and params.get('market_id'))


def has_events(params: Optional[Dict[str, Any]]) -> bool:
    """是否选了多事件（跨事件验证前提）"""
    return bool(params and params.get('selected_events'))


# ==================== window 字段转换 ====================

def window_type_to_engine(window_type: str,
                          custom_hours: Optional[int] = None
                          ) -> Dict[str, Any]:
    """
    UI 的 window_type → 引擎三字段

    Returns:
        {'window_mode': ..., 'window_param': ..., 'window_start': ...}
    """
    if window_type == '7d':
        return {'window_mode': 'rolling', 'window_param': 168,
                'window_start': None}
    if window_type == 'gamestart':
        return {'window_mode': 'expanding', 'window_param': None,
                'window_start': 'gamestart'}
    if window_type == 'open':
        return {'window_mode': 'expanding', 'window_param': None,
                'window_start': 'open'}
    # custom
    try:
        n = int(float(custom_hours))
        if n < 1:
            n = 168
    except (TypeError, ValueError):
        n = 168
    return {'window_mode': 'rolling', 'window_param': n,
            'window_start': None}


def engine_to_window_type(window_mode: str,
                          window_start: Optional[str]) -> str:
    """引擎三字段 → UI 的 window_type（反向）"""
    if window_mode == 'expanding':
        if window_start == 'gamestart':
            return 'gamestart'
        if window_start == 'open':
            return 'open'
        return 'gamestart'  # 兜底
    return '7d'  # rolling 默认视为 7d；自定义无法从 engine 反推


def normalize(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    规范化：确保 window_type 和 window_mode/param/start 一致。
    从 UI 修改后调用，或从外部注入 params 前调用。
    """
    p = merge(params)
    engine_fields = window_type_to_engine(
        p.get('window_type') or '7d',
        p.get('window_custom_hours'),
    )
    p.update(engine_fields)
    return p


# ==================== store 更新 helper ====================

def update_field(params: Optional[Dict[str, Any]],
                 key: str, value: Any) -> Dict[str, Any]:
    """在 store 上更新单个字段并返回新 dict（供回调使用）"""
    p = merge(params)
    p[key] = value
    # window_type 变化时自动联动 engine 字段
    if key in ('window_type', 'window_custom_hours'):
        p = normalize(p)
    return p


def update_fields(params: Optional[Dict[str, Any]],
                  updates: Dict[str, Any]) -> Dict[str, Any]:
    """批量更新多个字段"""
    p = merge(params)
    p.update(updates)
    if 'window_type' in updates or 'window_custom_hours' in updates:
        p = normalize(p)
    return p