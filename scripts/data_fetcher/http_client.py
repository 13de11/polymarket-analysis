#!/usr/bin/env python3
"""
HTTP 请求客户端 - 包含重试、超时和 SSL 处理
"""

import json
import time
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

from .config import USER_AGENT


def build_ssl_context() -> ssl.SSLContext:
    """创建忽略证书验证的 SSL 上下文（用于自签名或内网环境）"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def get_json(
    url: str,
    params: Optional[dict] = None,
    retries: int = 5,
    retry_delay: float = 2.0,
    timeout: float = 30.0,
    max_retries: int = None,
    base_delay: float = None,
) -> Any:
    """
    发送 GET 请求并返回 JSON 解析结果

    参数:
        url: 请求 URL
        params: URL 查询参数（会被自动编码）
        retries: 最大重试次数（默认 5）
        retry_delay: 重试基础延迟（秒），实际延迟会递增
        timeout: 超时时间（秒）
        max_retries: 兼容旧调用的别名（优先级高于 retries）
        base_delay: 兼容旧调用的别名（优先级高于 retry_delay）

    返回:
        JSON 解析后的 Python 对象（dict 或 list）
    """
    # 兼容旧参数名
    if max_retries is not None:
        retries = max_retries
    if base_delay is not None:
        retry_delay = base_delay

    if params:
        query = urllib.parse.urlencode(params)
        url = f"{url}?{query}"

    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    last_error = ""

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            ctx = build_ssl_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read().decode("utf-8")
            if not raw.strip():
                return None
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            # 读取错误详情
            detail = e.read().decode("utf-8", errors="replace")[:2000]
            last_error = f"HTTP {e.code}: {detail}"
            # 只在可重试的状态码下重试
            if e.code not in {408, 429, 500, 502, 503, 504}:
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = repr(e)
        if attempt < retries:
            time.sleep(retry_delay * attempt)

    raise RuntimeError(f"GET {url} failed: {last_error}")