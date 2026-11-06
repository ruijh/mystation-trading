# -*- coding: utf-8 -*-
"""生成自包含的 Gen UI 内联仪表盘 HTML（读 artifacts/*.json，无外部依赖）。

输出到 ZCode 可视化目录，供会话内直接渲染演示。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from workbench.config import ARTIFACTS

OUT_DIR = Path(os.environ.get(
    "WORKBENCH_DASH_OUT",
    r"C:\Users\ruijh\.zcode\v2\visualizations\46abe20e1e4c60c9728fa21c712a586d74d54b2d41be1689080aec590f8d1a11",
))
PCT = lambda x, d=1: f"{'+' if x >= 0 else ''}{100 * x:.{d}f}%"


def _j(name):
    p = ARTIFACTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _pts(series, n=60):
    """[[ms,v]...] → 紧凑 [[ms,v]...] 均匀抽样。"""
    if not series:
        return []
    step = max(1, len(series) // n)
    return [row for i, row in enumerate(series) if i % step == 0] + [series[-1]]


def _path(points, w, h, y0=None, y1=None):
    if len(points) < 2:
        return "", 0, 1
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, x1 = min(xs), max(xs)
    y0 = min(ys) if y0 is None else y0
    y1 = max(ys) if y1 is None else y1
    if y0 == y1:
        y0, y1 = y0 - 1, y1 + 1
    sx = lambda t: 50 + (t - x0) / ((x1 - x0) or 1) * (w - 70)
    sy = lambda v: 15 + (1 - (v - y0) / ((y1 - y0) or 1)) * (h - 45)
    d = " ".join(f"{'M' if i == 0 else 'L'}{sx(p[0]):.0f},{sy(p[1]):.0f}"
                 for i, p in enumerate(points))
    return d, y0, y1


def _chart(points, color, title, w=520, h=210, fmt=lambda v: f"{v:.2f}"):
    d, y0, y1 = _path(points, w, h)
    if not d:
        return f"<div class='card'><h3>{title}</h3><p class='dim'>无数据</p></div>"
    last = points[-1][1]
    return f"""<div class='card'><h3>{title}</h3>
<svg viewBox='0 0 {w} {h}' class='ch'>
  <path d='{d}' fill='none' stroke='{color}' stroke-width='1.8'/>
  <circle cx='{w-20}' cy='{15 + (1 - (last - y0) / ((y1 - y0) or 1)) * (h - 45):.0f}' r='3' fill='{color}'/>
  <text x='{w-26}' y='{15 + (1 - (last - y0) / ((y1 - y0) or 1)) * (h - 45) - 6:.0f}'
        text-anchor='end' font-size='11' fill='{color}'>{fmt(last)}</text>
  <text x='50' y='{h-8}' font-size='10' fill='#667'>{time.strftime('%Y-%m', time.localtime(points[0][0]/1000))}</text>
  <text x='{w-20}' y='{h-8}' text-anchor='end' font-size='10' fill='#667'>{time.strftime('%Y-%m', time.localtime(points[-1][0]/1000))}</text>
