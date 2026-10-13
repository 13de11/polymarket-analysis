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
├── assets/
│   └── style.css                 # 全站样式 + CSS 设计系统
│
├── data/                         # 数据目录（不入 git）
│   ├── polymarket_data.db        # 原始全量库（本地分析用）
│   ├── elon_tweets_analysis.db   # 精简库（Web 用）
│   └── experiments/              # 实验配置（预留）
│
├── scripts/                      # 数据处理脚本
│   ├── build_final_db.py         # 从原始库生成精简库
│   ├── check_db.py               # 数据库健康检查
│   └── data_fetcher/
│       ├── create_tables.py
│       ├── fetch_events.py       # 事件抓取（增量回看 15 天）
│       ├── fetch_markets.py
│       ├── fetch_prices.py
│       ├── import_tweets.py
│       ├── aggregate_prices_tweets.py  # 小时级聚合
│       └── run_all.py
│
├── src/dash_app/
│   ├── state/                    # 处理层全局状态
│   │   └── global_params.py
│   │
│   ├── ui/                       # UI 通用资源
│   │   └── theme.py              # 颜色常量（Plotly 图表用）
│   │
│   ├── pages/
│   │   ├── home.py
│   │   ├── price_tweet_analysis.py
│   │   ├── insights/
│   │   │   ├── layout.py
│   │   │   ├── callbacks.py
│   │   │   ├── explorer.py
│   │   │   └── _blocks.py        # 通用 UI 块（info_block 等）
│   │   ├── shared/
│   │   │   └── params_panel.py   # 参数面板生成器
│   │   ├── backtest/
│   │   │   ├── layout.py
│   │   │   ├── callbacks.py
│   │   │   ├── params_panel.py
│   │   │   └── tabs/
│   │   │       ├── preview.py
│   │   │       ├── overview.py
│   │   │       ├── trades.py
│   │   │       └── evaluation.py
│   │   └── research/
│   │       ├── layout.py
│   │       ├── filter_panel.py
│   │       ├── experiment_manager.py
│   │       └── tabs/
│   │           ├── comparison.py
│   │           ├── sensitivity.py
│   │           └── batch.py
│   │
│   └── utils/
│       ├── data_loader.py        # 数据读取（lru_cache）
│       ├── stats_loader.py
│       ├── parsing.py
│       ├── ui/
│       │   └── table.py          # 表格样式工具（td / th / table）
│       ├── research/
│       │   ├── params_schema.py
│       │   ├── strategy_config.py
│       │   ├── experiment.py
│       │   ├── storage.py
│       │   ├── serialize.py
│       │   └── batch.py
│       ├── signal/generator.py
│       ├── backtest/
│       │   ├── engine.py
│       │   ├── runner.py
│       │   ├── prepare.py
│       │   └── baseline.py
│       ├── metrics/
│       │   ├── calculator.py
│       │   ├── accuracy.py
│       │   └── hold_period.py
│       ├── comparison/engine.py
│       └── analysis/sensitivity.py
│
└── archives/
```

---

## 📄 页面结构

| 路径 | 页面 | 功能 |
|------|------|------|
| `/` | 首页 | 功能卡片（4 个）+ KPI 数据概览（响应 series 切换） |
| `/analysis` | 价格-推文分析 | 事件内各市场价格与推文关系 |
| `/insights` | 数据分析中心 | 命中模式、推文热度图谱、推文探索器（4 Tab） |
| `/backtest` | 预测回测 | 单事件信号评价（4 Tab） |
| `/research` | 策略研究 | 策略对比、敏感性、批量研究（3 Tab） |

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
1. 拉事件（增量：回看 15 天，避免状态漏更新）
   python scripts/data_fetcher/fetch_events.py --tag tweets-markets

2. 拉市场（增量：只拉未处理事件）
   python scripts/data_fetcher/fetch_markets.py

3. 拉价格（从最新时间戳往后）
   python scripts/data_fetcher/fetch_prices.py

4. 导入推文（Excel → DB）
   python scripts/data_fetcher/import_tweets.py

5. 聚合小时级数据
   python scripts/data_fetcher/aggregate_prices_tweets.py

6. 生成精简库（Web 用）
   python scripts/build_final_db.py

7. 检查数据健康
   python scripts/check_db.py
```

**一键全流程**：`python scripts/data_fetcher/run_all.py`

**每月建议**：跑一次**全量刷新**，兜住增量漏掉的状态更新。

