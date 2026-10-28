#!/usr/bin/env python3
"""
一键增量更新（v2，state 记账版）

流程（按顺序）：
  1. create_tables             建表/迁移（幂等：events.series_id 回填、price_sync_state）
  2. sync_events               事件增量（series_id 驱动，回看 7 天 + 在册状态刷新）
  3. sync_markets              市场增量（近 7 天事件 + 近 35 天无市场事件，UPSERT 保 token）
  4. sync_prices               价格增量（price_sync_state 记账，完成判定后不再重扫）
  5. import_tweets             推文宽表 -> 长表（增量；宽表 xlsx 是唯一手动步骤）
  6. aggregate_prices_tweets   小时级聚合（UPSERT，可自动修补历史空洞）
  7. build_final_db            生成精简库（Web 用）
  8. check_db                  健康报告

唯一手动步骤：更新 data/tweet_hourly_wide.xlsx（缺失时自动跳过第 5 步并警告）。

用法示例:
    python scripts/data_fetcher/run_all.py                  # 标准增量更新
    python scripts/data_fetcher/run_all.py --dry-run        # 价格阶段只打印任务清单
    python scripts/data_fetcher/run_all.py --full           # 价格全量重扫近 31 天
    python scripts/data_fetcher/run_all.py --skip-tweets    # 宽表还没更新时用
"""

import sys
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ========== 系列配置（series_id 为唯一权威标识，slug 仅作展示） ==========
SERIES_CONFIG = [
    {"id": "10000", "slug": "elon-tweets"},
    {"id": "10816", "slug": "elon-tweets-48h"},
]

SCRIPT_DIR = PROJECT_ROOT / "scripts" / "data_fetcher"


def run_script(script_name: str, args: list = None) -> bool:
    """运行单个脚本"""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"❌ 脚本不存在: {script_path}")
        return False

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    print(f"\n{'='*70}")
    print(f"🚀 运行: {script_name} {' '.join(args or [])}")
    print(f"{'='*70}")

    try:
        result = subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ 脚本执行失败（exit={e.returncode}）: {script_name}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Musk 系列一键增量更新（v2）")
    parser.add_argument("--lookback-days", type=int, default=7,
                        help="事件增量回看天数（默认 7，向前覆盖防缝隙）")
    parser.add_argument("--full", action="store_true", help="价格全量重扫近 31 天（忽略 complete 标记）")
    parser.add_argument("--dry-run", action="store_true", help="价格阶段只打印任务清单，不请求")
    parser.add_argument("--skip-events", action="store_true")
    parser.add_argument("--skip-markets", action="store_true")
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-tweets", action="store_true")
    parser.add_argument("--skip-aggregate", action="store_true")
    parser.add_argument("--skip-final-db", action="store_true")
    parser.add_argument("--skip-report", action="store_true")
    args = parser.parse_args()

    # ---------- 前置检查 ----------
    excel_path = PROJECT_ROOT / "data" / "tweet_hourly_wide.xlsx"
    tweets_ready = excel_path.exists()
    if not tweets_ready and not args.skip_tweets:
        print(f"⚠️ 推文宽表不存在: {excel_path}")
        print("   将自动跳过推文导入（其余步骤照常），或可加 --skip-tweets 消除此警告")

    print("=" * 70)
    print("📊 Musk 系列一键增量更新（v2）")
    print(f"系列: {[(c['id'], c['slug']) for c in SERIES_CONFIG]}")
    print(f"模式: {'全量重扫' if args.full else '增量'}{'（dry-run）' if args.dry_run else ''}")
    print("=" * 70)

    # ---------- 1. 建表/迁移 ----------
    print("\n【1/8】建表/迁移...")
    if not run_script("create_tables.py"):
        print("❌ 表结构准备失败，终止")
        return

    # ---------- 2. 事件增量 ----------
    if not args.skip_events:
        print("\n【2/8】事件增量...")
        event_args = []
        for config in SERIES_CONFIG:
            event_args.extend(["--series-id", config["id"]])
        event_args.extend(["--lookback-days", str(args.lookback_days)])
        if not run_script("sync_events.py", event_args):
            print("❌ 事件同步失败，终止后续流程")
            return
        time.sleep(1)
    else:
        print("\n【2/8】⏭️ 跳过事件增量")

    # ---------- 3. 市场增量 ----------
    if not args.skip_markets:
        print("\n【3/8】市场增量...")
        if not run_script("sync_markets.py"):
            print("❌ 市场同步失败，终止后续流程")
            return
        time.sleep(1)
    else:
        print("\n【3/8】⏭️ 跳过市场增量")

    # ---------- 4. 价格增量 ----------
    if not args.skip_prices:
        print("\n【4/8】价格增量...")
        price_args = ["--request-delay", "0.4"]
        if args.full:
            price_args.append("--full")
        if args.dry_run:
            price_args.append("--dry-run")
        if not run_script("sync_prices.py", price_args):
            print("❌ 价格同步失败，终止后续流程")
            return
        time.sleep(1)
    else:
        print("\n【4/8】⏭️ 跳过价格增量")

    # dry-run 到此为止（后面都是本地写库操作）
    if args.dry_run:
        print("\n🔍 dry-run 模式：价格任务清单已打印，后续写库步骤未执行")
        return

    # ---------- 5. 推文导入 ----------
    if not args.skip_tweets and tweets_ready:
        print("\n【5/8】推文导入（增量）...")
        if not run_script("import_tweets.py"):
            print("⚠️ 推文导入失败，继续后续步骤")
    else:
        print("\n【5/8】⏭️ 跳过推文导入（宽表未更新）")

    # ---------- 6. 小时级聚合 ----------
    if not args.skip_aggregate:
        print("\n【6/8】小时级聚合...")
        if not run_script("aggregate_prices_tweets.py"):
            print("⚠️ 聚合失败，继续后续步骤")
        time.sleep(1)
    else:
        print("\n【6/8】⏭️ 跳过聚合")

    # ---------- 7. 精简库 ----------
    if not args.skip_final_db:
        print("\n【7/8】构建精简数据库...")
        if not run_script("build_final_db.py"):
            print("⚠️ 精简库构建失败（若为 series_id 列导致，请反馈修 build_final_db.py）")
    else:
        print("\n【7/8】⏭️ 跳过精简库")

    # ---------- 8. 健康报告 ----------
    if not args.skip_report:
        print("\n【8/8】数据健康检查...")
        run_script("check_db.py")

    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()
