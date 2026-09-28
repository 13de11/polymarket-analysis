# src/dash_app/pages/backtest/__init__.py
"""
预测回测系统 - 回调注册

注意：layout 已移到 layout.py。
"""

from dash import html, Input, Output, State, callback, no_update, ctx
import pandas as pd

from src.dash_app.utils.backtest.runner import run_backtest
from src.dash_app.pages.backtest.tabs.preview import render_preview_tab
from src.dash_app.pages.backtest.tabs.overview import render_overview_tab
from src.dash_app.pages.backtest.tabs.trades import render_trades_tab
from src.dash_app.pages.backtest.tabs.evaluation import render_evaluation

# 从 layout 模块 re-export，保持 app_new.py 的 `from ... import layout` 兼容
from src.dash_app.pages.backtest.layout import layout  # noqa: F401


# ==================== 回测执行（唯一入口） ====================

@callback(
    Output('backtest-result-store', 'data'),
    Input('backtest-run-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    prevent_initial_call=True,
)
def cache_backtest_result(n_clicks, params):
    """点击「运行回测」时跑一次，结果存 store。所有 tab 从这里读。"""
    if not n_clicks:
        return no_update
    if not params or not params.get('market_id'):
        return {}
    result = run_backtest(params)
    if not result:
        return {}
    return {
        'metrics': result.get('metrics', {}),
        'trades': result.get('trades', []),
        'equity_curve': result.get('equity_curve', []),
        'final_capital': result.get('final_capital'),
    }


# ==================== Tab 内容分发 ====================

def _placeholder(msg):
    return html.Div(msg, style={
        'color': '#6c757d', 'textAlign': 'center',
        'padding': '40px 0',
    })


@callback(
    Output('backtest-tab-content', 'children'),
    Output('backtest-status-text', 'children'),
    Input('backtest-tabs', 'value'),
    Input('backtest-result-store', 'data'),
    Input('backtest-preview-btn', 'n_clicks'),
    State('backtest-params-store', 'data'),
    State('series-selector', 'value'),
)
def render_tab_content(tab_name, cached_result, preview_n, params, series):
    if not params or not params.get('market_id'):
        return _placeholder("请选择事件和市场，点击「运行回测」"), \
               "请选择事件和市场"

    series = series or '7d'

    # ---- 信号预览：随时可刷（点按钮或切到该 tab） ----
    if tab_name == 'preview':
        content, stats = render_preview_tab(params, series)
        n = stats.get('total_signals', 0)
        acc = stats.get('overall_accuracy', 0) * 100
        return content, f"✅ 信号预览 | 信号总数: {n} | 方向准确率: {acc:.1f}%"

    # ---- 其余 tab：统一从 store 读 ----
    if not cached_result or not cached_result.get('metrics'):
        return _placeholder("暂无回测结果，请点击「运行回测」"), \
               "暂无回测结果"

    if tab_name == 'overview':
        content, status = render_overview_tab(cached_result)
        return content, status

    if tab_name == 'trades':
        content, status = render_trades_tab(cached_result)
        return content, status

    if tab_name == 'evaluation':
        content, status = render_evaluation(params, cached_result)
        return content, status

    return _placeholder("未知 Tab"), ""


# ==================== 交易明细导出 ====================

@callback(
    Output('backtest-trades-download', 'data'),
    Input('backtest-trades-export-btn', 'n_clicks'),
    State('backtest-result-store', 'data'),
    prevent_initial_call=True,
)
def export_trades(n_clicks, cached_result):
    if not n_clicks or not cached_result:
        return no_update

    trades = cached_result.get('trades', [])
    completed = [t for t in trades if t.get('result') != 'pending']
    if not completed:
        df = pd.DataFrame(columns=['提示'])
        df.loc[0] = ['无已完成交易']
    else:
        df = pd.DataFrame(completed)

    return dcc.send_data_frame(df.to_csv, 'backtest_trades.csv',
                               index=False, encoding='utf-8-sig')


# 需要 dcc 用于 send_data_frame
from dash import dcc  # noqa: E402