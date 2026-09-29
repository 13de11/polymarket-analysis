"""用户输入的安全转换工具 - 非数字输入不抛异常"""


def safe_int(value, default=0, min_val=None, max_val=None):
    try:
        v = int(float(value))
    except (TypeError, ValueError):
        return default
    if min_val is not None and v < min_val:
        return default
    if max_val is not None and v > max_val:
        return default
    return v


def safe_float(value, default=0.0, min_val=None, max_val=None):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if min_val is not None and v < min_val:
        return default
    if max_val is not None and v > max_val:
        return default
    return v