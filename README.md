# Polymarket 数据分析平台

基于 Dash 的 Polymarket 预测市场数据分析平台，聚焦 Elon Musk 推文事件（7天 / 48小时系列）的价格-推文关联、市场命中模式与方向预测策略回测。

**公网地址**：https://13de11.pythonanywhere.com/

---

## 📂 目录结构

```
Polymarket_Analysis/
├── app_new.py # Dash 应用入口
├── config.py # 路径配置
├── requirements.txt
├── assets/ # 静态资源（CSS）
│ └── style.css
│
├── data/ # 数据目录（不入 git）
│ ├── polymarket_data.db # 原始全量库（本地分析用）
│ ├── elon_tweets_analysis.db # 精简库（Web 用）
│ └── experiments/ # 实验配置存储（预留）
│
├── scripts/ # 数据处理脚本
│ ├── build_final_db.py # 从原始库生成精简库
│ ├── check_db.py # 数据库健康检查
│ └── data_fetcher/ # API 数据采集
│ ├── create_tables.py
│ ├── fetch_events.py
│ ├── fetch_markets.py
│ ├── fetch_prices.py
│ ├── import_tweets.py
│ ├── aggregate_prices_tweets.py
│ └── run_all.py # 一键全流程
│
├── src/dash_app/ # Dash 应用
│ ├── pages/
│ │ ├── home.py
│ │ ├── price_tweet_analysis.py
│ │ ├── insights/ # 数据分析中心
│ │ │ ├── layout.py
│ │ │ ├── callbacks.py
│ │ │ └── explorer.py
│ │ ├── backtest/ # 预测回测
│ │ │ ├── init.py # 回调注册
│ │ │ ├── layout.py # 页面布局
│ │ │ ├── params_panel.py
│ │ │ └── tabs/
│ │ │ ├── preview.py
│ │ │ ├── overview.py
│ │ │ ├── trades.py
│ │ │ └── evaluation.py
│ │ └── research/ # 策略研究
│ │ ├── layout.py
│ │ ├── filter_panel.py
│ │ ├── experiment_manager.py # 实验保存/加载栏
│ │ └── tabs/
│ │ ├── comparison.py # 策略对比
│ │ └── sensitivity.py # 单/双参数敏感性
│ │
│ └── utils/
│ ├── data_loader.py # 数据读取（带 lru_cache）
│ ├── stats_loader.py # 统计聚合
│ ├── ui/
│ │ └── table.py # 表格样式工具（td/th/table）
│ ├── research/ # 研究模块基础设施
│ │ ├── params_schema.py # 参数/指标元数据（单一数据源）
│ │ ├── strategy_config.py # 策略配置 + 策略注册表
│ │ ├── experiment.py # 实验数据结构
│ │ ├── storage.py # 存储抽象（预留多用户）
│ │ └── serialize.py # numpy/datetime JSON 序列化
│ ├── signal/generator.py # 信号生成
│ ├── backtest/
│ │ ├── engine.py
│ │ ├── runner.py
│ │ ├── prepare.py
│ │ └── baseline.py
│ ├── metrics/
│ │ ├── calculator.py
│ │ ├── accuracy.py
│ │ └── hold_period.py
│ ├── comparison/engine.py # 多策略对比引擎
│ └── analysis/sensitivity.py # 单/双参数敏感性
│
└── archives/ # 旧项目备份（不入 git）
```


---

## 📄 页面结构

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 功能卡片 + 数据概览 |
| `/analysis` | 价格-推文分析 | 事件内各市场价格与推文关系 |
| `/insights` | 数据分析中心 | 命中模式、推文热度图谱（4 Tab） |
| `/backtest` | 预测回测 | 单事件回测与评估（4 Tab） |
| `/research` | 策略研究 | 策略对比、单/双参数敏感性、实验保存（2 Tab） |

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

3. 缓存说明
data_loader.py 的 6 个高频函数带 lru_cache，缓存 key 含当日日期，每天自动失效一次。

本地数据更新后如需立刻生效：重启应用

数据更新后不重启：第二天自动失效

手动清缓存：调用 data_loader.clear_caches()
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

🔬 策略研究模块

**数据流**:
PARAM_SCHEMA / METRIC_SCHEMA        参数与指标的单一数据源
        ↓
STRATEGY_REGISTRY                   策略类型注册表
        ↓
StrategyConfig                      一次回测的完整配置
        ↓
ComparisonEngine / SensitivityAnalysis  对比 / 敏感性
        ↓
run_backtest(params, series)        回测内核（与 /backtest 共用）

**核心能力**:
- 策略对比：3 张策略卡片，每张可覆盖任意参数（动态从 STRATEGY_REGISTRY 读）
- 单参数敏感性：从 PARAM_SCHEMA 自动生成扫描范围，支持指标方向（max/min）
- 双参数网格：热力图，色阶自动按指标方向反转
- 实验保存/加载：ExperimentConfig 序列化为 JSON，可下载/上传

