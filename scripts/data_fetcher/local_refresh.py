#!/usr/bin/env python3
"""
本地一键补全数据（跨平台，不依赖 shell 的 && 语法）

Windows 的 PyCharm 终端默认是 PowerShell 5.1，不支持 `&&`，链式命令会报
"标记 && 不是有效语句分隔符"。这个脚本用 Python 串流程，任何 shell 都能跑。

流程：
  1. create_tables             建表 / 迁移（幂等）
  2. sync_events               事件增量（series_id 驱动）
  3. sync_markets              市场增量
  4. sync_prices               价格增量（最慢，可用 --skip-prices 跳过）
  5. fetch_muskmeter --save     推文补全（爬虫，以 muskmeter 网页为准，覆盖式）
  6. aggregate_prices_tweets   小时级聚合（UPSERT，**不带 --force**）
  7. build_final_db            生成精简库（自动备份旧库为 .db.bak）
  8. check_db                  健康报告

用法：
    python scripts/data_fetcher/local_refresh.py                  # 全流程
    python scripts/data_fetcher/local_refresh.py --skip-prices    # 跳过价格（最快）
    python scripts/data_fetcher/local_refresh.py --from-tweets    # 只做推文→聚合→建库

说明：
- 价格阶段要逐市场请求 Polymarket，可能几分钟到几十分钟；中途断了不要紧，
  price_sync_state 会记账，重跑从断点继续。
- 推文爬虫失败（网络 / Vercel 拦截）只告警不中断：聚合和建库仍值得跑完，
  至少价格数据能进精简库。
- 想只补推文：`--from-tweets` 最快，跳过了事件/市场/价格三步。
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_DIR = PROJECT_ROOT / "scripts" / "data_fetcher"

# 事件同步用的系列（与 run_all.py 的 SERIES_CONFIG 保持一致）
SERIES_ARGS = ["--series-id", "10000", "--series-id", "10816", "--lookback-days", "7"]


def run_step(script: str, extra_args=None, required=True, desc: str = "") -> bool:
    """运行单个脚本，返回是否成功。子进程输出直接打到当前终端。"""
    cmd = [sys.executable, str(SCRIPT_DIR / script)] + (extra_args or [])
    print(f"\n{'=' * 70}")
    print(f"🚀 {desc or script}")
    print(f"{'=' * 70}")

    try:
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    except KeyboardInterrupt:
        print("\n⛔ 已中断（已写入的数据不会丢失，重跑即可续上）")
        sys.exit(130)

    ok = result.returncode == 0
    if not ok:
        tag = "❌ 失败" if required else "⚠️ 失败（非关键，继续后续步骤）"
        print(f"{tag}: {script}  (exit={result.returncode})")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="本地一键补全数据")
    parser.add_argument("--skip-prices", action="store_true",
                        help="跳过价格增量（最慢的一步）")
    parser.add_argument("--skip-events", action="store_true", help="跳过事件增量")
    parser.add_argument("--skip-markets", action="store_true", help="跳过市场增量")
    parser.add_argument("--skip-tweets", action="store_true", help="跳过推文爬虫")
    parser.add_argument("--from-tweets", action="store_true",
                        help="等价于同时跳过事件/市场/价格，只做推文→聚合→建库")
    parser.add_argument("--keep-going", action="store_true",
                        help="关键步骤失败也继续跑（默认失败即停）")
    args = parser.parse_args()

    t0 = time.time()

    steps = []

    if not args.from_tweets:
        steps.append(("create_tables.py", [], True, "建表 / 迁移"))
        if not args.skip_events:
            steps.append(("sync_events.py", SERIES_ARGS, True, "事件增量"))
        if not args.skip_markets:
            steps.append(("sync_markets.py", [], True, "市场增量"))
        if not args.skip_prices:
            steps.append(("sync_prices.py", [], True,
                          "价格增量（最慢，可加 --skip-prices）"))

    if not args.skip_tweets:
        steps.append(("fetch_muskmeter.py", ["--save"], False,
                      "推文补全（爬虫，覆盖式）"))

    steps.append(("aggregate_prices_tweets.py", [], True, "小时级聚合（UPSERT）"))
    steps.append(("build_final_db.py", [], False, "生成精简库"))
    steps.append(("check_db.py", [], False, "数据健康检查"))

    print("=" * 70)
    print("📦 本地数据补全")
    print(f"项目: {PROJECT_ROOT}")
    print(f"计划执行 {len(steps)} 个脚本" + ("（--keep-going）" if args.keep_going else ""))
    print("=" * 70)

    for script, extra, required, desc in steps:
        ok = run_step(script, extra, required=required, desc=desc)
        if not ok and required and not args.keep_going:
            print(f"\n❌ 关键步骤失败，已终止：{script}")
            print("   修好问题后可直接重跑本命令（已完成的步骤是幂等的）。")
            print(f"   或跳过它继续：python {Path(__file__).as_posix()} --from-tweets")
            return 1
        time.sleep(0.5)

    elapsed = time.time() - t0
    print(f"\n🎉 全部完成，用时 {elapsed:.0f} 秒")
    print("   下一步：重启本地应用（python app_new.py）后刷新页面，缓存才会失效。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
