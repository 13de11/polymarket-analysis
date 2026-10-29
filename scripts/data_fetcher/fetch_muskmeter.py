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
import os
import re
import time
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

# 项目根目录加入 sys.path（对比模式查库用）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE = "https://www.muskmeter.live/"

def _default_url() -> str:
    """默认抓"最近 7 天 → 现在"的窗口（不带 eventId，muskmeter 支持任意时间窗口，
    已实测）。自动化场景下窗口随时间自动滑动，永不失效。"""
    now = int(time.time())
    return (f"{DEFAULT_BASE}?start={now - 7 * 86400}&end={now}"
            "&eventType=weekly&source=3")

# 页面矩阵时区：美东。用 IANA 时区名而非固定 -4，自动处理冬令时切换
PAGE_TZ = "America/New_York"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_html(url):
    """抓取页面：先直连，被 Vercel 安全检查拦截时自动降级到真实浏览器抓取。

    浏览器路径需要 playwright（pip install playwright && playwright install chromium），
    GitHub Actions 环境会安装；本地直连通常成功，用不到它。
    换请求头没有用——Vercel 拦的是数据中心 IP 的信誉，不是请求头。
    """
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 429 or "Security Checkpoint" in resp.text:
        print("  ⚠️ 直连被 Vercel 安全检查拦截，尝试真实浏览器抓取…")
        try:
            return fetch_html_browser(url)
        except ImportError:
            raise RuntimeError(
                "被 Vercel 安全检查拦截（429），且未安装 playwright 无法使用浏览器抓取。"
                "GitHub Actions 环境请确认 workflow 里已安装 playwright + chromium")
        except Exception as e:
            raise RuntimeError(f"直连被拦且浏览器抓取也失败: {e}")
    resp.raise_for_status()
    return resp.text


