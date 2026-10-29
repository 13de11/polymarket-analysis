"""
线上数据采集器（与 Dash 应用同进程，部署在 PythonAnywhere）

背景：PA 免费版没有小时级定时任务、外网白名单不放行 muskmeter.live，
因此采用「外部 cron 触发 + Web 端点就地采集」的架构：
- 价格：PA 可直连 Polymarket API（已实测），由外部免费 cron（如 cron-job.org）
  每小时 GET /collect/prices?key=<COLLECT_KEY> 触发
- 推文：muskmeter 只能从能访问它的机器抓（用户本地），本地爬虫解析后
  POST /collect/tweets?key=<COLLECT_KEY> 推送到这里

部署要求（PA Web → WSGI 配置文件里设置）：
    os.environ['COLLECT_KEY'] = '你的秘钥'
未设置 COLLECT_KEY 时端点返回 404（功能关闭）。

价格采集逻辑：
- 活跃事件 = events.end_date >= now（PA 精简库内已有的事件；新事件需本地周更同步）
- token 从 market_tokens 表取（build_final_db 随库携带，不依赖 Gamma API）
- 每次拉每市场最近 2 小时 1 分钟价（上小时重算保证完整），
  按小时聚合 price_last / price_avg，INSERT OR REPLACE 到 price_hourly
"""

import os
import json
import hmac
import time
import sqlite3
from datetime import datetime, timezone

from flask import jsonify, request

# data_loader 导入时会把项目根目录加入 sys.path
from src.dash_app.utils.data_loader import DB_PATH

CLOB_BASE = "https://clob.polymarket.com"
LOOKBACK_SECONDS = 2 * 3600   # 每次回看 2 小时（上一个小时重算，保证整点后数据完整）
RETRY = 3

# PA 免费版 Web 应用进程出网必须走 PA 内部代理（Bash console 自动配置了，
# Web 应用进程没有——不配置时连不上 Polymarket，表现为端点长时间无响应）。
# 在 WSGI 文件里设置：os.environ['COLLECT_PROXY'] = 'http://proxy.server:3128'
# 本地环境不设置即可（不影响直连）。
_collect_proxy = os.environ.get("COLLECT_PROXY", "")
if _collect_proxy:
    os.environ.setdefault("HTTP_PROXY", _collect_proxy)
    os.environ.setdefault("HTTPS_PROXY", _collect_proxy)


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _authorized() -> bool:
    key = os.environ.get("COLLECT_KEY", "")
    if not key:
        return False  # 未配置秘钥 = 功能关闭
    given = request.args.get("key", "") or request.headers.get("X-Collect-Key", "")
    return hmac.compare_digest(key, given)


def _http_get_json(url: str, params: dict):
    """GET JSON，复用项目的 http_client（带重试 + SSL 处理，本地代理环境已验证）"""
    try:
        from scripts.data_fetcher.http_client import get_json
        return get_json(url, params, retries=2, retry_delay=1.0, timeout=30)
    except Exception:
        return None


def _active_event_ids(conn) -> list:
    """end_date >= now 的事件（PA 库内已有的事件；新事件靠本地周更同步进来）"""
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    rows = conn.execute("SELECT id, slug, end_date FROM events").fetchall()
    ids = []
    for event_id, slug, end_date in rows:
        try:
            end_dt = datetime.fromisoformat(str(end_date).replace("Z", "+00:00"))
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            if end_dt >= datetime.now(timezone.utc):
                ids.append(event_id)
        except ValueError:
            continue
    return ids


