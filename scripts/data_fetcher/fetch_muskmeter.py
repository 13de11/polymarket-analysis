#!/usr/bin/env python3
"""
muskmeter.live 爬虫（原型阶段：抓取 + 解析 + 打印/校验，不写数据库）

数据源：https://www.muskmeter.live/?start=<unix>&end=<unix>&eventId=<id>&eventType=weekly
页面为 Svelte SSR，小时 × 日期矩阵直接在 HTML 里：
- 表头：day-name/day-number（只有"周几 + 日号"，月份由 end 参数倒推）
- 每行：hour-label（HH:MM）+ N 个日期单元格 + 行尾 AVG（浮点，丢弃）
- 另有 Total / Trend 两种特殊行（跳过）
- 未来日期的格子显示 0（过滤，不入库）

时区：页面矩阵为美东时间（用户确认比 UTC 早 4 小时）。
⚠️ 用 America/New_York 时区换算（自动处理夏令时）：2026-11-01 美国结束夏令时后
   变为 UTC-5。首次跨冬令时运行时需人工核对一次（与网页或手抄数据对比）。

用法：
  python fetch_muskmeter.py                          # 抓默认 URL（当前事件窗口），打印差异（不写库）
  python fetch_muskmeter.py --save                   # 同上，并把差异写回本地库（修复假 0 / 补缺）
  python fetch_muskmeter.py --start <unix> --end <unix> --event-id <id>
  python fetch_muskmeter.py --html _diag_musk_page.html   # 离线解析已保存的页面
  python fetch_muskmeter.py --check                  # 仅对比汇总，不列明细
"""

import sys
import re
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# 项目根目录加入 sys.path（对比模式查库用）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_URL = ("https://www.muskmeter.live/"
               "?start=1792771200&end=1793376000&eventId=1221575&eventType=weekly&source=3")

# 页面矩阵时区：美东。用 IANA 时区名而非固定 -4，自动处理冬令时切换
PAGE_TZ = "America/New_York"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url: str) -> str:
    """抓取页面。Vercel 反爬（429/Security Checkpoint）时给出可读报错"""
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 429 or "Security Checkpoint" in resp.text:
        raise RuntimeError(
            "被 Vercel 安全检查拦截（429）。可能是请求过频：等待几分钟再试，"
            "或降低采集频率。若 PA 服务器 IP 长期被拦，需改用其他方案（见 README 备注）")
    resp.raise_for_status()
    return resp.text


def parse_heatmap(html: str, end_ts: int):
    """解析小时 × 日期矩阵

    返回 (title, records):
      title: 页面事件标题，如 'Elon Musk # tweets October 23 - October 30, 2026?'
      records: [{date_et: 'YYYY-MM-DD', hour: 0..23, count: int|None, ts_utc: int, future: bool}]
    """
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(PAGE_TZ)

    # ---- 日期表头（只有 周几 + 日号，月份需要倒推） ----
    heads = re.findall(
        r'day-name svelte-[\w-]+">([A-Za-z]{3})</div>\s*'
        r'<div class="day-number svelte-[\w-]+">(\d+)<', html)
    if not heads:
        raise RuntimeError("未找到日期表头，页面结构可能已变化")
    n_days = len(heads)

    # 最后一列 = end 参数当天（美东日期），据此倒推所有列日期，并用周几做交叉校验
    weekday_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    end_dt = datetime.fromtimestamp(end_ts, tz=tz).date()
    days = []
    for k, (name, num) in enumerate(heads):
        d = end_dt - timedelta(days=n_days - 1 - k)
        if weekday_map.get(name) != d.weekday() or d.day != int(num):
            raise RuntimeError(
                f"日期倒推校验失败：表头 {name} {num} vs 计算 {d}（%a）。"
                f"页面列布局可能不是 [end-7天, end]，需要调整推断逻辑")
        days.append(d)

    # ---- 页面事件标题 ----
    m = re.search(r'>([^<]*[Tt]weets[^<]{0,60})<', html)
    title = m.group(1).strip() if m else "(未找到事件标题)"

    # ---- 小时行 ----
    # 按 hour-label 切分；只保留 HH:MM 形式（排除 Total/Trend/空表头）
    parts = re.split(r'hour-label svelte-[\w-]+">', html)
    now_utc = datetime.now(tz=None).astimezone().timestamp()

    records = []
    for seg in parts[1:]:
        hm = re.match(r'(\d{2}):(\d{2})<', seg)
        if not hm:
            continue
        hour = int(hm.group(1))

        cells = re.findall(r'<div class="cell[^"]*"[^>]*>([^<]*)</div>', seg)
        # 末尾是 AVG 浮点列，丢掉；不足的补 None
        if len(cells) > n_days and '.' in cells[-1]:
            cells = cells[:n_days]
        cells = (cells + [None] * n_days)[:n_days]

        for day_date, raw in zip(days, cells):
            raw = (raw or '').strip()
            if raw in ('', '—'):
                count = None
            elif raw.isdigit():
                count = int(raw)
            else:
                count = None

            # 美东时间 → UTC 时间戳（zoneinfo 自动处理夏令时）
            dt_et = datetime(day_date.year, day_date.month, day_date.day,
                             hour, 0, tzinfo=tz)
            ts_utc = int(dt_et.timestamp())
            records.append({
                'date_et': day_date.isoformat(),
                'hour': hour,
                'count': count,
                'ts_utc': ts_utc,
                'future': ts_utc > now_utc,
            })

    return title, records


