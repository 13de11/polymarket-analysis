#!/usr/bin/env python3
"""
GA 价格采集推送脚本（GitHub Actions 每小时运行，也可本地手动运行）

流程：
1. 从 PA 拿活跃市场的 token 映射（GET /collect/tokens）
2. 直连 Polymarket CLOB 拉每市场最近 N 小时的 1 分钟价
3. 按小时聚合（price_last / price_avg）→ POST 回 PA（/collect/prices-data）

说明：
- 不读写本地数据库，全部通过 PA 的 HTTP 端点交互
- 带总时长熔断（默认 210 秒），超时即推送已采部分，剩余市场下轮自动补齐
- 逐市场失败只跳过不中断

用法：
    python fetch_prices_ga.py --key <秘钥>            # 默认推送到 PA 线上
    python fetch_prices_ga.py --lookback-hours 23     # 补缺口（CLOB 单窗口上限 1 天）
    python fetch_prices_ga.py --limit 5               # 调试：只采前 5 个市场
"""

import sys
import os
import time
import json
import argparse
from datetime import datetime, timezone

import requests

CLOB_BASE = "https://clob.polymarket.com"
DEFAULT_BASE_URL = "https://13de11.pythonanywhere.com"
DEADLINE_SECONDS = 210   # 总时长熔断（GA 单请求余量充足）


def agg_hourly(history: list) -> list:
    """1 分钟价 → 按小时聚合：price_last = 该小时最后一条，price_avg = 均值"""
    buckets = {}
    for point in history:
        ts, price = point.get("t"), point.get("p")
        if ts is None or price is None:
            continue
        hour_start = ts - ts % 3600
        buckets.setdefault(hour_start, []).append((ts, float(price)))
    out = []
    for hour_start in sorted(buckets):
        points = sorted(buckets[hour_start])
        price_last = points[-1][1]
        price_avg = sum(p for _, p in points) / len(points)
        out.append((hour_start, price_last, price_avg))
    return out


def main():
    parser = argparse.ArgumentParser(description="GA 价格采集推送")
    parser.add_argument('--base-url', default=DEFAULT_BASE_URL)
    parser.add_argument('--key', default=os.environ.get('COLLECT_KEY', ''))
    parser.add_argument('--lookback-hours', type=int, default=2,
                        help='回看小时数（默认 2；补缺口最大 23）')
    parser.add_argument('--limit', type=int, default=None, help='调试：只采前 N 个市场')
    parser.add_argument('--deadline', type=int, default=DEADLINE_SECONDS)
    args = parser.parse_args()

    if not args.key:
        raise SystemExit("❌ 缺少秘钥：--key 或环境变量 COLLECT_KEY")
    lookback = max(2, min(args.lookback_hours, 23))

    s = requests.Session()
    auth_headers = {"X-Collect-Key": args.key}

    # ---- 1. 拿 token 映射 ----
    print(f"🌐 获取 token 映射: {args.base_url}/collect/tokens")
    r = s.get(f"{args.base_url}/collect/tokens",
              headers=auth_headers, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"❌ 拿 token 失败: HTTP {r.status_code} {r.text[:200]}")
    tokens = r.json().get("tokens", [])
    if args.limit:
        tokens = tokens[:args.limit]
    if not tokens:
        raise SystemExit("❌ 没有活跃市场的 token（可能需要本地周更同步新事件）")
    print(f"✅ 活跃市场: {len(tokens)} 个")

    # ---- 2. 逐市场拉价 + 聚合 ----
    now = int(time.time())
    start_ts = now - lookback * 3600
    deadline = time.time() + args.deadline
    rows, fetch_errors, no_data, timed_out = [], 0, 0, False

    for i, t in enumerate(tokens, 1):
        if time.time() > deadline:
            timed_out = True
            print(f"⏱ 已到 {args.deadline}s 熔断时限，剩余市场下轮补齐")
            break
        try:
            resp = s.get(f"{CLOB_BASE}/prices-history", params={
                "market": t["token_id"], "fidelity": 1,
                "startTs": start_ts, "endTs": now,
            }, timeout=30)
            history = resp.json().get("history", []) or []
        except Exception:
            fetch_errors += 1
            continue
        if not history:
            no_data += 1
            continue
        for hour_start, price_last, price_avg in agg_hourly(history):
            rows.append([t["market_id"], hour_start, price_last, price_avg])
        if i % 20 == 0:
            print(f"  … 已处理 {i}/{len(tokens)}")

    print(f"📊 采集完成: {len(rows)} 行（{len(tokens)} 市场中 "
          f"无成交 {no_data}、失败 {fetch_errors}"
          f"{'、熔断截断' if timed_out else ''}）")

    # ---- 3. 推送回 PA ----
    if not rows:
        print("⚠️ 无数据可推送")
        return
    r = s.post(f"{args.base_url}/collect/prices-data",
               json={"rows": rows}, headers=auth_headers, timeout=120)
    print(f"推送: HTTP {r.status_code} {r.text[:200]}")
    if r.status_code != 200:
        sys.exit(1)
    print("✅ 价格推送完成")


if __name__ == '__main__':
    main()