def collect_prices(limit_markets: int = None, backfill_hours: int = 2) -> dict:
    """增量拉活跃事件价格 → 小时聚合 → upsert price_hourly

    limit_markets: 只处理前 N 个市场（调试用，线上全量时不传）
    backfill_hours: 回看小时数（默认 2；补缺口时最多 23——CLOB 1min API 单次窗口上限 1 天）
    """
    backfill_hours = max(2, min(int(backfill_hours), 23))
    conn = _connect()
    try:
        event_ids = _active_event_ids(conn)
        if not event_ids:
            return {"ok": True, "message": "无活跃事件", "hours_written": 0}

        placeholders = ",".join(["?"] * len(event_ids))
        # 排序：按最近已知价格降序（"在打"的热门市场优先）。
        # 全量采集时若中途被超时掐断，最重要的市场已先采完；
        # limit_markets 调试时选中的也是最有代表性的市场。
        query = """
            SELECT m.id, m.slug, t.token_id
            FROM markets m
            JOIN market_tokens t ON t.market_id = m.id
            WHERE m.event_id IN (%s)
            ORDER BY (
                SELECT price_last FROM price_hourly p
                WHERE p.market_id = m.id
                ORDER BY hour_start_utc DESC LIMIT 1
            ) IS NULL, (
                SELECT price_last FROM price_hourly p
                WHERE p.market_id = m.id
                ORDER BY hour_start_utc DESC LIMIT 1
            ) DESC
        """ % placeholders
        if limit_markets:
            query += f" LIMIT {int(limit_markets)}"
        markets = conn.execute(query, event_ids).fetchall()
        if not markets:
            return {"ok": False, "message": "活跃事件无 market_tokens 映射（需本地周更同步新事件）"}

        now = int(time.time())
        start_ts = now - backfill_hours * 3600
        hours_written = errors = 0
        no_token = 0

        for market_id, slug, token_id in markets:
            if not token_id:
                no_token += 1
                continue
            data = _http_get_json(f"{CLOB_BASE}/prices-history", {
                "market": token_id, "fidelity": 1,
                "startTs": start_ts, "endTs": now,
            })
            history = (data or {}).get("history", []) or []
            if not history:
                errors += 1
                continue

            # 按小时分桶：price_last = 该小时最后一条，price_avg = 均值
            buckets = {}
            for point in history:
                ts, price = point.get("t"), point.get("p")
                if ts is None or price is None:
                    continue
                hour_start = ts - ts % 3600
                buckets.setdefault(hour_start, []).append((ts, float(price)))

            for hour_start, points in buckets.items():
                points.sort()
                price_last = points[-1][1]
                price_avg = sum(p for _, p in points) / len(points)
                conn.execute(
                    "INSERT OR REPLACE INTO price_hourly "
                    "(market_id, hour_start_utc, price_last, price_avg) VALUES (?, ?, ?, ?)",
                    (market_id, hour_start, price_last, price_avg))
                hours_written += 1
            # 逐市场提交：请求若被 PA 超时掐断，已采的数据也已落库，
            # 下一轮（lookback 重叠）会自动补齐剩余市场
            conn.commit()

        conn.commit()
        return {
            "ok": True,
            "active_events": len(event_ids),
            "markets": len(markets),
            "hours_written": hours_written,
            "no_token": no_token,
            "fetch_errors": errors,
        }
    finally:
        conn.close()


def upsert_tweets(hours: list) -> int:
    """接收 [(timestamp_unix_utc, tweet_count), ...] 并 upsert 到 tweet_hourly"""
    conn = _connect()
    try:
        written = 0
        for item in hours:
            ts, count = int(item[0]), int(item[1])
            if ts <= 0 or count < 0:
                continue
            conn.execute(
                "INSERT OR REPLACE INTO tweet_hourly (timestamp_unix_utc, tweet_count) "
                "VALUES (?, ?)", (ts, count))
            written += 1
        conn.commit()
        return written
    finally:
        conn.close()


def register_collect_routes(server):
    """把采集端点挂到 Dash 底层的 Flask server 上"""

    @server.route("/collect/debug")
    def _collect_debug():
        if not _authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 404
        return jsonify({
            "COLLECT_KEY_set": bool(os.environ.get("COLLECT_KEY")),
            "COLLECT_PROXY": os.environ.get("COLLECT_PROXY", "(未设置)"),
            "HTTP_PROXY": os.environ.get("HTTP_PROXY", "(未设置)"),
            "HTTPS_PROXY": os.environ.get("HTTPS_PROXY", "(未设置)"),
            "database": str(DB_PATH),
        })

    @server.route("/collect/prices")
    def _collect_prices():
        if not _authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 404
        try:
            limit = request.args.get("limit")
            backfill = request.args.get("backfill_hours")
            result = collect_prices(
                limit_markets=int(limit) if limit else None,
                backfill_hours=int(backfill) if backfill else 2)
            status = 200 if result.get("ok") else 500
            return jsonify(result), status
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 500

    @server.route("/collect/tweets", methods=["POST"])
    def _collect_tweets():
        if not _authorized():
            return jsonify({"ok": False, "error": "unauthorized"}), 404
        try:
            payload = request.get_json(force=True, silent=True) or {}
            hours = payload.get("hours", [])
            if not isinstance(hours, list) or not hours:
                return jsonify({"ok": False, "error": "hours 字段缺失或为空"}), 400
            written = upsert_tweets(hours)
            return jsonify({"ok": True, "written": written})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 500