def print_matrix(records, n_days=15):
    """按 天×小时 矩阵打印（future 标 *）"""
    from itertools import groupby
    by_date = {}
    for r in records:
        by_date.setdefault(r['date_et'], []).append(r)
    dates = sorted(by_date)
    print(f"{'hour':>6} | " + " ".join(f"{d[5:]:>4}" for d in dates))
    for hour in range(24):
        row = []
        for d in dates:
            r = next(x for x in by_date[d] if x['hour'] == hour)
            v = '  —' if r['count'] is None else f"{r['count']:>3}"
            if r['future']:
                v += '*'
            row.append(f"{v:>4}")
        print(f"{hour:02d}:00 | " + " ".join(row))
    print("(* = 未来时间，仅页面显示 0，不应入库)")


def _load_db_counts():
    """读取本地原始库 tweet_counts → {(date_et, hour): tweet_count}"""
    import sqlite3
    from scripts.data_fetcher.config import DB_PATH

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db = {}
    for ot, tc in conn.execute("SELECT original_time, tweet_count FROM tweet_counts"):
        d, h = ot.split(" ")
        db[(d, int(h.split(":")[0]))] = tc
    conn.close()
    return db


def check_against_db(records, summary_only=False):
    """对比模式：网页 vs 本地库（只读）"""
    db = _load_db_counts()
    matched = diff = missing = 0
    print("\n=== 与本地库 tweet_counts 对比（仅过去时间、有值的小时） ===")
    for r in records:
        if r['future'] or r['count'] is None:
            continue
        key = (r['date_et'], r['hour'])
        if key not in db:
            missing += 1
            if not summary_only:
                print(f"  ➕ 本地库缺 {r['date_et']} {r['hour']:02d}:00 → 网页={r['count']}")
            continue
        if db[key] == r['count']:
            matched += 1
        else:
            diff += 1
            if not summary_only:
                print(f"  ⚠️ 不一致 {r['date_et']} {r['hour']:02d}:00: "
                      f"网页={r['count']} 本地库={db[key]}")
    print(f"  一致: {matched}  不一致: {diff}  本地库缺: {missing}")


