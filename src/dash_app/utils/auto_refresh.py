"""自动刷新基建（只在分析类页面启用）

思路：
1. 全局一个 dcc.Interval（10 分钟）。非 /analysis、/insights 页面把它 disabled，
   完全不产生回调请求。
2. 每次 tick 只查两条 MAX（tweet_hourly.timestamp_unix_utc、
   price_hourly.hour_start_utc）。两表都有索引，MAX 是索引末端一次 seek，
   微秒级，PA 免费版的 CPU 额度完全够。
3. 用「数据版本串」判断有没有新数据：版本没变就 no_update，一个查询之外
   什么都不做；版本变了才清缓存并写 dcc.Store，各业务回调监听
   data-version 重算。

为什么不能只靠 lru_cache 自然过期：
   缓存 key 是日期/小时，跨小时才失效。但采集是在整点后几分钟写入的，
   页面可能在 :05 刚用完缓存、:07 数据就到了 —— 此时 key 没变，缓存
   不会失效，页面要一直挂到下一个整点。版本号能立刻发现这种变化。
"""

from dash import Input, Output, State, callback, no_update

from src.dash_app.utils.data_loader import run_query, clear_caches as clear_data_caches
from src.dash_app.utils.stats_loader import clear_stats_caches

# 刷新间隔：采集是每小时一次，10 分钟足够及时，又不会把额度耗在空转上
REFRESH_INTERVAL_MS = 10 * 60 * 1000

# 只有这两页需要"数据到了自动更新"，其余页面 Interval 保持 disabled
REFRESH_PAGES = ('/analysis', '/insights')


def current_data_version() -> str:
    """数据版本 = 推文表最新小时 + 价格表最新小时，任一变即视为有新数据"""
    df = run_query("""
        SELECT (SELECT MAX(timestamp_unix_utc) FROM tweet_hourly) AS tw,
               (SELECT MAX(hour_start_utc)     FROM price_hourly) AS pr
    """)
    if df.empty:
        return ''
    tw = df['tw'].iloc[0]
    pr = df['pr'].iloc[0]
    return f"{int(tw) if tw is not None else 0}-{int(pr) if pr is not None else 0}"


@callback(
    Output('auto-refresh-tick', 'disabled'),
    Input('url', 'pathname'),
)
def toggle_auto_refresh(pathname):
    """进出刷新页面时开关定时器，避免在其他页面空转"""
    return pathname not in REFRESH_PAGES


@callback(
    Output('data-version', 'data'),
    Input('auto-refresh-tick', 'n_intervals'),
    Input('url', 'pathname'),
    State('data-version', 'data'),
)
def bump_data_version(_n_intervals, pathname, prev_version):
    """tick 时比对数据版本；有新数据才清缓存并下发新版本号"""
    if pathname not in REFRESH_PAGES:
        return no_update

    version = current_data_version()
    if not version or version == prev_version:
        return no_update

    if prev_version is None:
        # 会话内第一次 tick：缓存本来就是空的，只记下版本号，不必清
        return version

    # 新数据到了：清掉旧缓存，让监听 data-version 的回调重新查库
    clear_data_caches()
    clear_stats_caches()
    return version
