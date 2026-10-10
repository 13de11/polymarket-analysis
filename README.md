# Polymarket 数据分析平台

基于 Dash 的 Polymarket 预测市场数据分析平台，聚焦 Elon Musk 推文事件（7天 / 48小时系列）的价格-推文关联、市场命中模式与方向预测策略回测。

**公网地址**：https://13de11.pythonanywhere.com/

---

## 📂 目录结构

```
Polymarket_Analysis/
├── app_new.py                    # Dash 应用入口（layout + 顶层回调 + register_* 调用）
├── config.py                     # 路径配置
├── requirements.txt
├── assets/
│   └── style.css
│
├── data/                         # 数据目录（不入 git）
│   ├── polymarket_data.db        # 原始全量库（本地分析用）
│   ├── elon_tweets_analysis.db   # 精简库（Web 用）
│   └── experiments/              # 实验配置（预留服务器端存储）
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
│       └── run_all.py
│
├── src/dash_app/                 # Dash 应用
│   ├── state/                    # 全局状态（处理层共享）
│   │   └── global_params.py      # 处理层共享参数结构 + helper
│   │
│   ├── pages/
│   │   ├── home.py
│   │   ├── price_tweet_analysis.py
│   │   ├── insights/             # 数据分析中心
│   │   │   ├── layout.py
│   │   │   ├── callbacks.py
│   │   │   └── explorer.py
│   │   │
│   │   ├── shared/               # 跨页面共享组件
│   │   │   └── params_panel.py   # 参数面板生成器（schema 驱动）
│   │   │
│   │   ├── backtest/             # 预测回测
│   │   │   ├── __init__.py       # 仅 docstring
│   │   │   ├── layout.py         # 页面布局
│   │   │   ├── callbacks.py      # 所有 @callback
│   │   │   ├── params_panel.py   # 参数面板（调用 shared 生成器）
│   │   │   └── tabs/
│   │   │       ├── preview.py
│   │   │       ├── overview.py
│   │   │       ├── trades.py
│   │   │       └── evaluation.py
│   │   │
│   │   └── research/             # 策略研究
│   │       ├── layout.py
│   │       ├── filter_panel.py
│   │       ├── experiment_manager.py   # 实验保存/加载栏
│   │       └── tabs/
│   │           ├── comparison.py       # 策略对比
│   │           ├── sensitivity.py      # 单/双参数敏感性
│   │           └── batch.py            # 跨事件批量研究
│   │
│   └── utils/
│       ├── data_loader.py        # 数据读取（lru_cache）
│       ├── stats_loader.py       # 统计聚合
│       ├── parsing.py            # 输入安全转换（safe_int / safe_float）
│       ├── ui/
│       │   └── table.py          # 表格样式工具（td / th / table）
│       ├── research/             # 研究模块基础设施
│       │   ├── params_schema.py      # 参数/指标元数据（单一数据源）
│       │   ├── strategy_config.py    # 策略类型注册 + StrategyConfig
│       │   ├── experiment.py         # ExperimentConfig 数据结构
│       │   ├── storage.py            # ExperimentStorage 抽象
│       │   ├── serialize.py          # numpy/datetime JSON 序列化
│       │   └── batch.py              # BatchEngine 多事件批量研究引擎
│       ├── signal/generator.py   # 方向信号生成
│       ├── backtest/
│       │   ├── engine.py         # 交易执行
│       │   ├── runner.py         # run_backtest / build_signal_context
│       │   ├── prepare.py        # 数据准备（lru_cache）
│       │   └── baseline.py       # 基线策略
│       ├── metrics/
│       │   ├── calculator.py     # 指标计算 + 显示格式化
│       │   ├── accuracy.py       # 多窗口方向准确率
│       │   └── hold_period.py    # 持仓周期分析（分桶自适应）
│       ├── comparison/engine.py  # 多策略对比引擎
│       └── analysis/sensitivity.py  # 单/双参数敏感性
│
└── archives/                     # 旧项目备份（不入 git）
```

---

## 📄 页面结构

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 功能卡片 + 数据概览 |
| `/analysis` | 价格-推文分析 | 事件内各市场价格与推文关系 |
| `/insights` | 数据分析中心 | 命中模式、推文热度图谱（4 Tab） |
| `/backtest` | 预测回测 | 单事件回测与评估（4 Tab） |
| `/research` | 策略研究 | 策略对比、单/双参数敏感性、跨事件批量（3 Tab） |

---

## 🚀 快速开始

