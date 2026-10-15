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
│   │   │   ├── layout.py         # Tab 内容内嵌 dcc.Tab children（T2）
│   │   │   ├── callbacks.py
│   │   │   ├── explorer.py       # IN-7 拆出纯计算函数
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
│   │       ├── layout.py         # Tab 内容内嵌 dcc.Tab children（T2）
│   │       ├── filter_panel.py   # @callback 自动注册（T1）
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
│       │   ├── params_schema.py  # 参数 + 指标元数据（单一数据源）
│       │   ├── strategy_config.py
│       │   ├── experiment.py
│       │   ├── storage.py
│       │   ├── serialize.py
│       │   └── batch.py
│       ├── signal/generator.py   # 方向信号生成器（核心策略逻辑）
│       ├── backtest/
│       │   ├── engine.py         # 回测引擎（模拟交易执行）
│       │   ├── runner.py         # 回测执行器（组装 prepare+generator+engine）
│       │   ├── prepare.py        # 数据准备（lru_cache）
│       │   └── baseline.py       # 基线策略（buy_and_hold）
│       ├── metrics/
│       │   ├── calculator.py     # 指标计算（独立函数）
│       │   ├── accuracy.py       # 多窗口方向准确率
│       │   └── hold_period.py
│       ├── comparison/engine.py  # 多策略对比引擎
│       └── analysis/sensitivity.py
│
└── archives/
```

---

## 📄 页面结构

| 路径 | 页面 | 功能 | Tab 机制 |
|------|------|------|----------|
| `/` | 首页 | 功能卡片 + KPI 数据概览（响应 series 切换） | — |
| `/analysis` | 价格-推文分析 | 事件内各市场价格与推文关系 | — |
| `/insights` | 数据分析中心 | 命中模式、推文热度图谱、推文探索器 | `dcc.Tab` children（T2） |
| `/backtest` | 预测回测 | 单事件信号评价 | 懒渲染（`render_tab_content` 回调按 active tab 生成） |
| `/research` | 策略研究 | 策略对比、敏感性、批量研究 | `dcc.Tab` children（T2） |

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

**本地**（代码 + 文档单笔提交，git add 用显式文件名）：
```bash
git add src/dash_app/pages/xxx.py README.md
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

## 🧠 策略逻辑简述

**方向判断**：
1. 估算总量 = 平均推文速率 × 剩余小时数
2. 距离 = |估算总量 − 市场中位数|
3. 容差过滤：距离 ≤ 容差 → 看平（→）
4. 噪音过滤：距离变动 ≤ 阈值 且 价格变动 ≤ 阈值 → 不触发新信号
5. 方向判断：距离变小 → ↑；变大 → ↓
6. 惯性保护：连续 ≥ N 小时无有效信号 → 强制看平
7. 动量修正：最近 6 小时速率变化调整估算总量（系数限制 0.8~1.2，递归累积）

**推文速率窗口**：
- `7d`：最近 168 小时滚动平均
- `gamestart`：从统计起点到当前累计平均
- `open`：从事件开盘到当前累计平均
- `自定义`：最近 N 小时滚动平均

**回测规则**：
- ↑ 信号 + 空仓 → 开仓（做多）
- ↓ 信号 + 持仓 → 平仓
- → 信号 → 不动
- 回测结束强制平仓
- 仅做多，无交易成本/滑点

**定位**：本工具的回测**不是策略优化器**，而是**信号处理效果的评价器**。

---

## 🔬 策略研究模块

### 核心能力

1. **策略对比**：3 张策略卡片，每张可覆盖任意参数（含窗口类型）
   - 资金曲线对比 + 绩效散点图 + 指标对比表
   - 导出指标表 / 交易明细 CSV
   - 一键带入信号回测（C1，当前失效，待修）
2. **敏感性分析**：3 种模式
   - 单参单市场 / 双参单市场网格 / **单参多市场集合**
   - 多市场模式下：Y 轴为平均指标，辅助线为正收益市场占比