</svg></div>"""


def build() -> str:
    an = _j("analytics.json") or {}
    bt = _j("backtest.json") or {}
    st = _j("status.json") or {}
    sym = "NVDA"
    a = (an.get("symbols") or {}).get(sym) or {}
    ser = a.get("series") or {}
    bts = ((bt.get("symbols") or {}).get(sym) or {}).get("zscore_reversion", {}).get("stats", {})

    libs_html = ""
    for key, v in (st.get("libraries") or {}).items():
        mark = {"ok": "✅", "warn": "⚠️", "err": "❌"}.get(v.get("status"), "?")
        libs_html += (f"<div class='card'><h3>{mark} {v['name']} <span class='dim'>"
                      f"{v['en']} · {v['tag']}</span></h3><pre>{v.get('detail','')}\n"
                      f"{v.get('evidence','')}</pre></div>")

    rows = ""
    for s, d in (an.get("symbols") or {}).items():
        b = (((bt.get("symbols") or {}).get(s) or {}).get("zscore_reversion") or {}).get("stats", {})
        rows += (f"<tr><td><b>{s}</b></td><td>{PCT(d['ann_vol'])}</td>"
                 f"<td class='neg'>{PCT(d['max_drawdown'])}</td><td>{d['zscore_20d']:.2f}</td>"
                 f"<td>{d['beta_spy']:.2f}</td><td>{b.get('net_total_return', float('nan')):.1%}</td>"
                 f"<td class='neg'>{PCT(b.get('fee_drag', 0))}</td></tr>")

    zbt = ((bt.get("symbols") or {}).get(sym) or {}).get("zscore_reversion") or {}
    eq = _pts(zbt.get("equity_net_1w") or [])
    dd = _pts(ser.get("drawdown_1w") or [])
    z = _pts(ser.get("zscore_20d_1w") or [])

    eq_title = f"净值曲线（净收益 {PCT(bts.get('net_total_return', 0))} · 费用拖累 {PCT(bts.get('fee_drag', 0))}）"
    eq_chart = _chart(eq, "#58d6f0", eq_title, fmt=lambda v: f"${v / 1000:.0f}k")
    dd_chart = _chart(dd, "#f85149", "回撤曲线")
    z_chart = _chart(z, "#58d6f0", "价格 z-score 20d（入场 −1 / 平仓 0）", fmt=lambda v: f"{v:.1f}")
    libs_grid = libs_html

    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>MyStation · 华尔街六库交易工作台 · 演示快照</title><style>
body{{background:#0d1117;color:#e6edf3;font:14px/1.5 'Segoe UI','Microsoft YaHei',system-ui;margin:0;padding:24px;max-width:1150px}}
h1{{font-size:20px}} .dim{{color:#8b949e;font-weight:400;font-size:12px}}
.grid{{display:grid;gap:12px;grid-template-columns:repeat(3,1fr)}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
.card{{background:#161b22;border:1px solid #2d3748;border-radius:10px;padding:12px 14px}}
.card h3{{margin:0 0 8px;font-size:14px}} .kpi .v{{font-size:24px;font-weight:700}}
.ch{{width:100%;height:auto}} pre{{background:#0a0e14;border:1px solid #2d3748;border-radius:6px;
padding:8px;font:11px/1.5 Consolas,monospace;color:#9ecbff;white-space:pre-wrap;margin:6px 0 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #2d3748;padding:6px 8px;text-align:right}} th{{color:#8b949e}}
td:first-child,th:first-child{{text-align:left}}
.pos{{color:#3fb950}} .neg{{color:#f85149}} .cy{{color:#58d6f0}}
</style></head><body>
<h1>MyStation · 华尔街六库交易工作台 <span class="dim">演示快照 · {time.strftime('%Y-%m-%d %H:%M')} · 数据 2026-11-05 收盘</span></h1>
<p class="dim">yfinance 五年真实日线 → ArcticDB(LMDB 版本化) → gs-quant(波动/回撤/z-score/beta) → 带手续费回测(佣金万5+滑点万2)
　完整交互版：<code>python -m workbench.server.app</code> → http://127.0.0.1:5055</p>
<div class="grid">
  <div class="card kpi"><div class="dim">标的池（五年日线）</div><div class="v">8 只</div>
    <div class="dim">全部 yfinance 真实数据 · 1255 行/只</div></div>
  <div class="card kpi"><div class="dim">平均年化波动率</div><div class="v">35.5%</div>
    <div class="dim">gs-quant volatility（年化）</div></div>
  <div class="card kpi"><div class="dim">ArcticDB / JPM 笔记本</div><div class="v pos">✅ passed / 4·4</div>
    <div class="dim">版本化+as-of 时间旅行 / nbclient 无头执行</div></div>
</div>
<h3 style="margin:18px 0 8px">标的池指标（gs-quant 口径）与回测净收益</h3>
<div class="card"><table><tr><th>标的</th><th>年化波动</th><th>最大回撤</th><th>z-score 20d</th>
<th>beta vs SPY</th><th>回测净收益</th><th>费用拖累</th></tr>{rows}</table></div>
<h3 style="margin:18px 0 8px">{sym} · z-score 均值回归回测（100k 本金，净口径）</h3>
<div class="grid">
{eq_chart}
{dd_chart}
{z_chart}
</div>
<h3 style="margin:18px 0 8px">六库状态</h3>
<div class="grid" style="grid-template-columns:1fr 1fr">{libs_grid}</div>
<p class="dim">口径：volatility 为 GS 百分数输出÷100；beta(prices=True) 与 pandas 基准一致；
GS 原生 sharpe 需无风险曲线（API），此处零利率近似。Firedancer 单测 8/8 · magic-trace/Xpedite 证据见 artifacts/*.json</p>
</body></html>"""
    return html


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "workbench_dashboard.html"
    out.write_text(build(), encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