```bash
pip install -r requirements.txt
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
2. 登录 PythonAnywhere → **Files** → `data/` 目录
3. **先删** `elon_tweets_analysis.db-wal` 和 `elon_tweets_analysis.db-shm`
4. 再上传 `elon_tweets_analysis.db`（覆盖）
5. Web 页面点 **Reload**

> `.db-wal` / `.db-shm` 是 SQLite WAL 模式的附属文件，数据更新时若不清掉可能读到旧数据。

### 3. 缓存说明

`data_loader.py` 和 `backtest/prepare.py` 的多个高频函数带 `lru_cache`，cache key 含当日日期，**每天自动失效一次**。

- 数据更新后如需立刻生效：重启应用
- 数据更新后不重启：第二天自动失效
- 手动清缓存：`data_loader.clear_caches()` / `prepare.clear_prepare_cache()`

### 4. PythonAnywhere 常见坑（已踩过的）

- **Web 标签 → Code 区**：
  - `Source code` 和 `Working directory` **必须都填** `/home/13de11/polymarket-analysis`
  - 填错会导致 Dash 版本错位、样式不一致（曾踩过坑）
- **Python 版本**：Web app 的 Python 版本要与 Bash 里 `python -c "import dash; print(dash.__version__)"` 一致
- **依赖升级后**：Web 页面 Reload + 浏览器 `Ctrl + Shift + R`
- **首次访问 `/research` 或 `/backtest`**：会慢 1~2 秒（建 `lru_cache`），之后正常

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

**定位说明**：本工具的回测**不是策略优化器**，而是**信号处理效果的评价器**——交易规则固定为 ↑开仓/↓平仓，回测用于感知信号在不同参数下的效果。

---

## 🔬 策略研究模块

### 数据流

```
PARAM_SCHEMA / METRIC_SCHEMA        参数与指标元数据（单一数据源）
        ↓
STRATEGY_REGISTRY                   策略类型注册表
        ↓
StrategyConfig                      一次回测的完整配置
        ↓
ComparisonEngine / SensitivityAnalysis / BatchEngine
        ↓
run_backtest(params)                回测内核（与 /backtest 共用）
```

### 核心能力

1. **策略对比**：3 张策略卡片，每张可覆盖任意参数（动态从 `STRATEGY_REGISTRY` 读）
   - 资金曲线对比 + 绩效散点图（收益-夏普平面）+ 指标对比表
   - 导出指标表 / 交易明细 CSV
2. **单参数敏感性**：扫描范围从 `PARAM_SCHEMA` 自动生成，支持指标方向（max / min）
3. **双参数网格**：热力图，色阶按指标方向自动反转
4. **跨事件批量研究**：
   - 事件多选（默认全选）
   - 聚合统计表（收益均值 / 中位数 / 标准差 / 正事件率）
   - 事件 × 策略 收益矩阵热力图
   - 逐事件明细 DataTable（排序 / 分页 / 导出）
5. **实验保存/加载**：`ExperimentConfig` 序列化为 JSON，可下载/上传

### 关键文件

- `utils/research/params_schema.py`：所有参数的 label / min / max / step / **id** / group / ui
- `utils/research/strategy_config.py`：策略类型注册 + `StrategyConfig`
- `utils/research/experiment.py`：`ExperimentConfig`（带 version，预留迁移）
- `utils/research/storage.py`：`ExperimentStorage` 抽象（为将来多用户准备）
- `utils/research/batch.py`：`BatchEngine` 多事件批量研究引擎

### 扩展方式

- **加参数**：`PARAM_SCHEMA` 加一条 → 面板自动出现
- **加策略**：`STRATEGY_REGISTRY` 加一条 → 下拉自动出现 → 需在 `runner.py` 里按 `strategy_id` 分发（**分发逻辑尚未实现**）

---

## 📈 回测模块

### 执行架构

```
点击「运行回测」
    ↓
save_params                    从组件读值 → global-params（带 _trigger 标记）
    ↓
cache_backtest_result          监听 global-params；_trigger='run' 时才跑
    ↓
backtest-result-store          结果存 store
    ↓
render_tab_content             4 个 tab 从 store 读
    ├─ preview:  独立路径（build_signal_context）
    ├─ overview: 读 store
    ├─ trades:   读 store
    └─ evaluation: 读 store