def save_to_db(records, fill_only=True, apply=False):
    """回填本地库

    fill_only=True（保守，推荐）: 只处理本地为 0 或缺失的格子——修复'定格的假 0'，
        绝不覆盖已确认的非零值（muskmeter 会追溯修订历史，覆盖有风险）
    fill_only=False（覆盖式）: 网页数据为准，值不同即覆盖

    apply=False 时只打印将执行的动作，不写库。
    返回 (inserted, updated, skipped_diff)
    """
    import sqlite3
    from scripts.data_fetcher.config import DB_PATH

    ABNORMAL = 805  # 与 import_tweets.py 相同的异常值过滤
    db = _load_db_counts()
    inserted = updated = skipped_diff = 0
    actions = []  # (action, original_time, old, new)

    for r in records:
        if r['future'] or r['count'] is None or r['count'] == ABNORMAL:
            continue
        key = (r['date_et'], r['hour'])
        original_time = f"{r['date_et']} {r['hour']:02d}:00"
        count = r['count']

        if key not in db:
            actions.append(('insert', original_time, None, count))
        elif db[key] != count:
            if fill_only and db[key] != 0:
                skipped_diff += 1
                continue
            actions.append(('update', original_time, db[key], count))

    if apply:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(PAGE_TZ)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for action, original_time, old, count in actions:
            if action == 'insert':
                dt_et = datetime.strptime(original_time, '%Y-%m-%d %H:%M').replace(tzinfo=tz)
                dt_utc = dt_et.astimezone(timezone.utc)
                cur.execute(
                    "INSERT OR IGNORE INTO tweet_counts "
                    "(original_time, utc_time, timestamp_unix_utc, tweet_count) "
                    "VALUES (?, ?, ?, ?)",
                    (original_time, dt_utc.isoformat(timespec='seconds'),
                     int(dt_utc.timestamp()), count))
                inserted += cur.rowcount
            else:
                cur.execute(
                    "UPDATE tweet_counts SET tweet_count = ? "
                    "WHERE original_time = ?", (count, original_time))
                updated += 1
        conn.commit()
        conn.close()
    else:
        for action, original_time, old, count in actions:
            if action == 'insert':
                print(f"  ➕ 新增 {original_time} → {count}")
            else:
                print(f"  ✏️ 修正 {original_time}: {old} → {count}")
        if not actions:
            print("  （无需修改，本地库已是最新）")

    print(f"\n  汇总: 新增 {len([a for a in actions if a[0]=='insert'])}, "
          f"修正 {len([a for a in actions if a[0]=='update'])}, "
          f"保守跳过 {skipped_diff}")
    return inserted, updated, skipped_diff


def main():
    parser = argparse.ArgumentParser(description="muskmeter 推文小时计数爬虫")
    parser.add_argument('--url', default=DEFAULT_URL, help='完整页面 URL')
    parser.add_argument('--html', help='离线解析本地保存的 HTML 文件（不联网）')
    parser.add_argument('--save', action='store_true',
                        help='把差异写回本地库（默认只打印差异）')
    parser.add_argument('--fill-only', action='store_true',
                        help='配合 --save：保守回填，只写本地为 0/缺失的格子，'
                             '不覆盖已确认的非零值（推荐，muskmeter 会修订历史）')
    parser.add_argument('--check', action='store_true', help='仅对比汇总，不列明细')
    args = parser.parse_args()

    # 从 URL 提取 end 参数（用于日期倒推）
    m = re.search(r'[?&]end=(\d+)', args.url)
    if not m:
        raise SystemExit("URL 中缺少 end 参数")
    end_ts = int(m.group(1))

    if args.html:
        html = Path(args.html).read_text(encoding='utf-8')
    else:
        print(f"🌐 抓取: {args.url}")
        html = fetch_html(args.url)
        print(f"✅ 抓取成功，{len(html):,} 字符")

    title, records = parse_heatmap(html, end_ts)
    print(f"\n📌 页面事件: {title}")
    print(f"📊 解析出 {len(records)} 条 (日期×小时) 记录")

    if args.save:
        mode = '保守回填（fill-only，只修 0/缺失）' if args.fill_only \
            else '覆盖式（网页数据为准）'
        print(f"\n=== 回填本地库 · {mode} ===")
        save_to_db(records, fill_only=args.fill_only, apply=True)
    elif args.check:
        check_against_db(records, summary_only=True)
    else:
        print_matrix(records)
        mode = '保守回填（fill-only，只修 0/缺失）' if args.fill_only \
            else '覆盖式（网页数据为准）'
        print(f"\n=== 回填预览 · {mode}（未写库） ===")
        save_to_db(records, fill_only=args.fill_only, apply=False)
        print("\n(确认无误后加 --save 执行)" if args.fill_only else
              "\n(覆盖式会改写 muskmeter 已修订的历史值，建议改用 --save --fill-only)")


if __name__ == '__main__':
    main()
