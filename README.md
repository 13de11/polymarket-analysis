# Polymarket 数据分析平台

基于 Dash 的 Polymarket 预测市场数据分析平台，聚焦 Elon Musk 推文事件（7天 / 48小时系列）的价格-推文关联、市场命中模式与方向预测策略回测。

**公网地址**：https://13de11.pythonanywhere.com/

---

## 📂 目录结构

```
Polymarket_Analysis/
├── app_new.py                    # Dash 应用入口
├── config.py                     # 路径配置
├── requirements.txt
├── assets/                       # 静态资源（CSS）
│   └── style.css
│
├── data/                         # 数据目录（不入 git）
│   ├── polymarket_data.db        # 原始全量库（本地分析用）
│   └── elon_tweets_analysis.db   # 精简库（Web 用）
│
├── scripts/                      # 数据处理脚本
│   ├── build_final_db.py         # 从原始库生成精简库
│   ├── check_db.py               # 数据库健康检查
│   └── data_fetcher/             # API 数据采集
│       ├── create_tables.py
│       ├── fetch_events.py
│       ├── fetch_markets.py
│       ├── fetch_prices.py
│       ├── import_tweets.py
│       ├── aggregate_prices_tweets.py
│       └── run_all.py            # 一键全流程
│
├── src/dash_app/                 # Dash 应用
│   ├── components/
│   │   └── params_panel.py       # 回测参数面板
│   ├── pages/
│   │   ├── home.py
│   │   ├── price_tweet_analysis.py
│   │   ├── insights_dashboard.py
│   │   └── prediction_backtest.py
│   └── utils/
│       ├── data_loader.py        # 数据读取
│       ├── stats_loader.py       # 统计聚合
│       ├── signal/generator.py   # 信号生成
│       ├── backtest/
│       │   ├── engine.py         # 回测引擎
│       │   └── runner.py         # 回测执行器
│       ├── comparison/engine.py  # 策略对比
│       ├── analysis/sensitivity.py
│       └── metrics/calculator.py
│
└── archives/                     # 旧项目备份（不入 git）
```

---

## 🚀 快速开始

### 1. 环境

```bash
pip install -r requirements.txt
```

### 2. 本地运行

```bash
python app_new.py
```

浏览器打开 `http://localhost:8050`。

---

## 📊 数据处理流程

```
1. API 拉取原始数据
   python scripts/data_fetcher/run_all.py

2. 生成精简库（Web 用）
   python scripts/build_final_db.py

3. 检查数据健康
   python scripts/check_db.py
```

**一键全流程**：
```bash
python scripts/data_fetcher/run_all.py
```

**增量拉取**（默认）：
- 事件：从最新 start_date 往后拉
- 市场：只拉没有市场的事件
- 价格：从最新 timestamp 往后拉

**全量拉取**：
```bash
python scripts/data_fetcher/run_all.py --full
```

---

## 🌐 部署流程

### 1. 代码更新

**本地**：
```bash
git add -A
git commit -m "..."
git push origin main
```

**PythonAnywhere Bash**：
```bash
cd /home/13de11/polymarket-analysis
git pull origin main
```

**PythonAnywhere Web 页面**：点 **Reload**。

### 2. 数据库更新

1. 本地跑 `python scripts/build_final_db.py`
2. 浏览器登录 PythonAnywhere → **Files** → `data/` 目录
3. 上传 `elon_tweets_analysis.db`（覆盖）
4. Web 页面点 **Reload**

---

## 🔧 常用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/build_final_db.py` | 从原始库构建精简库 |
| `scripts/check_db.py` | 打印两个库的状态 |
| `scripts/data_fetcher/run_all.py` | 一键拉取全流程 |
| `scripts/data_fetcher/create_tables.py` | 创建表结构 |
| `scripts/data_fetcher/fetch_events.py` | 拉取事件 |
| `scripts/data_fetcher/fetch_markets.py` | 拉取市场 |
| `scripts/data_fetcher/fetch_prices.py` | 拉取价格 |
| `scripts/data_fetcher/import_tweets.py` | 导入推文（Excel → DB） |
| `scripts/data_fetcher/aggregate_prices_tweets.py` | 聚合小时级数据 |

---

## 🧠 策略逻辑简述

**方向判断**：
1. 估算总量 = 平均推文速率 × 剩余小时数
2. 距离 = |估算总量 − 市场中位数|
3. 容差过滤：距离 ≤ 容差 → 看平（→）
4. 噪音过滤：距离变动 ≤ 阈值 且 价格变动 ≤ 阈值 → 不触发新信号
5. 方向判断：距离变小 → 看涨（↑）；变大 → 看跌（↓）
6. 惯性保护：连续 ≥ N 小时无有效信号 → 强制看平

**推文速率窗口**：
- `7d`：最近 168 小时滚动平均
- `gamestart`：从统计起点到当前累计平均
- `open`：从事件开盘到当前累计平均
- `自定义`：最近 N 小时滚动平均

**回测规则**：
- ↑ 信号 + 空仓 → 开仓
- ↓ 信号 + 持仓 → 平仓
- → 信号 → 不动
- 回测结束强制平仓
- 仅做多

---

## 📝 说明

- `data/*.db` 不入 git（本地保留）
- `archives/` 为旧项目备份，不参与 Web
- 部署用精简库 `elon_tweets_analysis.db`（约 18 MB）