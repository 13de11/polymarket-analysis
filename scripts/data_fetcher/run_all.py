#!/usr/bin/env python3
"""
一键运行所有数据采集脚本
按顺序执行：建表 → 拉取事件 → 拉取市场 → 拉取价格 → 导入推文 → 聚合价格与推文

用法示例:
    # 默认配置（增量拉取 elon-tweets 系列，从 2026-05-01 开始）
    python scripts/data_fetcher/run_all.py

    # 全量拉取
    python scripts/data_fetcher/run_all.py --full

    # 指定日期范围
    python scripts/data_fetcher/run_all.py --start-date-min 2026-08-01T00:00:00Z
"""

import sys
import subprocess
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ========== Musk 系列配置 ==========
SERIES_CONFIG = [
    {"id": "10000", "slug": "elon-tweets"},
    {"id": "10816", "slug": "elon-tweets-48h"},
]
DEFAULT_START_DATE = "2026-05-01T00:00:00Z"


def run_script(script_name: str, args: list = None) -> bool:
    """运行单个脚本"""
    script_path = PROJECT_ROOT / "scripts" / "data_fetcher" / script_name
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
        print(f"❌ 脚本执行失败: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Musk 事件一键拉取")
    parser.add_argument("--start-date-min", default=DEFAULT_START_DATE,
                        help=f"开始日期（默认: {DEFAULT_START_DATE}）")
    parser.add_argument("--full", action="store_true", help="全量拉取")
    parser.add_argument("--skip-events", action="store_true", help="跳过事件")
    parser.add_argument("--skip-markets", action="store_true", help="跳过市场")
    parser.add_argument("--skip-prices", action="store_true", help="跳过价格")
    parser.add_argument("--skip-tweets", action="store_true", help="跳过推文导入")
    parser.add_argument("--skip-aggregate", action="store_true", help="跳过聚合")

    args = parser.parse_args()

    print("=" * 70)
    print("📊 Musk 事件数据一键拉取")
    print(f"系列: {[c['slug'] for c in SERIES_CONFIG]}")
    print(f"开始日期: {args.start_date_min}")
    print(f"全量模式: {'是' if args.full else '否（增量）'}")
    print("=" * 70)

    # ---------- 0. 建表 ----------
    print("\n📋 确保表结构存在...")
    run_script("create_tables.py")
    time.sleep(1)

    # ---------- 1. 事件 ----------
    if not args.skip_events:
        event_args = []
        for config in SERIES_CONFIG:
            event_args.extend(["--series-id", config["id"]])
        event_args.extend(["--start-date-min", args.start_date_min])
        if args.full:
            event_args.append("--full")
        if not run_script("fetch_events.py", event_args):
            print("❌ 事件拉取失败，终止后续流程")
            return
        time.sleep(2)
    else:
        print("⏭️ 跳过拉取事件")

    # ---------- 2. 市场 ----------
    if not args.skip_markets:
        market_args = []
        for config in SERIES_CONFIG:
            market_args.extend(["--series-slug", config["slug"]])
        if args.full:
            market_args.append("--force")
        if not run_script("fetch_markets.py", market_args):
            print("❌ 市场拉取失败，终止后续流程")
            return
        time.sleep(2)
    else:
        print("⏭️ 跳过拉取市场")

    # ---------- 3. 价格 ----------
    if not args.skip_prices:
        price_args = []
        for config in SERIES_CONFIG:
            price_args.extend(["--series-slug", config["slug"]])
        # 不传 --days-back，走增量逻辑
        price_args.extend(["--request-delay", "0.5"])
        price_args.extend(["--retry-limit", "2"])
        price_args.extend(["--event-start-date-min", args.start_date_min])
        if args.full:
            price_args.append("--full")
        if not run_script("fetch_prices.py", price_args):
            print("❌ 价格拉取失败")
            return
        time.sleep(2)
    else:
        print("⏭️ 跳过拉取价格")

    # ---------- 4. 推文导入 ----------
    if not args.skip_tweets:
        if not run_script("import_tweets.py"):
            print("⚠️ 推文导入失败，继续执行后续步骤")
        time.sleep(2)
    else:
        print("⏭️ 跳过推文导入")

    # ---------- 5. 聚合 ----------
    if not args.skip_aggregate:
        # 如果有事件，只聚合一两个新事件
        if not run_script("aggregate_prices_tweets.py"):
            print("⚠️ 聚合失败")
        time.sleep(2)
    else:
        print("⏭️ 跳过聚合")

    # ---------- 6. 构建精简数据库 ----------
    print("\n🔄 构建精简数据库...")
    subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "build_final_db.py")], cwd=str(PROJECT_ROOT))

    print("\n🎉 全部完成！")


if __name__ == "__main__":
    main()