```

### 4 个 Tab

| Tab | 内容 |
|------|------|
| 🔍 信号预览 | 价格 + 推文 + 信号点（上图）/ 估算总量 vs 实际累计推文（下图） |
| 📊 绩效概览 | 资金曲线（含买卖点标记）+ 核心绩效 8 卡片 + 盈亏细节 5 卡片 |
| 📋 交易明细 | DataTable（排序 / 分页 / 导出）+ 外置筛选（结果 / 平仓原因 / 只看部分成交） |
| 📈 策略评估 | 多窗口准确率 + 策略 vs 基线（20 次均值 ± 标准差）+ 交易分布直方图 + 持仓周期分桶 |

### 参数面板

- 由 `pages/shared/params_panel.py` **schema 驱动生成**
- 分四步折叠：数据选择 / 观察维度 / 信号参数 / 评价假设
- 组件 ID 由 `PARAM_SCHEMA[key]['id']` 显式声明

### 特殊说明

- **两个按钮**：`刷新信号预览`（只更新 preview）/ `运行回测`（跑完整回测）
- **回调风格**：backtest 模块已统一到现代 `@callback` 风格（`callbacks.py`）；research / insights 仍是 `register_*(app)` 老风格
- **失败提示**：回测失败时状态栏和内容区显示红字原因
- **输入即时生效**：`dcc.Input` 无 debounce

---

## 🎨 表格样式工具

`utils/ui/table.py` 提供 `td` / `th` / `table` 三件套：

```python
from src.dash_app.utils.ui.table import td, table as tbl

rows = [html.Tr([td('a'), td('b', color='red', fontWeight='bold')])]
return tbl(['列1', '列2'], rows)
```

`td` 支持任意 CSS 属性作为 kwargs。

**注意**：backtest 交易明细、research 批量研究明细用 `dash_table.DataTable`（排序/筛选/分页/导出），不走这个工具。

---

## 🗺️ 待办清单

按模块 + 优先级组织。编号供后续对话直接引用（如"做 R1"）。

### 🔴 高优先

| 编号 | 方向 | 模块 | 备注 |
|------|------|------|------|
| M1~M3 | 扫描 `insights/` / `price_tweet_analysis.py` / `home.py` 的表格对齐 | 观察层 | 用 `utils/ui/table.py` 统一 |
| M4 | 检查上述三页面是否有"多次重跑"架构问题 | 观察层 | 参考 backtest 的坑 |
| R4 | 策略类型扩展：`buy_hold` / `reverse_signal` / 双均线 | 策略研究 | 需在 `runner.py` 按 `strategy_id` 分发 |
| R5 | 窗口作为策略级覆盖项（A/B/C 用不同 `window_type`） | 策略研究 | 现在窗口是全局基础参数 |

### 🟠 中优先

| 编号 | 方向 | 模块 | 备注 |
|------|------|------|------|
| **C1** | **跨页带参功能（挂起）** | 全局 | 试过多种方案均失败，代码保留但按钮隐藏，实际点击不生效 |
| E1 | 多事件聚合统计：跨事件看策略稳定性 | 策略研究 | 与批量研究相关 |
| B3 | 参数面板统一到 schema（research 侧） | 策略研究 | backtest 已迁移，research 待做 |
| T1 | 回调风格统一（research / insights 尚未统一） | 全局 | `@callback` vs `register_*(app)` |
| T2 | Tab 改用 `dcc.Tabs` children 机制（research） | 全局 | 现在用 `style={'display'}` 切换 |

### 🟡 低优先 / 技术债

| 编号 | 方向 | 模块 | 备注 |
|------|------|------|------|
| T3 | `generator.py` 状态管理重构（`prev_distance` 双重更新） | 信号 | 策略定型后做 |
| T4 | `baseline.random_signal` 风险暴露公平性（全押 vs 固定金额） | 回测 | 基线对比不严格公平 |
| T7 | 研究面板懒加载（`create_research_panel` 不查库） | 策略研究 | 缓存后已不痛 |
| T5b | 敏感性/网格分析多线程或向量化提速 | 基础设施 | 纯 Python 循环是当前瓶颈 |

### 🔵 远期

| 编号 | 方向 | 备注 |
|------|------|------|
| R6 | 实验服务器端存储（`LocalFileStorage` 接口已就绪） | 数据落在 `data/experiments/` |
| R7 | 多用户登录 + 历史记录 | 最终目标，涉及 `flask_login` 或 session |
| E2 | 参数寻优（敏感性反过来自动搜最优） | 现有扫描的延伸 |
| E3 | 实时数据接入（事件进行中也能分析） | 架构变化大 |
| E4 | 策略信号导出（给外部工具） | — |

---

## 📝 说明

- `data/*.db` 不入 git（本地保留）
- `archives/` 为旧项目备份，不参与 Web
- 部署用精简库 `elon_tweets_analysis.db`（约 18 MB）
- `_test_*.py` / `_find_*.py` 为本地调试脚本，不入 git
- **当前全局 store**：`global-params` 定义在 `app_new.py`，结构见 `state/global_params.py`

---

## 📌 版本状态

- **稳定可用**：观察层（`/analysis`、`/insights`）、回测模块、策略研究三 Tab、实验保存/加载
- **已知失效**：跨页带参（comparison / sensitivity / batch → backtest），按钮保留但无效
- **近期重构重点**：`backtest` 已迁移到 schema 驱动面板 + 全局 store；research 侧待迁移