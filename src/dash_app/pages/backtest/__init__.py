"""
预测回测系统 - 主页面
- 参数配置区 + 信号预览 + 回测结果
"""

import dash
from dash import html, dcc, Input, Output, State, callback, no_update
import plotly.graph_objects as go
import pandas as pd

from src.dash_app.pages.backtest.params_panel import create_params_panel
from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.pages.backtest.tabs.preview import render_preview_tab
from src.dash_app.pages.backtest.tabs.overview import render_overview_tab
from src.dash_app.pages.backtest.tabs.trades import render_trades_tab
from src.dash_app.pages.backtest.tabs.evaluation import render_evaluation

def layout():
    return html.Div([

        # ========== 页面标题 ==========
        html.Div([
            html.H2("📈 预测回测系统", style={'marginBottom': 2}),
            html.P("基于推文热度的方向预测与模拟交易回测",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        html.Details([
            html.Summary("📖 方向判断逻辑详解（点击展开）", style={
                'cursor': 'pointer', 'fontWeight': 'bold', 'padding': '10px 15px',
                'backgroundColor': '#e8f4fd', 'borderRadius': '6px',
                'border': '1px solid #b8d4e8', 'fontSize': '14px'
            }),
            html.Div([
                html.H5("🎯 核心思路", style={'marginTop': '10px'}),
                html.P("用「推文热度」估算市场参与度，通过「估算总量距中位数的距离变化」推断价格方向。"),
                html.P("直觉：如果推文速度在加快，说明市场热度上升，目标区间更可能被触及，价格倾向上涨。"),

                html.H5("📐 五步判断流程", style={'marginTop': '15px'}),
                html.Ol([
                    html.Li([html.Strong("估算总量"), html.Span(" = 平均推文速率 × 剩余小时数")]),
                    html.Li([html.Strong("距离"), html.Span(" = |估算总量 − 市场中位数|")]),
                    html.Li([html.Strong("容差过滤"), html.Span("：距离 ≤ 容差 → 直接判定为「看平」（→）")]),
                    html.Li([html.Strong("噪音过滤"),
                             html.Span("：距离变动 ≤ 距离阈值 且 价格变动 ≤ 价格阈值 → 不触发新信号")]),
                    html.Li([html.Strong("方向判断"), html.Span("：距离变小 → ↑；变大 → ↓；不变 → →")]),
                ]),

                html.H5("🛡️ 惯性保护", style={'marginTop': '15px'}),
                html.P("连续 ≥ 惯性小时 无有效信号 → 强制输出 →（看平），避免长期持有单一方向。"),

                html.H5("⚡ 动量修正", style={'marginTop': '15px'}),
                html.P(
                    "根据最近 6 小时推文速率变化调整估算总量。调整系数 = 1 + 动量系数 × rateChange，限制在 0.8~1.2 倍。"),

                html.H5("🎨 信号模式（仅影响图表显示）", style={'marginTop': '15px'}),
                html.Ul([
                    html.Li("full：显示每个连续段的起点和终点"),
                    html.Li("start：只显示起点（推荐）"),
                    html.Li("end：只显示终点"),
                ]),

                html.H5("📊 方向准确率", style={'marginTop': '15px'}),
                html.P("信号发出 → 到下一个反向信号出现，看这段区间内价格是否朝预测方向变化。"),
            ], style={'padding': '15px 20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '6px'})
        ], style={'marginBottom': '15px'}),

        # ========== 主布局：左侧参数 + 右侧结果 ==========
        html.Div([
            # ---- 左侧：参数面板 ----
            html.Div([
                create_params_panel()
            ], className='backtest-left', style={
                'width': '28%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'paddingRight': '20px',
                'boxSizing': 'border-box'
            }),
            # ---- 右侧：结果展示区 ----
            html.Div([
                html.Div([
                    html.H4("📊 回测结果", style={'margin': 0, 'color': '#2c3e50'}),
                    html.P(id='backtest-status-text',
                           style={'fontSize': '12px', 'color': '#7f8c8d', 'margin': '4px 0 0 0'})
                ], style={'borderBottom': '2px solid #3498db', 'paddingBottom': '10px', 'marginBottom': '15px'}),
                # ---- Tab 切换 ----
                dcc.Tabs(
                    id='backtest-tabs',
                    value='preview',
                    children=[
                        dcc.Tab(label='🔍 信号预览', value='preview'),
                        dcc.Tab(label='📊 绩效概览', value='overview'),
                        dcc.Tab(label='📋 交易明细', value='trades'),
                        dcc.Tab(label='📈 策略评估', value='evaluation'),
                    ],
                    style={'marginBottom': '15px'}
                ),
                # ---- Tab 内容（带 loading）----
                dcc.Loading(
                    id='loading-backtest',
                    type='default',  # ← 改成 default
                    color='#3498db',  # ← 蓝色
                    children=[html.Div(id='backtest-tab-content', style={'minHeight': '400px'})]
                ),
                # ---- 隐藏存储 ----
                dcc.Store(id='backtest-result-store', data={}),
                dcc.Store(id='backtest-trades-store', data=[]),
                dcc.Store(id='backtest-equity-store', data=[]),
            ], className='backtest-right', style={
                'width': '70%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'boxSizing': 'border-box'
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),

        # ========== 底部：方向判断与回测规则详解 ==========
        html.Details([
            html.Summary("📖 方向判断与回测规则详解", style={'cursor': 'pointer', 'fontWeight': 'bold', 'padding': '10px 0'}),
            html.Div([
                # ---- 方向判断逻辑 ----
                html.H5("🎯 方向判断逻辑", style={'marginTop': '5px', 'color': '#2c3e50'}),
                html.Ol([
                    html.Li([
                        html.Strong("估算总量 = 平均推文速率 × 剩余小时数"),
                        html.Br(),
                        html.Span(
                            "平均推文速率由「推文速率窗口」决定：\n"
                            "• 7天 = 最近 168 小时的滚动平均\n"
                            "• gamestart至今 = 从事件统计起点到当前的累计平均\n"
                            "• 开盘至今 = 从事件开盘到当前的累计平均\n"
                            "• 自定义 = 最近 N 小时的滚动平均",
                            style={'fontSize': '13px', 'color': '#495057'}
                        )
                    ], style={'marginBottom': '8px'}),
                    html.Li([
                        html.Strong("距离 = |估算总量 − 市场中位数|"),
                        html.Br(),
                        html.Span(
                            "中位数 =（区间下界 + 区间上界）/ 2。例如市场 180-199，中位数 = 189.5",
                            style={'fontSize': '13px', 'color': '#495057'}
                        )
                    ], style={'marginBottom': '8px'}),
                    html.Li([
                        html.Strong("容差过滤：距离 ≤ 容差 → 直接判定为「看平」（→）"),
                        html.Br(),
                        html.Span(
                            "容差越大，看平信号越多",
                            style={'fontSize': '13px', 'color': '#495057'}
                        )
                    ], style={'marginBottom': '8px'}),
                    html.Li([
                        html.Strong("噪音过滤：距离变动 ≤ 距离阈值 且 价格变动 ≤ 价格阈值 → 不触发新信号"),
                        html.Br(),
                        html.Span(
                            "两个条件同时满足才算噪音。任一超过阈值 → 触发下一步方向判断",
                            style={'fontSize': '13px', 'color': '#495057'}
                        )
                    ], style={'marginBottom': '8px'}),
                    html.Li([
                        html.Strong("方向判断：当前距离 vs 上一时刻距离"),
                        html.Br(),
                        html.Span(
                            "距离变小 → ↑（看涨）；距离变大 → ↓（看跌）；距离不变 → →（看平）",
                            style={'fontSize': '13px', 'color': '#495057'}
                        )
                    ], style={'marginBottom': '8px'}),
                ], style={'marginLeft': '0', 'paddingLeft': '20px'}),

                # ---- 惯性保护 ----
                html.H5("🛡️ 惯性保护", style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.P(
                    "连续 ≥ 惯性小时 无有效信号 → 强制输出 →（看平），避免长期持有单一方向。",
                    style={'fontSize': '13px', 'color': '#495057', 'marginLeft': '20px'}
                ),

                # ---- 动量修正 ----
                html.H5("⚡ 动量修正", style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.P(
                    "根据最近 6 小时的推文速率变化调整估算总量。调整系数 = 1 + 动量系数 × rateChange，限制在 0.8~1.2 倍。",
                    style={'fontSize': '13px', 'color': '#495057', 'marginLeft': '20px'}
                ),

                # ---- 信号模式 ----
                html.H5("🎨 信号模式", style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.P(
                    "只影响图表上箭头的显示密度，不影响回测交易。\n"
                    "• full：首尾都显示\n"
                    "• start：只显示每个连续段的起点\n"
                    "• end：只显示每个连续段的终点",
                    style={'fontSize': '13px', 'color': '#495057', 'marginLeft': '20px', 'whiteSpace': 'pre-line'}
                ),

                # ---- 回测规则 ----
                html.H5("💰 回测规则", style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.Ul([
                    html.Li("开仓：预测方向 ↑ 且当前空仓 → 以当前价格买入（固定金额 / 固定份额）"),
                    html.Li("平仓：预测方向 ↓ 且当前持仓 → 以当前价格卖出，计算盈亏"),
                    html.Li("→ 信号：不触发任何交易，维持当前状态"),
                    html.Li("强制平仓：回测结束时自动以最后价格平仓"),
                    html.Li("权益 = 现金 + 持仓市值；仅做多，不支持做空"),
                ], style={'fontSize': '13px', 'color': '#495057'}),

                # ---- 方向准确率说明 ----
                html.H5("📊 方向准确率", style={'marginTop': '15px', 'color': '#2c3e50'}),
                html.P(
                    "基于信号发出后 1 小时的价格变化判定：↑ 信号后价格涨 → 正确；↓ 信号后价格跌 → 正确。"
                    "该指标用于评估策略的短期方向判断能力。",
                    style={'fontSize': '13px', 'color': '#495057', 'marginLeft': '20px'}
                ),
            ], style={'padding': '15px 20px', 'backgroundColor': '#f8f9fa', 'borderRadius': '6px'})
        ], style={'marginTop': '20px'}),

    ], style={'padding': '10px 20px'})


# ==================== Tab 内容回调 ====================
@callback(
    Output('backtest-tab-content', 'children'),
    Output('backtest-status-text', 'children'),
    Input('backtest-tabs', 'value'),
    Input('backtest-result-store', 'data'),   # ← 改：监听 store
    Input('series-selector', 'value'),
    State('backtest-params-store', 'data'),
    State('backtest-preview-btn', 'n_clicks'),
    State('backtest-run-btn', 'n_clicks'),
)
def render_tab_content(tab_name, cached_result, series, params, preview_clicks, run_clicks):
    """根据选中的 Tab 和参数渲染内容"""

    # ===== 信号预览 Tab =====
    if tab_name == 'preview':
        if not params or not params.get('market_id'):
            status_text = "请选择事件和市场，点击「更新信号预览」"
            content, _ = render_preview_tab(params, series)
            return content, status_text

        content, stats = render_preview_tab(params, series)
        status_text = f"✅ 信号预览已更新 | 信号总数: {stats.get('total_signals', 0)} | 方向准确率: {stats.get('overall_accuracy', 0) * 100:.1f}%"
        return content, status_text

    # ===== 绩效概览 Tab =====
    elif tab_name == 'overview':
        return render_overview_tab(params, series)

    # ===== 交易明细 Tab =====
    elif tab_name == 'trades':
        return render_trades_tab(params, series)

    # ===== 策略评估 Tab =====
    elif tab_name == 'evaluation':
        if not params or not params.get('market_id'):
            return html.Div([
                html.P("📈 策略评估将在此显示",
                       style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请配置参数并点击「运行回测」",
                       style={'color': '#6c757d', 'textAlign': 'center'})
            ]), "请选择事件和市场，点击「运行回测」"

        result = run_backtest(params, series)
        if result is None:
            return html.Div([
                html.P("❌ 回测运行失败，请检查参数",
                       style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '40px 0'})
            ]), "回测运行失败"

        return render_evaluation(params, result), "✅ 策略评估已加载"


@callback(
    Output('backtest-result-store', 'data'),
    Input('backtest-params-store', 'data'),
    Input('series-selector', 'value'),
    prevent_initial_call=True,
)
def cache_backtest_result(params, series):
    """参数变化时跑一次回测，结果存入 store"""
    if not params or not params.get('market_id'):
        return {}
    result = run_backtest(params, series)
    return result if result else {}

