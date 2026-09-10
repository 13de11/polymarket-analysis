"""
预测回测系统 - 主页面
- 参数配置区 + 信号预览 + 回测结果
"""

import dash
from dash import html, dcc, Input, Output, State, callback
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Dict, Any
import pandas as pd
import numpy as np

from src.dash_app.components.params_panel import create_params_panel, register_params_callbacks
from src.dash_app.utils.data_loader import (
    get_price_data_for_market,
    get_tweet_data_for_event,
    get_event_remaining_hours,
    get_market_median,
    get_event_time_range,
    get_event_gamestart_label,
)
from src.dash_app.utils.signal.generator import DirectionSignalGenerator
from src.dash_app.utils.backtest.engine import BacktestEngine
from src.dash_app.utils.metrics.calculator import calculate_metrics_from_trades, format_metrics_for_display
from src.dash_app.utils.strategy.registry import StrategyRegistry
from src.dash_app.utils.comparison.engine import ComparisonEngine

def layout():
    return html.Div([

        # ========== 页面标题 ==========
        html.Div([
            html.H2("📈 预测回测系统", style={'marginBottom': 2}),
            html.P("基于推文热度的方向预测与模拟交易回测",
                   style={'color': '#6c757d', 'fontSize': '14px', 'marginTop': 0}),
        ], style={'marginBottom': 15}),

        # ========== 参数说明（可折叠） ==========
        html.Details([
            html.Summary("📖 参数说明（点击展开）", style={
                'cursor': 'pointer',
                'fontWeight': 'bold',
                'padding': '8px 12px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '6px',
                'border': '1px solid #e9ecef'
            }),
            html.Div([
                html.Div([
                    html.H5("📊 数据选择", style={'margin': '10px 0 5px 0'}),
                    html.Table([
                        html.Tr([html.Th("参数", style={'textAlign': 'left', 'padding': '4px 12px'}),
                                 html.Th("含义", style={'textAlign': 'left', 'padding': '4px 12px'})]),
                        html.Tr([html.Td("事件", style={'padding': '4px 12px'}),
                                 html.Td("选择要分析的具体预测事件", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("目标市场", style={'padding': '4px 12px'}),
                                 html.Td("选择特定的推文区间市场，决定中位数锚点", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("价格类型", style={'padding': '4px 12px'}),
                                 html.Td("last=最新价，avg=均价，用于价格曲线和ΔP计算", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("推文速率窗口", style={'padding': '4px 12px'}),
                                 html.Td("计算平均推文速率时回溯的小时数", style={'padding': '4px 12px'})]),
                    ], style={'borderCollapse': 'collapse', 'width': '100%'}),
                ]),
                html.Div([
                    html.H5("🧠 策略参数", style={'margin': '10px 0 5px 0'}),
                    html.Table([
                        html.Tr([html.Th("参数", style={'textAlign': 'left', 'padding': '4px 12px'}),
                                 html.Th("含义", style={'textAlign': 'left', 'padding': '4px 12px'}),
                                 html.Th("计算逻辑", style={'textAlign': 'left', 'padding': '4px 12px'})]),
                        html.Tr([html.Td("容差", style={'padding': '4px 12px'}),
                                 html.Td("判断'看平'的距离阈值", style={'padding': '4px 12px'}),
                                 html.Td("distCur ≤ 容差 → →（看平）", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("价格变动阈值", style={'padding': '4px 12px'}),
                                 html.Td("价格噪音过滤", style={'padding': '4px 12px'}),
                                 html.Td("ΔP ≤ 阈值 → 不触发新信号", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("距离变动阈值", style={'padding': '4px 12px'}),
                                 html.Td("距离噪音过滤", style={'padding': '4px 12px'}),
                                 html.Td("ΔD ≤ 阈值 → 不触发新信号", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("惯性重置", style={'padding': '4px 12px'}),
                                 html.Td("信号漂移保护", style={'padding': '4px 12px'}),
                                 html.Td("连续无有效信号 ≥ 惯性小时 → 强制输出 →", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("动量修正", style={'padding': '4px 12px'}),
                                 html.Td("推文速率变化的自适应调整", style={'padding': '4px 12px'}),
                                 html.Td("调整系数 = 1 + 系数 × rateChange，限制 0.8~1.2", style={'padding': '4px 12px'})]),
                    ], style={'borderCollapse': 'collapse', 'width': '100%'}),
                ]),
                html.Div([
                    html.H5("🎨 信号展示", style={'margin': '10px 0 5px 0'}),
                    html.Table([
                        html.Tr([html.Th("参数", style={'textAlign': 'left', 'padding': '4px 12px'}),
                                 html.Th("含义", style={'textAlign': 'left', 'padding': '4px 12px'})]),
                        html.Tr([html.Td("信号模式", style={'padding': '4px 12px'}),
                                 html.Td("首尾/只首/只尾，仅影响图表显示密度", style={'padding': '4px 12px'})]),
                        html.Tr([html.Td("信号确认次数", style={'padding': '4px 12px'}),
                                 html.Td("信号需连续出现 N 次才生效，减少假信号", style={'padding': '4px 12px'})]),
                    ], style={'borderCollapse': 'collapse', 'width': '100%'}),
                ]),
                html.Div([
                    html.H5("📈 方向判断逻辑", style={'margin': '10px 0 5px 0'}),
                    html.Ul([
                        html.Li("① 距离计算：distance = |估算总量 - 中位数|"),
                        html.Li("② 容差过滤：distance ≤ 容差 → →（看平）"),
                        html.Li("③ 方向判断：distance < prevDistance → ↑（看涨），> → ↓（看跌）"),
                        html.Li("④ 噪声过滤：ΔP ≤ 价格阈值 且 ΔD ≤ 距离阈值 → 不触发新信号"),
                        html.Li("⑤ 惯性重置：连续无有效信号 ≥ 惯性小时 → 强制输出 →"),
                    ], style={'margin': '4px 0'})
                ]),
            ], style={'padding': '10px 15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '6px'}),
        ], style={'marginBottom': '15px'}),

        # ========== 主布局：左侧参数 + 右侧结果 ==========
        html.Div([
            # ---- 左侧：参数面板 ----
            html.Div([
                create_params_panel()
            ], style={
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
                        dcc.Tab(label='📊 策略对比', value='comparison'),
                        dcc.Tab(label='📊 敏感性分析', value='sensitivity'),
                    ],
                    style={'marginBottom': '15px'}
                ),
                # ---- Tab 内容 ----
                html.Div(id='backtest-tab-content', style={'minHeight': '400px'}),
                # ---- 隐藏存储 ----
                dcc.Store(id='backtest-result-store', data={}),
                dcc.Store(id='backtest-trades-store', data=[]),
                dcc.Store(id='backtest-equity-store', data=[]),
            ], style={
                'width': '70%',
                'display': 'inline-block',
                'verticalAlign': 'top',
                'boxSizing': 'border-box'
            }),
        ], style={'display': 'flex', 'flexWrap': 'wrap'}),

        # ========== 底部：回测规则说明 ==========
        html.Details([
            html.Summary("📖 回测规则说明", style={'cursor': 'pointer', 'fontWeight': 'bold', 'padding': '10px 0'}),
            html.Div([
                html.Ul([
                    html.Li("开仓：预测方向 ↑ 时，以当前价格买入固定金额（默认 $10）"),
                    html.Li("平仓：预测方向 ↓ 时，以当前价格卖出，计算盈亏"),
                    html.Li("→ 信号：不触发任何交易，维持当前状态"),
                    html.Li("强制平仓：回测区间结束或事件结束时，自动以最后价格平仓"),
                    html.Li("权益计算：权益 = 现金余额 + 持仓市值"),
                    html.Li("仅支持做多，不支持做空"),
                ], style={'margin': '8px 0'})
            ], style={'padding': '10px 15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '6px'})
        ], style={'marginTop': '20px'}),

    ], style={'padding': '10px 20px'})


# ==================== Tab 内容回调 ====================
@callback(
    Output('backtest-tab-content', 'children'),
    Output('backtest-status-text', 'children'),
    Input('backtest-tabs', 'value'),
    Input('backtest-params-store', 'data'),
    Input('series-selector', 'value'),  # ← 新增这一行
    State('backtest-preview-btn', 'n_clicks'),
    State('backtest-run-btn', 'n_clicks'),
)
def render_tab_content(tab_name, params, series, preview_clicks, run_clicks):  # ← 新增 series 参数
    """根据选中的 Tab 和参数渲染内容"""

    # ===== 信号预览 Tab =====
    if tab_name == 'preview':
        if not params or not params.get('market_id'):
            status_text = "请选择事件和市场，点击「更新信号预览」"
            return html.Div([
                html.P("📊 信号预览图将在此显示",
                       style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请选择事件和市场，点击「更新信号预览」", style={'color': '#6c757d', 'textAlign': 'center'})
            ]), status_text

        # 生成信号预览图
        fig, stats = generate_signal_preview(params, series)  # ← 传入 series
        stats_cards = stats.get('_cards', html.Div("无统计数据"))
        status_text = f"✅ 信号预览已更新 | 信号总数: {stats.get('total_signals', 0)} | 方向准确率: {stats.get('overall_accuracy', 0) * 100:.1f}%"
        return html.Div([
            dcc.Graph(figure=fig, style={'height': '500px'}),
            html.Div(stats_cards, style={
                'display': 'flex',
                'flexWrap': 'wrap',
                'gap': '15px',
                'padding': '15px',
                'backgroundColor': '#f8f9fa',
                'borderRadius': '6px',
                'marginTop': '15px'
            })
        ]), status_text

    # ===== 绩效概览 Tab =====
    elif tab_name == 'overview':
        if not params or not params.get('market_id'):
            return html.Div([
                html.P("📊 绩效指标将在此显示", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请配置参数并点击「运行回测」", style={'color': '#6c757d', 'textAlign': 'center'})
            ]), "请选择事件和市场，点击「运行回测」"

        # 运行回测
        result = run_backtest(params, series)  # ← 传入 series
        if result is None:
            return html.Div([
                html.P("❌ 回测运行失败，请检查参数",
                       style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '40px 0'})
            ]), "回测运行失败"

        metrics = result.get('metrics', {})
        equity_curve = result.get('equity_curve', [])

        # 构建绩效卡片
        formatted = format_metrics_for_display(metrics)

        # 核心指标卡片
        core_metrics = ['最终权益', '总收益率', '总交易次数', '胜率', '盈亏比', '最大回撤', '夏普比率', '平均持仓']
        cards = []
        for key in core_metrics:
            if key in formatted:
                cards.append(html.Div([
                    html.Div(key, style={'fontSize': '12px', 'color': '#7f8c8d'}),
                    html.Div(formatted[key], style={'fontSize': '20px', 'fontWeight': 'bold'})
                ], style={'textAlign': 'center', 'minWidth': '80px', 'padding': '8px 12px',
                          'backgroundColor': '#f8f9fa', 'borderRadius': '6px'}))

        # 资金曲线图
        if equity_curve:
            fig_equity = create_equity_curve_chart(equity_curve)
        else:
            fig_equity = go.Figure()

        return html.Div([
            html.Div([
                html.H5("📈 资金曲线", style={'margin': '10px 0'}),
                dcc.Graph(figure=fig_equity, style={'height': '300px'})
            ]),
            html.H5("📊 绩效指标", style={'margin': '15px 0 10px 0'}),
            html.Div(cards, style={
                'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px', 'justifyContent': 'center'
            }),
        ]), f"✅ 回测完成 | 总交易: {metrics.get('total_trades', 0)} | 胜率: {metrics.get('win_rate', 0):.1f}% | 总收益: {metrics.get('total_return', 0):.2f}%"

    # ===== 交易明细 Tab =====
    elif tab_name == 'trades':
        if not params or not params.get('market_id'):
            return html.Div([
                html.P("📋 交易明细将在此显示", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请配置参数并点击「运行回测」", style={'color': '#6c757d', 'textAlign': 'center'})
            ]), "请选择事件和市场，点击「运行回测」"

        result = run_backtest(params)
        if result is None:
            return html.Div([
                html.P("❌ 回测运行失败，请检查参数",
                       style={'color': '#e74c3c', 'textAlign': 'center', 'padding': '40px 0'})
            ]), "回测运行失败"

        trades = result.get('trades', [])
        completed_trades = [t for t in trades if t.get('result') != 'pending']

        if not completed_trades:
            return html.Div([
                html.P("📋 暂无交易记录", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'})
            ]), "暂无交易记录"

        # 构建交易明细表
        table_rows = []
        for t in completed_trades:
            result_color = '#28a745' if t.get('result') == '盈利' else '#e74c3c' if t.get(
                'result') == '亏损' else '#f39c12'
            entry_time = t.get('entry_time', '')
            exit_time = t.get('exit_time', '')
            if hasattr(entry_time, 'strftime'):
                entry_time = entry_time.strftime('%Y-%m-%d %H:%M')
            if hasattr(exit_time, 'strftime'):
                exit_time = exit_time.strftime('%Y-%m-%d %H:%M')
            table_rows.append(html.Tr([
                html.Td(str(t.get('trade_id', ''))),
                html.Td(entry_time),
                html.Td(exit_time),
                html.Td(f"{t.get('entry_price', 0):.4f}"),
                html.Td(f"{t.get('exit_price', 0):.4f}"),
                html.Td(f"${t.get('profit', 0):.2f}"),
                html.Td(f"{t.get('profit_pct', 0):.2f}%"),
                html.Td(f"{t.get('hold_hours', 0):.1f}h" if t.get('hold_hours') else ''),
                html.Td(t.get('result', ''), style={'color': result_color, 'fontWeight': 'bold'}),
            ]))

        return html.Div([
            html.H5("📋 交易明细", style={'margin': '10px 0'}),
            html.Div([
                html.Table([
                    html.Thead(html.Tr([
                        html.Th('#'), html.Th('开仓时间'), html.Th('平仓时间'),
                        html.Th('开仓价'), html.Th('平仓价'), html.Th('盈亏($)'),
                        html.Th('盈亏(%)'), html.Th('持仓时间'), html.Th('结果')
                    ])),
                    html.Tbody(table_rows)
                ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})
            ], style={'overflowX': 'auto', 'maxHeight': '400px', 'overflowY': 'auto'})
        ]), f"✅ 共 {len(completed_trades)} 笔交易"

    # ===== 策略对比 Tab =====
    elif tab_name == 'comparison':
        if not params or not params.get('market_id'):
            return html.Div([
                html.P("📊 策略对比将在此显示", style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请选择事件和市场，配置对比策略", style={'color': '#6c757d', 'textAlign': 'center'})
            ]), "请选择事件和市场"

        # 构建策略选项（预设参数变体）
        strategy_options = [
            {'label': '方向信号 (阈值0.005)', 'value': 'dir_005'},
            {'label': '方向信号 (阈值0.01)', 'value': 'dir_01'},
            {'label': '方向信号 (阈值0.015)', 'value': 'dir_015'},
        ]

        return html.Div([
            html.H5("📊 策略对比", style={'margin': '10px 0'}),
            html.Div([
                html.P("选择要对比的策略（最多3个）：", style={'fontSize': '14px'}),
                html.Div([
                    html.Div([
                        html.Label("策略A:", style={'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='comparison-strategy-a',
                            options=strategy_options,
                            value='dir_005',
                            style={'width': '100%'}
                        ),
                    ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                    html.Div([
                        html.Label("策略B:", style={'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='comparison-strategy-b',
                            options=strategy_options,
                            value='dir_01',
                            style={'width': '100%'}
                        ),
                    ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                    html.Div([
                        html.Label("策略C (可选):", style={'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='comparison-strategy-c',
                            options=[{'label': '无', 'value': None}] + strategy_options,
                            value=None,
                            style={'width': '100%'}
                        ),
                    ], style={'width': '30%', 'display': 'inline-block'}),
                ], style={'marginBottom': '15px'}),
                html.Button(
                    '🚀 运行对比',
                    id='comparison-run-btn',
                    n_clicks=0,
                    style={
                        'padding': '10px 20px',
                        'backgroundColor': '#6c5ce7',
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '6px',
                        'fontSize': '14px',
                        'fontWeight': 'bold',
                        'cursor': 'pointer'
                    }
                ),
            ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),
            html.Div(id='comparison-results', style={'marginTop': '15px'}),
        ]), "配置策略后点击「运行对比」"

    elif tab_name == 'sensitivity':
        if not params or not params.get('market_id'):
            return html.Div([
                html.P("📊 参数敏感性分析将在此显示",
                       style={'color': '#6c757d', 'textAlign': 'center', 'padding': '40px 0'}),
                html.P("请选择事件和市场，配置分析参数", style={'color': '#6c757d', 'textAlign': 'center'})
            ]), "请选择事件和市场"

        return html.Div([
            html.H5("📊 参数敏感性分析", style={'margin': '10px 0'}),
            html.Div([
                html.P("分析参数变化对回测结果的影响：", style={'fontSize': '14px'}),
                html.Div([
                    html.Div([
                        html.Label("分析参数:", style={'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='sensitivity-param',
                            options=[
                                {'label': '价格阈值 (price_threshold)', 'value': 'price_threshold'},
                                {'label': '容差 (capacity)', 'value': 'capacity'},
                                {'label': '距离阈值 (distance_threshold)', 'value': 'distance_threshold'},
                                {'label': '惯性 (inertia)', 'value': 'inertia'},
                                {'label': '动量系数 (momentum_coef)', 'value': 'momentum_coef'},
                            ],
                            value='price_threshold',
                            style={'width': '100%'}
                        ),
                    ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                    html.Div([
                        html.Label("追踪指标:", style={'fontWeight': 'bold'}),
                        dcc.Dropdown(
                            id='sensitivity-metric',
                            options=[
                                {'label': '总收益率', 'value': 'total_return'},
                                {'label': '夏普比率', 'value': 'sharpe_ratio'},
                                {'label': '胜率', 'value': 'win_rate'},
                                {'label': '最大回撤', 'value': 'max_drawdown_pct'},
                            ],
                            value='total_return',
                            style={'width': '100%'}
                        ),
                    ], style={'width': '30%', 'display': 'inline-block', 'paddingRight': '10px'}),
                    html.Div([
                        html.Label("参数范围:", style={'fontWeight': 'bold'}),
                        html.Div([
                            dcc.Input(
                                id='sensitivity-min',
                                type='number',
                                value=0.001,
                                step=0.001,
                                style={'width': '40%', 'display': 'inline-block', 'marginRight': '5px'}
                            ),
                            dcc.Input(
                                id='sensitivity-max',
                                type='number',
                                value=0.02,
                                step=0.001,
                                style={'width': '40%', 'display': 'inline-block'}
                            ),
                        ]),
                        html.P("步长: 自动计算 (10个点)",
                               style={'fontSize': '12px', 'color': '#6c757d', 'margin': '4px 0 0 0'})
                    ], style={'width': '30%', 'display': 'inline-block'}),
                ], style={'marginBottom': '15px'}),
                html.Button(
                    '🔬 运行分析',
                    id='sensitivity-run-btn',
                    n_clicks=0,
                    style={
                        'padding': '10px 20px',
                        'backgroundColor': '#00b894',
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '6px',
                        'fontSize': '14px',
                        'fontWeight': 'bold',
                        'cursor': 'pointer'
                    }
                ),
            ], style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderRadius': '8px'}),
            html.Div(id='sensitivity-results', style={'marginTop': '15px'}),
        ]), "配置参数后点击「运行分析」"

    # 默认情况（不应该发生）
    return html.Div(), ""



# ==================== 信号预览生成函数 ====================
def generate_signal_preview(params, series='7d'):  # ← 新增 series 参数（暂不使用）
    """生成信号预览图表和统计"""
    market_id = params.get('market_id')
    price_type = params.get('price_type', 'price_last')
    window_hours = params.get('window_hours', 168)
    event_id = params.get('event_id')

    # 获取价格数据
    price_df = get_price_data_for_market(market_id)
    if price_df.empty:
        return go.Figure(), {'total_signals': 0}

    # 获取推文数据
    tweet_df = get_tweet_data_for_event(event_id)

    # 合并数据
    combined = pd.merge(price_df, tweet_df, on='datetime_utc', how='left')
    combined['tweet_count'] = combined['tweet_count'].fillna(0)
    combined = combined.sort_values('datetime_utc').reset_index(drop=True)

    # ===== 区间过滤（使用 hour_start_utc 避免时区问题） =====
    backtest_range = params.get('backtest_range', 'full')
    if backtest_range in ['pre', 'post']:
        gamestart_label = get_event_gamestart_label(event_id)
        if gamestart_label:
            # 将 gamestart_label 转换为 UTC 时间戳（整数）
            gamestart_dt = pd.to_datetime(gamestart_label, utc=True)
            gamestart_ts = int(gamestart_dt.timestamp())
            if backtest_range == 'pre':
                combined = combined[combined['hour_start_utc'] < gamestart_ts]
            else:  # post
                combined = combined[combined['hour_start_utc'] >= gamestart_ts]
            if combined.empty:
                return go.Figure(), {'total_signals': 0}
    # ===== 区间过滤结束 =====

    if len(combined) < 10:
        return go.Figure(), {'total_signals': 0}

    # 获取中位数和剩余小时数
    median = get_market_median(market_id)
    remaining_hours = get_event_remaining_hours(event_id)

    # 信号生成
    signal_params = {
        'capacity': params.get('capacity', 0),
        'price_threshold': params.get('price_threshold', 0.005),
        'distance_threshold': params.get('distance_threshold', 1.5),
        'inertia_hours': params.get('inertia', 6),
        'momentum_enable': params.get('momentum_enable', True),
        'momentum_coef': params.get('momentum_coef', 0.10),
        'signal_mode': params.get('signal_mode', 'full'),
        'median': median,
        'remaining_hours': remaining_hours,
    }

    generator = DirectionSignalGenerator(signal_params)
    price_col = price_type
    price_df_renamed = combined[['datetime_utc', price_col]].rename(
        columns={'datetime_utc': 'timestamp', price_col: 'price'}
    )
    tweet_df_renamed = combined[['datetime_utc', 'tweet_count']].rename(
        columns={'datetime_utc': 'timestamp'}
    )
    signal_df = generator.generate_signals(price_df_renamed, tweet_df_renamed, window_hours)

    # 信号统计
    stats = generator.get_signal_stats(signal_df)

    # ---- 构建图表 ----
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        row_heights=[0.7, 0.3],
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]]
    )

    # 价格曲线
    fig.add_trace(
        go.Scatter(
            x=signal_df['timestamp'],
            y=signal_df['price'],
            name='目标价格',
            line=dict(color='#e74c3c', width=2),
            hovertemplate='价格: %{y:.4f}<extra></extra>'
        ),
        row=1, col=1, secondary_y=False
    )

    # 推文柱状图
    fig.add_trace(
        go.Bar(
            x=signal_df['timestamp'],
            y=signal_df['tweet_count'],
            name='推文数',
            marker=dict(color='rgba(255, 100, 50, 0.3)'),
            yaxis='y2',
            hovertemplate='推文: %{y}<extra></extra>'
        ),
        row=1, col=1, secondary_y=True
    )

    # ---- 信号箭头 ----
    for idx, row in signal_df.iterrows():
        signal = row['signal']
        if signal in ['↑', '↓', '→']:
            color = '#2ecc71' if signal == '↑' else '#e74c3c' if signal == '↓' else '#95a5a6'
            symbol = '▲' if signal == '↑' else '▼' if signal == '↓' else '●'
            fig.add_annotation(
                x=row['timestamp'],
                y=row['price'],
                text=symbol,
                showarrow=False,
                font=dict(size=15, color=color),
                row=1, col=1,
                yshift=10 if signal == '↑' else -10 if signal == '↓' else 0
            )

    # ---- 权益曲线（预览模式简化） ----
    if len(signal_df) > 0:
        equity = 100 + (signal_df['price'] / signal_df['price'].iloc[0] - 1) * 100
        fig.add_trace(
            go.Scatter(
                x=signal_df['timestamp'],
                y=equity,
                name='权益曲线(模拟)',
                line=dict(color='#2c3e50', width=2),
                hovertemplate='权益: %{y:.2f}<extra></extra>'
            ),
            row=2, col=1
        )
        max_equity = equity.cummax()
        drawdown = (equity - max_equity) / max_equity * 100
        fig.add_trace(
            go.Scatter(
                x=signal_df['timestamp'],
                y=drawdown,
                name='回撤%',
                fill='tozeroy',
                line=dict(color='rgba(231, 76, 60, 0.5)', width=1),
                hovertemplate='回撤: %{y:.2f}%<extra></extra>'
            ),
            row=2, col=1
        )

    fig.update_layout(
        title=dict(text="信号预览 - 价格 + 推文 + 方向信号", font=dict(size=14)),
        legend=dict(orientation='h', yanchor='top', y=1.02, xanchor='center', x=0.5),
        hovermode='x unified',
        height=600,
        margin=dict(l=50, r=50, t=60, b=50)
    )
    fig.update_xaxes(title_text="", row=1, col=1)
    fig.update_xaxes(title_text="时间", row=2, col=1)
    fig.update_yaxes(title_text="价格", secondary_y=False, row=1, col=1)
    fig.update_yaxes(title_text="推文数", secondary_y=True, row=1, col=1)
    fig.update_yaxes(title_text="权益", row=2, col=1)

    # ---- 统计卡片 ----
    stats_cards = html.Div([
        html.Div([
            html.Strong("📊 信号总数"),
            html.Div(str(stats.get('total_signals', 0)), style={'fontSize': '20px', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("▲ 看涨"),
            html.Div(str(stats.get('up_count', 0)), style={'fontSize': '20px', 'color': '#2ecc71', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("▼ 看跌"),
            html.Div(str(stats.get('down_count', 0)), style={'fontSize': '20px', 'color': '#e74c3c', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("➔ 看平"),
            html.Div(str(stats.get('flat_count', 0)), style={'fontSize': '20px', 'color': '#95a5a6', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '80px'}),
        html.Div([
            html.Strong("🎯 方向准确率"),
            html.Div(f"{stats.get('overall_accuracy', 0)*100:.1f}%", style={'fontSize': '20px', 'color': '#3498db', 'fontWeight': 'bold'})
        ], style={'textAlign': 'center', 'minWidth': '120px'}),
        html.Div([
            html.Strong("▲ 上涨准确率"),
            html.Div(f"{stats.get('up_accuracy', 0)*100:.1f}%", style={'fontSize': '16px', 'color': '#2ecc71'})
        ], style={'textAlign': 'center', 'minWidth': '100px'}),
        html.Div([
            html.Strong("▼ 下跌准确率"),
            html.Div(f"{stats.get('down_accuracy', 0)*100:.1f}%", style={'fontSize': '16px', 'color': '#e74c3c'})
        ], style={'textAlign': 'center', 'minWidth': '100px'}),
    ], style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '20px', 'justifyContent': 'center'})

    stats['_cards'] = stats_cards
    return fig, stats



# ==================== 回测执行函数 ====================

def run_backtest(params: dict, series='7d'):  # ← 新增 series 参数（暂不使用）
    """执行回测"""
    try:
        market_id = params.get('market_id')
        price_type = params.get('price_type', 'price_last')
        window_hours = params.get('window_hours', 168)
        event_id = params.get('event_id')

        price_df = get_price_data_for_market(market_id)
        if price_df.empty:
            return None

        tweet_df = get_tweet_data_for_event(event_id)

        combined = pd.merge(price_df, tweet_df, on='datetime_utc', how='left')
        combined['tweet_count'] = combined['tweet_count'].fillna(0)
        combined = combined.sort_values('datetime_utc').reset_index(drop=True)

        # ===== 区间过滤（使用 hour_start_utc） =====
        backtest_range = params.get('backtest_range', 'full')
        if backtest_range in ['pre', 'post']:
            gamestart_label = get_event_gamestart_label(event_id)
            if gamestart_label:
                gamestart_dt = pd.to_datetime(gamestart_label, utc=True)
                gamestart_ts = int(gamestart_dt.timestamp())
                if backtest_range == 'pre':
                    combined = combined[combined['hour_start_utc'] < gamestart_ts]
                else:  # post
                    combined = combined[combined['hour_start_utc'] >= gamestart_ts]
                if combined.empty:
                    return None
        # ===== 区间过滤结束 =====

        if len(combined) < 10:
            return None

        median = get_market_median(market_id)
        remaining_hours = get_event_remaining_hours(event_id)

        signal_params = {
            'capacity': params.get('capacity', 0),
            'price_threshold': params.get('price_threshold', 0.005),
            'distance_threshold': params.get('distance_threshold', 1.5),
            'inertia_hours': params.get('inertia', 6),
            'momentum_enable': params.get('momentum_enable', True),
            'momentum_coef': params.get('momentum_coef', 0.10),
            'signal_mode': 'full',
            'median': median,
            'remaining_hours': remaining_hours,
        }

        generator = DirectionSignalGenerator(signal_params)
        price_col = price_type
        price_df_renamed = combined[['datetime_utc', price_col]].rename(
            columns={'datetime_utc': 'timestamp', price_col: 'price'}
        )
        tweet_df_renamed = combined[['datetime_utc', 'tweet_count']].rename(
            columns={'datetime_utc': 'timestamp'}
        )
        signal_df = generator.generate_signals(price_df_renamed, tweet_df_renamed, window_hours)

        if signal_df.empty:
            return None

        engine = BacktestEngine(
            initial_capital=params.get('initial_capital', 100),
            position_mode=params.get('position_mode', 'fixed_amount'),
            position_size=params.get('position_size', 10),
        )
        result = engine.run(signal_df, price_col='price')
        return result

    except Exception as e:
        print(f"回测错误: {e}")
        import traceback
        traceback.print_exc()
        return None


def create_equity_curve_chart(equity_curve: list) -> go.Figure:
    """创建资金曲线图"""
    if not equity_curve:
        return go.Figure()

    df = pd.DataFrame(equity_curve)
    if df.empty:
        return go.Figure()

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['equity'],
        name='权益曲线',
        line=dict(color='#2c3e50', width=2),
        fill='tozeroy',
        fillcolor='rgba(44, 62, 80, 0.1)'
    ))

    if not df.empty:
        initial = df['equity'].iloc[0]
        fig.add_hline(y=initial, line_dash="dash", line_color="gray", annotation_text="初始资金")

    fig.update_layout(
        title='资金曲线',
        xaxis_title='时间',
        yaxis_title='权益 ($)',
        hovermode='x',
        height=300,
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

# ==================== 策略对比辅助函数 ====================

def create_comparison_chart(results: Dict[str, Any]) -> go.Figure:
    """创建资金曲线对比图"""
    fig = go.Figure()
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6']

    for i, (name, data) in enumerate(results.items()):
        equity_curve = data.get('equity_curve', [])
        if equity_curve:
            df = pd.DataFrame(equity_curve)
            if not df.empty:
                fig.add_trace(go.Scatter(
                    x=df['timestamp'],
                    y=df['equity'],
                    name=name,
                    line=dict(color=colors[i % len(colors)], width=2)
                ))

    fig.update_layout(
        title='策略资金曲线对比',
        xaxis_title='时间',
        yaxis_title='权益 ($)',
        hovermode='x',
        height=400,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    return fig


def create_comparison_table(results: Dict[str, Any]) -> html.Table:
    """创建绩效指标对比表"""
    headers = ['策略名称', '总交易次数', '胜率', '盈亏比', '总收益', '最大回撤', '夏普比率']
    rows = []

    for name, data in results.items():
        metrics = data.get('metrics', {})
        rows.append(html.Tr([
            html.Td(name, style={'fontWeight': 'bold'}),
            html.Td(str(metrics.get('total_trades', 0))),
            html.Td(f"{metrics.get('win_rate', 0):.1f}%"),
            html.Td(f"{metrics.get('profit_factor', 0):.2f}"),
            html.Td(f"{metrics.get('total_return', 0):.2f}%"),
            html.Td(f"{metrics.get('max_drawdown_pct', 0):.2f}%"),
            html.Td(f"{metrics.get('sharpe_ratio', 0):.2f}"),
        ]))

    return html.Table([
        html.Thead(html.Tr([html.Th(h, style={'padding': '8px 12px', 'backgroundColor': '#f8f9fa'}) for h in headers])),
        html.Tbody(rows)
    ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '13px'})

# ==================== 策略对比回调 ====================

@callback(
    Output('comparison-results', 'children'),
    Input('comparison-run-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    State('comparison-strategy-a', 'value'),
    State('comparison-strategy-b', 'value'),
    State('comparison-strategy-c', 'value'),
)
def run_comparison(n_clicks, params, strategy_a, strategy_b, strategy_c):
    if n_clicks == 0:
        return html.Div()

    if not params or not params.get('market_id'):
        return html.Div("请先选择事件和市场")

    # 定义策略配置
    strategy_configs = []
    threshold_map = {'dir_005': 0.005, 'dir_01': 0.01, 'dir_015': 0.015}

    if strategy_a:
        strategy_configs.append({
            'name': f'策略A (阈值{threshold_map[strategy_a]})',
            'params': {'price_threshold': threshold_map[strategy_a]}
        })
    if strategy_b:
        strategy_configs.append({
            'name': f'策略B (阈值{threshold_map[strategy_b]})',
            'params': {'price_threshold': threshold_map[strategy_b]}
        })
    if strategy_c:
        strategy_configs.append({
            'name': f'策略C (阈值{threshold_map[strategy_c]})',
            'params': {'price_threshold': threshold_map[strategy_c]}
        })

    # 执行对比
    results = ComparisonEngine.run_comparison(params, strategy_configs)

    if not results:
        return html.Div("对比运行失败，请检查参数")

    fig = create_comparison_chart(results)
    table = create_comparison_table(results)

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '400px'}),
        html.H5("📊 绩效指标对比", style={'margin': '15px 0 10px 0'}),
        table,
    ])

@callback(
    Output('sensitivity-results', 'children'),
    Input('sensitivity-run-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    State('sensitivity-param', 'value'),
    State('sensitivity-metric', 'value'),
    State('sensitivity-min', 'value'),
    State('sensitivity-max', 'value'),
)
def run_sensitivity_analysis(n_clicks, params, param_name, metric_key, min_val, max_val):
    if n_clicks == 0:
        return html.Div()

    if not params or not params.get('market_id'):
        return html.Div("请先选择事件和市场")

    # 生成参数值列表（10个点）
    param_values = np.linspace(min_val, max_val, 10).tolist()
    param_values = [round(v, 4) for v in param_values]

    # 运行分析
    from src.dash_app.utils.analysis.sensitivity import SensitivityAnalysis
    result = SensitivityAnalysis.run_sensitivity_analysis(
        params, param_name, param_values, metric_key
    )

    if not result or not result['results']:
        return html.Div("分析运行失败，请检查参数")

    # 构建图表
    fig = create_sensitivity_chart(result)
    best = result.get('best_value')

    best_info = html.Div()
    if best:
        best_info = html.Div([
            html.Strong("✅ 最优参数: "),
            html.Span(f"{param_name} = {best['param_value']:.4f}", style={'color': '#00b894', 'fontWeight': 'bold'}),
            html.Span(f" → {metric_key}: {best['metric_value']:.2f}", style={'fontWeight': 'bold'}),
        ], style={'padding': '10px', 'backgroundColor': '#e8f8f5', 'borderRadius': '6px', 'marginTop': '10px'})

    return html.Div([
        dcc.Graph(figure=fig, style={'height': '400px'}),
        best_info,
    ])


def create_sensitivity_chart(result: Dict[str, Any]) -> go.Figure:
    """创建敏感性分析图表"""
    fig = go.Figure()

    results = result['results']
    param_name = result['param_name']
    metric_key = result['metric_key']

    # 提取有效数据
    valid = [r for r in results if r.get('metric_value') is not None]
    if not valid:
        return go.Figure()

    x_vals = [r['param_value'] for r in valid]
    y_vals = [r['metric_value'] for r in valid]

    # 折线图 + 标记点
    fig.add_trace(go.Scatter(
        x=x_vals,
        y=y_vals,
        mode='lines+markers',
        name='敏感性曲线',
        line=dict(color='#00b894', width=2),
        marker=dict(size=8, color='#00b894'),
        hovertemplate='参数: %{x:.4f}<br>指标: %{y:.2f}<extra></extra>'
    ))

    # 标记最优值
    if result.get('best_value'):
        best = result['best_value']
        fig.add_annotation(
            x=best['param_value'],
            y=best['metric_value'],
            text=f"最优 {best['param_value']:.4f}",
            showarrow=True,
            arrowhead=2,
            ax=20,
            ay=-30,
            font=dict(color='#00b894', size=12)
        )

    metric_labels = {
        'total_return': '总收益率 (%)',
        'sharpe_ratio': '夏普比率',
        'win_rate': '胜率 (%)',
        'max_drawdown_pct': '最大回撤 (%)',
    }

    fig.update_layout(
        title=f'参数敏感性分析: {param_name} → {metric_labels.get(metric_key, metric_key)}',
        xaxis_title=param_name,
        yaxis_title=metric_labels.get(metric_key, metric_key),
        hovermode='x',
        height=400,
        margin=dict(l=50, r=50, t=50, b=50)
    )

    return fig