def fetch_html_browser(url):
    """真实浏览器抓取：自动执行 Vercel 挑战 JS 并通过

    浏览器驱动优先级：patchright（playwright 反检测补丁版）> playwright。
    启动参数做了无头自动化指纹隐藏（webdriver/chrome 对象等）。
    失败时输出诊断信息（页面标题 + 内容片段），便于判断卡在哪。
    """
    try:
        from patchright.sync_api import sync_playwright as sync_pw
        driver_name = 'patchright'
    except ImportError:
        from playwright.sync_api import sync_playwright as sync_pw
        driver_name = 'playwright'

    with sync_pw() as p:
        browser = None
        # 优先用系统安装的 Google Chrome（品牌通道，指纹比 chromium 更真实）
        for launch_kwargs in ({'channel': 'chrome', 'headless': True},
                              {'headless': True}):
            try:
                browser = p.chromium.launch(**launch_kwargs)
                break
            except Exception:
                continue
        if browser is None:
            raise RuntimeError('无法启动浏览器（chrome 通道和内置 chromium 都失败）')

        try:
            page = browser.new_page(user_agent=HEADERS['User-Agent'], locale='en-US')
            # 隐藏无头自动化的常见检测点
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = window.chrome || { runtime: {} };
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """)
            page.goto(url, wait_until='domcontentloaded', timeout=60000)

            # 检查点页会自动执行挑战 JS 后放行；循环等待真实热力图出现（最多 90 秒）
            deadline = time.time() + 90
            while time.time() < deadline:
                html = page.content()
                if 'Security Checkpoint' not in html and 'heatmap' in html:
                    return html
                page.wait_for_timeout(2000)

            # 诊断信息：看到底卡在什么页面
            html = page.content()
            snippet = re.sub(r'\s+', ' ', html)[:300]
            raise RuntimeError(
                f'等待 90 秒仍未通过安全检查 [driver={driver_name}] '
                f'页面标题="{page.title()}" 内容片段="{snippet}"')
        finally:
            browser.close()


def parse_heatmap(html: str, end_ts: int):
    """解析小时 × 日期矩阵

    页面上可能有多个 meter 的热力图（mojometers 系列组件），按 heatmap 分块，
    取含完整小时行（≥20 行）的推文主表。

    返回 (title, records):
      title: 页面事件标题，如 'Elon Musk # tweets October 23 - October 30, 2026?'
      records: [{date_et: 'YYYY-MM-DD', hour: 0..23, count: int|None, ts_utc: int, future: bool}]
    """
    from zoneinfo import ZoneInfo
    tz = ZoneInfo(PAGE_TZ)

    day_header_re = (r'day-name svelte-[\w-]+">([A-Za-z]{3})</div>\s*'
                     r'<div class="day-number svelte-[\w-]+">(\d+)<')

    # ---- 按 heatmap 分块，选小时行最全的块（推文主表） ----
    best_block = None
    for block in html.split('<div class="heatmap')[1:]:
        heads = re.findall(day_header_re, block)
        hour_rows = len(re.findall(r'hour-label svelte-[\w-]+">\d{2}:\d{2}<', block))
        if heads and hour_rows >= 20 and (best_block is None or hour_rows > best_block[1]):
            best_block = (heads, hour_rows, block)
    if best_block is None:
        raise RuntimeError("未找到推文热力图，页面结构可能已变化")
    heads, hour_rows_found, block = best_block
    n_days = len(heads)

    # 末列锚点推断：实测规则是 end 参数的 UTC 日期（滚动窗口 end=now 时页面会
    # 包含"今天"整列），但为健壮起见依次尝试多个锚点，取能使日号序列自洽的那个
    end_utc = datetime.fromtimestamp(end_ts, tz=timezone.utc).date()
    end_et = datetime.fromtimestamp(end_ts, tz=tz).date()
    today_et = datetime.now(tz).date()
    candidates = []
    for cand in (end_utc, end_et, today_et):
        if cand not in candidates:
            candidates.append(cand)

    days = None
    for anchor in candidates:
        cand_days = [anchor - timedelta(days=n_days - 1 - k) for k in range(n_days)]
        if all(d.day == int(num) for (name, num), d in zip(heads, cand_days)):
            days = cand_days
            break
    if days is None:
        raise RuntimeError(
            "日期倒推校验失败：所有锚点（end 的 UTC/ET 日期、今天）都无法对齐表头日号，"
            "页面列布局可能已变化，需要调整推断逻辑")

    # 星期仅警告不报错（实测网站对窗口首列的星期标注偶有 bug）
    weekday_map = {'Mon': 0, 'Tue': 1, 'Wed': 2, 'Thu': 3, 'Fri': 4, 'Sat': 5, 'Sun': 6}
    for (name, _), d in zip(heads, days):
        if weekday_map.get(name) != d.weekday():
            print(f"⚠️ 星期标注与推算不符（表头 {name} {d.day} 号，实际 {d}），按日号倒推继续")
            break

    # ---- 页面事件标题 ----
    m = re.search(r'>([^<]*[Tt]weets[^<]{0,60})<', html)
    title = m.group(1).strip() if m else "(未找到事件标题)"

    # ---- 小时行（仅限主表块内，避免混入其他 meter 的数据） ----
    # 按 hour-label 切分；只保留 HH:MM 形式（排除 Total/Trend/空表头）
    parts = re.split(r'hour-label svelte-[\w-]+">', block)
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
    parser.add_argument('--url', default=None,
                        help='完整页面 URL（不传则用 start/end 或默认最近 7 天窗口）')
    parser.add_argument('--start', type=int, help='窗口起点 unix 时间戳')
    parser.add_argument('--end', type=int, help='窗口终点 unix 时间戳（默认=现在）')
    parser.add_argument('--html', help='离线解析本地保存的 HTML 文件（不联网）')
    parser.add_argument('--save', action='store_true',
                        help='把差异写回本地库（默认只打印差异）')
    parser.add_argument('--fill-only', action='store_true',
                        help='配合 --save：保守回填，只写本地为 0/缺失的格子，'
                             '不覆盖已确认的非零值（推荐，muskmeter 会修订历史）')
    parser.add_argument('--push', action='store_true',
                        help='把解析出的小时推文推送到 PA 线上库'
                             '（POST /collect/tweets，需 --key 或环境变量 COLLECT_KEY）')
    parser.add_argument('--push-url', default='http://13de11.pythonanywhere.com/collect/tweets',
                        help='PA 推送端点地址')
    parser.add_argument('--key', default=os.environ.get('COLLECT_KEY', ''),
                        help='采集端点秘钥（也可用环境变量 COLLECT_KEY）')
    parser.add_argument('--check', action='store_true', help='仅对比汇总，不列明细')
    args = parser.parse_args()

    # 确定 URL：--url 优先，其次 --start/--end 拼接，都没传用默认滚动窗口
    if args.url:
        url = args.url
    elif args.start:
        end = args.end or int(time.time())
        url = (f"{DEFAULT_BASE}?start={args.start}&end={end}"
               "&eventType=weekly&source=3")
    else:
        url = _default_url()

    # 从 URL 提取 end 参数（用于日期倒推）
    m = re.search(r'[?&]end=(\d+)', url)
    if not m:
        raise SystemExit("URL 中缺少 end 参数")
    end_ts = int(m.group(1))

    if args.html:
        html = Path(args.html).read_text(encoding='utf-8')
    else:
        print(f"🌐 抓取: {url}")
        html = fetch_html(url)
        print(f"✅ 抓取成功，{len(html):,} 字符")

    title, records = parse_heatmap(html, end_ts)
    print(f"\n📌 页面事件: {title}")
    print(f"📊 解析出 {len(records)} 条 (日期×小时) 记录")

    if args.save:
        mode = '保守回填（fill-only，只修 0/缺失）' if args.fill_only \
            else '覆盖式（网页数据为准）'
        print(f"\n=== 回填本地库 · {mode} ===")
        save_to_db(records, fill_only=args.fill_only, apply=True)

    if args.push:
        # 推送到 PA 线上库：只推过去时间且有值的小时
        hours = [[r['ts_utc'], r['count']] for r in records
                 if not r['future'] and r['count'] is not None]
        if not args.key:
            raise SystemExit("❌ 缺少秘钥：--key 或环境变量 COLLECT_KEY")
        import requests
        print(f"\n=== 推送到线上（{args.push_url}），共 {len(hours)} 小时 ===")
        resp = requests.post(
            args.push_url,
            json={'hours': hours},
            headers={'X-Collect-Key': args.key},
            timeout=60)
        print(f"HTTP {resp.status_code}: {resp.text[:200]}")

    if not args.save and not args.push:
        if args.check:
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
