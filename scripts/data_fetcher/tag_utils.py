#!/usr/bin/env python3
"""
标签解析工具 - 将 tag slug/label 解析为 tag ID
"""

from .http_client import get_json
from .config import GAMMA_BASE


def resolve_tag(tag_identifier: str) -> dict:
    """
    通过 slug 或 label 解析 tag ID

    Args:
        tag_identifier: tag 的 slug 或 label（如 'tweets-markets'）

    Returns:
        dict: {'id': '123', 'slug': 'xxx', 'label': 'xxx'}
              如果未找到，返回 {'id': None, 'slug': None, 'label': None}
    """
    try:
        data = get_json(f"{GAMMA_BASE}/tags")
        if not data:
            return {"id": None, "slug": None, "label": None}

        for tag in data:
            if tag.get("slug") == tag_identifier or tag.get("label") == tag_identifier:
                return {
                    "id": str(tag.get("id")),
                    "slug": tag.get("slug"),
                    "label": tag.get("label"),
                }
        return {"id": None, "slug": None, "label": None}
    except Exception as e:
        print(f"⚠️ 解析 tag 失败: {e}")
        return {"id": None, "slug": None, "label": None}


def get_tag_id(tag_identifier: str) -> str | None:
    """简化接口：只返回 tag ID"""
    result = resolve_tag(tag_identifier)
    return result.get("id")