```bash
python scripts/data_fetcher/fetch_events.py --tag tweets-markets --full
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
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

**Web 页面**：点 **Reload**。**浏览器**：`Ctrl + Shift + R`。

### 2. 数据库更新

1. 本地跑 `python scripts/build_final_db.py`
2. 登录 PythonAnywhere → **Files** → `data/` 目录
3. **先删** `elon_tweets_analysis.db-wal` 和 `elon_tweets_analysis.db-shm`
4. 再上传 `elon_tweets_analysis.db`（覆盖）
5. Web 页面点 **Reload**

### 3. 缓存说明

`data_loader.py` 和 `backtest/prepare.py` 的高频函数带 `lru_cache`，cache key 含当日日期，**每天自动失效一次**。

- 数据更新后立刻生效：重启应用
- 不重启：第二天自动失效
- 手动清：`data_loader.clear_caches()` / `prepare.clear_prepare_cache()`

### 4. PythonAnywhere 常见坑

- **Web 标签 → Code 区**：
  - `Source code` 和 `Working directory` 都填 `/home/13de11/polymarket-analysis`
- **依赖升级后**：Web Reload + 浏览器 `Ctrl + Shift + R`
- **首次访问 `/research` 或 `/backtest`**：慢 1~2 秒（建 lru_cache），之后正常
- **空间配额（512MB）易满**：跑 `~/clean_pa.sh` 清理

---

## 🔧 常用脚本

| 脚本 | 用途 |
|------|------|
| `scripts/build_final_db.py` | 从原始库构建精简库 |
| `scripts/check_db.py` | 打印两个库的状态 |
| `scripts/data_fetcher/run_all.py` | 一键拉取全流程 |
| `scripts/data_fetcher/fetch_events.py` | 拉取事件（增量回看 15 天） |
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
5. 方向判断：距离变小 → ↑；变大 → ↓
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

**定位**：本工具的回测**不是策略优化器**，而是**信号处理效果的评价器**。

---

## 🔬 策略研究模块

### 核心能力

1. **策略对比**：3 张策略卡片，每张可覆盖任意参数（含窗口类型）
   - 资金曲线对比 + 绩效散点图 + 指标对比表
   - 导出指标表 / 交易明细 CSV
2. **敏感性分析**：3 种模式
   - 单参单市场 / 双参单市场网格 / **单参多市场集合**
   - 多市场模式下：Y 轴为平均指标，辅助线为正收益市场占比
3. **批量研究**：2 种模式
   - **多事件 × 目标市场** / **单事件 × 多子市场**
   - 聚合统计 + 标签 × 策略收益热力图 + 逐条明细 DataTable
4. **实验保存/加载**：`ExperimentConfig` 序列化为 JSON

### 扩展方式

- **加参数**：`PARAM_SCHEMA` 加一条 → 面板自动出现
- **加策略**：`STRATEGY_REGISTRY` 加一条 → 下拉自动出现 → 需在 `runner.py` 里按 `strategy_id` 分发

---

## 📈 回测模块

### 执行架构

```
点击「运行回测」
    ↓
save_params                    从组件读值 → global-params（带 _trigger）
    ↓
cache_backtest_result          监听 global-params；_trigger='run' 时才跑
    ↓
backtest-result-store          结果存 store
    ↓
render_tab_content             4 个 tab 从 store 读
```

### 4 个 Tab

| Tab | 内容 |
|------|------|
| 🔍 信号预览 | 价格 + 推文 + 信号点 / 估算总量 vs 实际累计推文 |
| 📊 绩效概览 | 资金曲线（含买卖点）+ 核心绩效 8 卡片 + 盈亏细节 5 卡片 |
| 📋 交易明细 | DataTable（排序 / 分页 / 导出）+ 外置筛选 |
| 📈 策略评估 | 多窗口准确率 + 策略 vs 基线 + 交易分布直方图 + 持仓周期分桶 |

### 参数面板

- 由 `pages/shared/params_panel.py` **schema 驱动生成**
- 分四步折叠：数据选择 / 观察维度 / 信号参数 / 评价假设

---

## 🎨 UI 系统

### CSS 设计系统

`assets/style.css` 定义：

- **CSS 变量**：颜色、字号、间距、圆角、阴影
- **通用类**：`.card` / `.panel` / `.info-block` / `.kpi-card` / `.text-muted` / `.hint` 等

**用法**：
```python
html.Div("...", className="info-block")
html.Div([html.Div("总事件", className="kpi-label"),
          html.Div("42", className="kpi-value")], className="kpi-card")
