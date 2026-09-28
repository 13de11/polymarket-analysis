# src/dash_app/utils/research/params_schema.py
"""
研究参数 & 指标元数据（单一数据源）

所有 UI 组件、敏感性分析、参数校验，都应从这里读取。
新增一个可调参数，只需要在 PARAM_SCHEMA 里加一条。
"""

# ============ 参数元数据 ============
# type: 'float' | 'int' | 'bool' | 'enum'
# tunable: 是否可以在敏感性分析里被扫描
# group: UI 分组
PARAM_SCHEMA = {
    'capacity': {
        'label': '容差',
        'type': 'float',
        'min': 0.0, 'max': 5.0, 'step': 0.5, 'default': 0.5,
        'group': 'strategy',
        'tunable': True,
    },
    'price_threshold': {
        'label': '价格变动阈值',
        'type': 'float',
        'min': 0.001, 'max': 0.02, 'step': 0.001, 'default': 0.005,
        'group': 'strategy',
        'tunable': True,
    },
    'distance_threshold': {
        'label': '距离变动阈值',
        'type': 'float',
        'min': 0.5, 'max': 4.0, 'step': 0.1, 'default': 1.5,
        'group': 'strategy',
        'tunable': True,
    },
    'inertia': {
        'label': '惯性重置',
        'type': 'int',
        'min': 1, 'max': 12, 'step': 1, 'default': 6,
        'group': 'strategy',
        'tunable': True,
    },
    'momentum_enable': {
        'label': '动量修正',
        'type': 'bool',
        'default': True,
        'group': 'strategy',
        'tunable': False,
    },
    'momentum_coef': {
        'label': '动量系数',
        'type': 'float',
        'min': 0.01, 'max': 0.30, 'step': 0.01, 'default': 0.10,
        'group': 'strategy',
        'tunable': True,
    },
    'window_type': {
        'label': '推文速率窗口',
        'type': 'enum',
        'options': ['7d', 'gamestart', 'open'],
        'default': '7d',
        'group': 'data',
        'tunable': False,
    },
    'price_type': {
        'label': '价格类型',
        'type': 'enum',
        'options': ['price_last', 'price_avg'],
        'default': 'price_last',
        'group': 'data',
        'tunable': False,
    },
    'position_mode': {
        'label': '开仓模式',
        'type': 'enum',
        'options': ['fixed_amount', 'fixed_shares'],
        'default': 'fixed_amount',
        'group': 'execution',
        'tunable': False,
    },
    'position_size': {
        'label': '每次投入',
        'type': 'float',
        'min': 1.0, 'max': 1000.0, 'step': 1.0, 'default': 10.0,
        'group': 'execution',
        'tunable': False,
    },
    'initial_capital': {
        'label': '初始资金',
        'type': 'float',
        'min': 10.0, 'max': 100000.0, 'step': 10.0, 'default': 100.0,
        'group': 'execution',
        'tunable': False,
    },
}

# ============ 指标元数据 ============
# direction: 'max' 表示越大越好，'min' 表示越小越好，None 表示中性
METRIC_SCHEMA = {
    'total_return': {
        'label': '总收益率', 'unit': '%', 'direction': 'max', 'fmt': '.2f',
    },
    'sharpe_ratio': {
        'label': '夏普比率', 'unit': '', 'direction': 'max', 'fmt': '.2f',
    },
    'win_rate': {
        'label': '胜率', 'unit': '%', 'direction': 'max', 'fmt': '.1f',
    },
    'max_drawdown_pct': {
        'label': '最大回撤', 'unit': '%', 'direction': 'min', 'fmt': '.2f',
    },
    'profit_factor': {
        'label': '盈亏比', 'unit': '', 'direction': 'max', 'fmt': '.2f',
    },
    'total_trades': {
        'label': '交易次数', 'unit': '', 'direction': None, 'fmt': '.0f',
    },
}

# ============ 辅助函数 ============
def get_tunable_params():
    """返回所有可调参数 key 列表（用于敏感性分析下拉）"""
    return [k for k, v in PARAM_SCHEMA.items() if v.get('tunable')]

def get_param_range(param_key, n_points=10):
    """
    返回某参数的推荐扫描范围（n 个点）
    - bool: [False, True]
    - int:  返回 int 列表
    - float: 返回 float 列表
    """
    schema = PARAM_SCHEMA[param_key]
    if schema['type'] == 'bool':
        return [False, True]

    lo, hi = schema['min'], schema['max']
    if n_points <= 1:
        return [lo]

    if schema['type'] == 'int':
        return [int(round(lo + i * (hi - lo) / (n_points - 1)))
                for i in range(n_points)]

    return [round(lo + i * (hi - lo) / (n_points - 1), 6)
            for i in range(n_points)]

def get_metric_options():
    """返回指标下拉的 options"""
    return [{'label': v['label'], 'value': k} for k, v in METRIC_SCHEMA.items()]

def is_lower_better(metric_key):
    """判断指标方向，用于 _find_best"""
    return METRIC_SCHEMA.get(metric_key, {}).get('direction') == 'min'

def fmt_metric(metric_key, value):
    """统一指标格式化（前端表格用）"""
    schema = METRIC_SCHEMA.get(metric_key, {})
    fmt = schema.get('fmt', '.2f')
    unit = schema.get('unit', '')
    try:
        return f"{value:{fmt}}{unit}"
    except (TypeError, ValueError):
        return "—"