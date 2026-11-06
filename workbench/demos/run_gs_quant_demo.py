# -*- coding: utf-8 -*-
"""gs-quant（高盛）分析演示：波动率 / 最大回撤 / z-score / beta —— 全部走 GS 开源库。

输入：ArcticDB 中的五年日线（yfinance 真实数据）
输出：artifacts/analytics.json（指标 + 图表序列）+ 控制台摘要
"""
from __future__ import annotations

import json
import time

from workbench.analytics import risk
from workbench.config import ARTIFACTS, ZSCORE_WINDOW, active_tickers, benchmark_of
from workbench.store.arctic import load_symbol


def _series_json(s, freq=None) -> list:
    """pd.Series → [[ms, val], ...]（可选降采样，供前端 SVG 图表）。"""
    s = s.dropna()
    if freq:
        s = s.resample(freq).last().dropna()
    return [[int(ts.timestamp() * 1000), round(float(v), 6)] for ts, v in s.items()]


def analyze_symbol(symbol: str, bench_cache: dict | None = None) -> dict:
    """单标的 gs-quant 全套指标（供全量 run 与页面增量添加共用）。"""
    bench_cache = {} if bench_cache is None else bench_cache
    bench_name = benchmark_of(symbol)
    if bench_name not in bench_cache:
        bench_cache[bench_name] = load_symbol(bench_name)["adjclose"].astype(float)
    bench = bench_cache[bench_name]
    px = load_symbol(symbol)["adjclose"].astype(float)
    sym_out = {
        "benchmark": bench_name,
        "ann_vol": risk.annual_volatility_from_prices(px),
        "max_drawdown": risk.max_drawdown(px),
        "zscore_20d": risk.latest_zscore(px, ZSCORE_WINDOW),
        "beta_spy": risk.beta_vs_benchmark(px, bench),
        "sharpe": risk.sharpe_ratio(px),
        "series": {
            "drawdown_1w": _series_json(risk.drawdown_curve(px), "1W-FRI"),
            "rolling_vol_63d_1w": _series_json(risk.rolling_volatility(px, 63), "1W-FRI"),
            "zscore_20d_1w": _series_json(risk.zscore_series(px, ZSCORE_WINDOW), "1W-FRI"),
            "beta_126d_1w": _series_json(risk.rolling_beta(px, bench, 126), "1W-FRI"),
        },
    }
    print(f"  {symbol:<10} bench={bench_name:<10} vol={sym_out['ann_vol']:.2%}  "
          f"maxDD={sym_out['max_drawdown']:.2%}  z={sym_out['zscore_20d']:+.2f}  "
          f"beta={sym_out['beta_spy']:.2f}  sharpe={sym_out['sharpe']:.2f}")
    return sym_out


def run() -> dict:
    out = {
        "engine": risk.ENGINE,
        "benchmarks": {"US": "SPY", "CN": "000300.SS", "HK": "HSI.HK"},
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "symbols": {},
    }
    bench_cache: dict[str, pd.Series] = {}
    for symbol in active_tickers():
        out["symbols"][symbol] = analyze_symbol(symbol, bench_cache)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "analytics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    print(f"  → {ARTIFACTS / 'analytics.json'}")
    return out


if __name__ == "__main__":
    run()