```

**规则**：
- 固定样式 → `className`
- 动态样式（随数据变）→ `style`，值从 `ui/theme.py` 取

### Python 颜色常量

`ui/theme.py`：`COLOR_PRIMARY` / `COLOR_SUCCESS` / `COLOR_DANGER` 等。

**用于 Plotly 图表**（不能用 CSS）：
```python
from src.dash_app.ui.theme import COLOR_PRIMARY
line=dict(color=COLOR_PRIMARY)
```

### 表格工具

`utils/ui/table.py`：`td` / `th` / `table` 三件套，统一表头/内容居中。

---

## 🗺️ 待办清单

编号体系：P0（明显错误）、P1（体验/一致性）、P2（可延后）、P3（远期）。

### P0（已完成 ✅）

HM-3（首页缺策略研究入口）、HM-2（最后更新假数据）、PT-4（过滤条件文案不符）、PT-1（"共5个市场"写死）、IN-9（除零）、IN-8（裸 except）

### P1 —— 部分完成

| 编号 | 状态 |
|------|------|
| PT-2 X 轴时间格式 | ✅ 完成（统一 `MM-DD`） |
| PT-5 图例位置统一 | ✅ 完成 |
| IN-5 insights 卡片样式统一 | ✅ 完成 |
| HM-1 首页 KPI 响应 series | ✅ 完成 |
| IN-3 说明块抽组件 | ✅ 完成（`info_block` + CSS 类） |
| **IN-7** `update_tweet_explorer` 拆分 | 🔄 进行中 |
| **R4** 策略类型扩展 | 🔲 待做 |
| **T1** 回调风格统一 | 🔲 待做 |
| **T2** Tab 用 `dcc.Tabs` children 机制 | 🔲 待做 |
| **B3** 参数面板统一到 schema（research 侧） | 🔲 待做 |

### P2 —— 可延后

| 编号 | 问题 |
|------|------|
| PT-6 | `price_tweet_analysis` 加"导出当前数据"按钮 |
| PT-3 | `update_chart` 重复调用 `get_markets_by_event` |
| PT-7 | "±2" 硬编码，改为控件 |
| IN-1 | `insights-store` 死代码 |
| IN-4 | "最多 30 个事件"硬编码 |
| IN-6 | insights 回调没 `prevent_initial_call` |
| IN-10 | 冗余 `if not df.empty` 检查 |
| IN-11 | `go.Table` 高度硬算 |
| IN-12 | explorer 3 个回调分散 |
| HM-4 | 首页 KPI 在 layout 阶段查库 |
| T3 | `generator.py` 状态管理重构 |
| T4 | `baseline.random_signal` 公平性 |
| T7 | 研究面板懒加载 |
| T5b | 敏感性/网格分析提速 |
| E1 | 多事件聚合统计 |

### P3 —— 远期

C1（跨页带参，挂起）、R6（服务器端存储）、R7（多用户）、E2（参数寻优）、E3（实时数据）、E4（信号导出）

---

## 📝 说明

- `data/*.db` 不入 git
- `archives/` 不参与 Web
- 部署用精简库 `elon_tweets_analysis.db`（约 24 MB）
- `_test_*.py` / `_find_*.py` / `_diag*.py` 为本地调试脚本，不入 git

---

## 📌 版本状态

- **稳定可用**：观察层（`/analysis`、`/insights`）、回测模块、策略研究三 Tab、实验保存/加载
- **已知失效**：跨页带参（C1，按钮保留但无效）
- **重构重点**：观察层渐进式迁移到 CSS 设计系统；research 侧待迁移到 schema 驱动

---

## 🛠️ 运维备忘

- **PythonAnywhere 空间清理**：`bash ~/clean_pa.sh`
- **依赖版本**：
  - Python：本地 3.13 / PA 3.11（差异容忍）
  - dash：4.4.1（两端一致）
  - plotly：本地 5.24.1 / PA 6.8.0（差异容忍）
  - pandas：本地 3.0.3 / PA 2.2.2（差异容忍）
  - numpy：本地 2.4.6 / PA 2.1.0（差异容忍）
- **`requirements.txt`**：只钉 dash / plotly / openpyxl；pandas / numpy 给范围