3. **批量研究**：2 种模式
   - **多事件 × 目标市场** / **单事件 × 多子市场**
   - 聚合统计 + 标签 × 策略收益热力图 + 逐条明细 DataTable

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
render_tab_content             按 active tab 从 store 读，懒渲染（只渲染当前 tab）
```

### 4 个 Tab

| Tab | 内容 | 数据来源 |
|------|------|----------|
| 🔍 信号预览 | 价格 + 推文 + 信号点 / 估算总量 vs 实际累计推文 | 实时生成（params → generator） |
| 📊 绩效概览 | 资金曲线（含买卖点）+ 核心绩效 8 卡片 + 盈亏细节 5 卡片 | backtest-result-store |
| 📋 交易明细 | DataTable（排序 / 分页 / 导出）+ 外置筛选 | backtest-result-store |
| 📈 策略评估 | 多窗口准确率 + 策略 vs 基线 + 交易分布直方图 + 持仓周期分桶 | store + params |

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

## 🗺️ 整改路线图

> 2026-10-14 整体审计后重构。编号：C=跨页/闭环、F=金融逻辑、S=结构债、E=功能增强，前缀数字代表批次。

### 已完成 ✅

| 编号 | 内容 |
|------|------|
| P0 六项 | HM-3 / HM-2 / PT-4 / PT-1 / IN-9 / IN-8 |
| P1 前六项 | PT-2 X轴时间 / PT-5 图例位置 / IN-5 卡片统一 / HM-1 KPI响应series / IN-3 说明块抽组件 |
| IN-7 | `update_tweet_explorer` 拆出 `_resolve_range` + `_compute_stats` 纯函数 |
| T1 | 全仓回调统一 `@callback` 自动注册，删 `register_callbacks` 手动链 |
| T2 | insights/research Tab 改用 `dcc.Tab` children 机制，删 style-toggle 回调 |
| C1 | 跨页带参修复：两段式回调 + `refresh=True` 整页刷新 + `storage_type='session'` 持久化 |
| F1 | Sharpe 去年化：去掉 `sqrt(252*24)` 年化因子，返回周期内原始 mean/std |
| S4 | equity_curve Timestamp 序列化：经验证 Dash PlotlyJSONEncoder 已自动处理，非真实问题 |

### 第一批：核心闭环 + 高风险 ✅ 已完成

| 编号 | 问题 | 修法 | 结果 |
|------|------|------|------|
| C1 | 跨页带参失效 | 两段式回调 + refresh + session 存储 | 研究→回测闭环跑通 |
| F1 | Sharpe 年化虚高 | 去掉 `sqrt(252*24)` 年化因子 | Sharpe 从 5.29 → 0.068（周期内原始值） |
| S4 | equity_curve Timestamp 序列化风险 | 验证后确认非问题 | Dash 编码器自动转 ISO 字符串 |

### 第二批：一致性 + 指标补全 🟡

| 编号 | 问题 | 修法 |
|------|------|------|
| **S1** | metrics 两套实现：`BacktestEngine._calculate_metrics` vs `calculator.py`，Sharpe 口径不同 | 统一到 `calculator.py`，engine 只调它 ✅已统一 |
| **F3** | 方向准确率不看幅度：价格涨 0.001 跟涨 0.05 都算"正确" | 每窗口加对时均幅/错时均幅/每信号期望 ✅已完成（选幅度方案，弃加权） |
| **E3** | 策略对比曲线/散点重合时不可见 | 重合检测 + 黄色提示条 + 重合曲线虚线区分 ✅已完成 |
| **E1** | 缺 Sortino / Calmar / Exposure 指标 | ⏸️ 暂缓（2026-10-15 用户决定不做：calculator 已补算但 overview 白名单不展示，直接移除） |
| **F4** | explorer 三个"平均"口径不一致（旧 IN-13） | 统一活跃口径（平均/小时=活跃总数/活跃格数）+ Total行末格改日均 + 说明标注 ✅已完成 |
| **F2** | 无交易成本/滑点，回测收益偏乐观 | 概览卡片下加口径提示条 ✅已完成（选标注方案；不加费率参数——Polymarket 零手续费，硬编码费率会假精确） |

### 第三批：清理 + 功能扩展 🟢

| 编号 | 问题 | 修法 |
|------|------|------|
| **S2** | `insights-store` 死代码（旧 IN-1） | 删 |
| **S3** | `save_params` 新旧 ctx 风格混用 | 统一 `ctx.triggered_id` |
| **S5** | `backtest/callbacks.py` 残留 `import dash` | 换 `from dash import ctx` |
| **S6** | 信号生成器状态是实例变量（旧 T3），`_determine_signal` 里 prev_distance 冗余更新 | 改局部变量或 dataclass |
| **E4** | 只有 direction_signal 一种策略，buy_hold/reverse_signal 注释掉了（旧 T4+R4） | 实现 buy_hold 基线，评价信号 alpha |
| **B3** | research 参数面板未统一到 schema | 迁移 |
| **F5** | 动量修正是递归累积，代码注释说"设计意图" | 确认是否合理，加开关 |
| **F6** | 命中阈值 0.99 硬编码（旧 IN-4 同类） | 参数化 |

### 保留项（旧 P2/P3 未重新编号）

| 旧编号 | 问题 |
|--------|------|
| PT-6 | `price_tweet_analysis` 加"导出当前数据"按钮 |
| PT-3 | `update_chart` 重复调用 `get_markets_by_event` |
| PT-7 | "±2" 硬编码，改为控件 |
| IN-6 | insights 回调没 `prevent_initial_call` |
| IN-10 | 冗余 `if not df.empty` 检查 |
| IN-11 | `go.Table` 高度硬算 |
| IN-12 | explorer 3 个回调分散 |
| HM-4 | 首页 KPI 在 layout 阶段查库 |
| T7 | 研究面板懒加载 |
| T5b | 敏感性/网格分析提速 |
| R6 / R7 | 服务器端存储 / 多用户（远期） |
| E2 / E3-old / E4-old | 参数寻优 / 实时数据 / 信号导出（远期） |

---

## ⚠️ 已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| `research-params-store` State 跨页告警 | 在 /backtest 页时 console 出现 nonexistent object 警告 | 无害（suppress_callback_exceptions 未完全吞 State 校验），不影响功能 |
| Sharpe 为周期内值非年化值 | 数字偏小（如 0.07），不能与传统年化 Sharpe（1~3）直接比 | 设计如此：7 天数据不该年化，衡量的是回测期内每小时信噪比 |

---

## 📝 说明

- `data/*.db` 不入 git
- `archives/` 不参与 Web
- 部署用精简库 `elon_tweets_analysis.db`（约 24 MB）
- `_test_*.py` / `_find_*.py` / `_diag*.py` 为本地调试脚本，不入 git

---

## 📌 版本状态

- **稳定可用**：观察层（`/`、`/analysis`、`/insights`）、回测模块、策略研究三 Tab、跨页带参闭环（C1 已修）
- **审计整改**：第一批（C1/F1/S4）、第二批（S1/F3/E3/E1/F4/F2，其中 E1 暂缓）全部完成；第三批待做（详见整改路线图）

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