**关键文件**:
- utils/research/params_schema.py：所有参数的 label / min / max / step / tunable
- utils/research/strategy_config.py：策略类型注册 + StrategyConfig 数据结构
- utils/research/experiment.py：ExperimentConfig（带 version，预留迁移）
- utils/research/storage.py：ExperimentStorage 抽象，为将来多用户准备

**新增参数 / 策略**:
- 加参数：PARAM_SCHEMA 加一条 → 卡片自动出现输入框
- 加策略：STRATEGY_REGISTRY 加一条 → 下拉自动出现 → 需在 runner.py 里按 strategy_id 分发

---

📈 回测模块

**执行架构**:
点击「运行回测」
    ↓
cache_backtest_result          唯一入口，跑一次 run_backtest
    ↓
backtest-result-store          结果存 store
    ↓
render_tab_content             4 个 tab 从 store 读
    ├─ preview:  独立路径（需完整信号序列）
    ├─ overview: 读 store
    ├─ trades:   读 store
    └─ evaluation: 读 store

**4 个 Tab**:
Tab	内容
🔍 信号预览	价格 + 推文 + 信号点 + 估算总量 vs 实际累计推文
📊 绩效概览	资金曲线 + 核心绩效 8 卡片 + 盈亏细节 5 卡片
📋 交易明细	表格（含份数期望/实际对比）+ 导出 CSV
📈 策略评估	多窗口准确率 + 持仓周期分桶 + 策略 vs 基线

**特殊说明**:
- 两个按钮：刷新信号预览（只更新 preview）/ 运行回测（跑完整回测，刷新其余 tab）
- 持仓周期分桶自适应：按最大持仓时长选桶边界
- 随机基线：20 次取均值 ± 标准差

---

🎨 表格样式工具
utils/ui/table.py 提供 td / th / table 三件套，统一表头与单元格居中对齐：

python
from src.dash_app.utils.ui.table import td, table as tbl
rows = [html.Tr([td('a'), td('b', color='red', fontWeight='bold')])]
return tbl(['列1', '列2'], rows)
td 支持任意 CSS 属性作为 kwargs（color / fontWeight / fontSize / textAlign ...）。

---

🗺️ 下一步计划

## 🗺️ 项目路线图

### 已完成的大阶段

| # | 阶段 | 状态 |
|---|------|------|
| 1 | 数据采集与数据库建设 | ✅ |
| 2 | 价格-推文分析 / 数据分析中心（基础版） | ✅ |
| 3 | 预测回测模块（基础框架） | ✅ |
| 4 | 策略研究模块（基础框架） | ✅ |
| 5 | **预测回测 + 策略研究模块优化**（本大阶段完成） | ✅ |

**阶段 5 具体成果**：

- **策略研究**：从"骨架"到"能研究"
  - `PARAM_SCHEMA` / `METRIC_SCHEMA` / `STRATEGY_REGISTRY` 单一数据源
  - 多策略对比引擎（任意策略 × 任意参数覆盖）
  - 单参数敏感性（范围从 schema 自动生成，支持指标方向）
  - 双参数网格热力图（色阶按指标方向自动反转）
  - 实验配置保存 / 加载（`ExperimentConfig` + JSON）
  - `data_loader` 6 个高频函数加 `lru_cache`
- **预测回测**：从"粗糙框架"到"架构干净"
  - 统一执行链（4 个 tab 从 store 读，不再 4 次重跑）
  - `format_metrics_for_display` 字段名对齐
  - 信号预览：删假曲线，加估算总量 vs 实际累计推文
  - 绩效概览：核心绩效 + 盈亏细节两组卡片
  - 策略评估：接线多窗口准确率、随机基线 20 次带 std
  - 交易明细：加导出 CSV
  - 持仓周期分桶自适应、`random_signal` 参数化
  - 表格样式工具化 `utils/ui/table.py`
  - `layout` 从 `__init__.py` 挪回 `layout.py`

### 待启动的大阶段

| # | 阶段 | 状态 |
|---|------|------|
| 6 | 其余页面优化：`insights/` / `price_tweet_analysis.py` / `home.py` | 🔲 下一阶段 |
| 7 | 多用户登录 + 服务器端实验历史 | 🔲 远期（最终目标） |

### 阶段 5 遗留的技术债

| 项 | 说明 | 计划 |
|----|------|------|
| 参数面板统一 | backtest / research 的参数面板高度重复 | 等两边功能对齐后，统一到 `PARAM_SCHEMA` 动态生成 |
| 全局回调风格统一 | 项目里混用 `@callback` 和 `app.callback` | 涉及多个模块，最后整体统一 |
| `generator.py` 内部状态 | `prev_distance` 在函数内和循环末尾各更新一次，当前行为正确但脆弱 | 策略定型后重构 |
| `baseline.random_signal` 风险暴露 | 随机信号是"全押"，策略是"固定金额"，基线对比不完全公平 | 阶段 6 或更晚处理 |
## 📝 说明

- `data/*.db` 不入 git（本地保留）
- `archives/` 为旧项目备份，不参与 Web
- 部署用精简库 `elon_tweets_analysis.db`（约 18 MB）