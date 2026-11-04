/*
 * 事件倒计时 —— 纯前端，零服务端开销
 *
 * 用法：服务端渲染一个带 data-end-ts 属性的元素即可，例如
 *     html.Span("--", **{"data-end-ts": 1793788800})
 * 本脚本每秒扫一遍这些元素，把「距离该时间戳还剩多久」写进 textContent。
 *
 * 为什么不用 Dash 的 dcc.Interval：
 *   每秒一次的服务端回调 = 每小时 3600 次请求，PythonAnywhere 免费版
 *   100 CPU 秒/天根本扛不住。放前端的代价是每秒一次 querySelectorAll
 *   （节点数一般 < 10），开销在几十微秒量级，可以忽略。
 *
 * 为什么用属性扫描而不是绑定到具体 id：
 *   同一个页面可能有多处倒计时（分析页、探索器），组件也可能随 Tab 切换
 *   反复重建。扫描 DOM 属性天然不受 React 重渲染影响。
 */
(function () {
    'use strict';

    function fmt(ms) {
        if (ms <= 0) {
            return '已结束';
        }
        var total = Math.floor(ms / 1000);
        var d = Math.floor(total / 86400);
        var h = Math.floor((total % 86400) / 3600);
        var m = Math.floor((total % 3600) / 60);
        var s = total % 60;
        var out = '';
        if (d > 0) {
            out += d + 'd ';
        }
        return out + h + 'h ' + m + 'm ' + s + 's';
    }

    function tick() {
        var nodes = document.querySelectorAll('[data-end-ts]');
        for (var i = 0; i < nodes.length; i++) {
            var node = nodes[i];
            var end = parseFloat(node.getAttribute('data-end-ts'));
            if (!end || isNaN(end)) {
                continue;
            }
            var text = fmt(end * 1000 - Date.now());
            if (node.textContent !== text) {
                node.textContent = text;
            }
        }
    }

    setInterval(tick, 1000);
    // Dash 是异步渲染的，页面首次加载和路由切换后各补几次
    document.addEventListener('DOMContentLoaded', tick);
    setTimeout(tick, 300);
    setTimeout(tick, 1200);
})();
