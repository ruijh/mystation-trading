# -*- coding: utf-8 -*-
"""带手续费回测演示：z-score 均值回归 + 双均线趋势，毛/净双口径 + 费用明细。

成本模型：调仓按 |Δ仓位| × 收盘价 计名义额，佣金(万5)+滑点(万2)单边收取。
绩效指标（波动/回撤/夏普）调用 gs-quant 实现。
输出：artifacts/backtest.json
"""
from __future__ import annotations

import json
import time

import pandas as pd

from workbench.analytics.backtest import run_backtest
from workbench.config import ARTIFACTS, TICKERS
from workbench.store.arctic import load_symbol


def _equity_json(s) -> list:
    s = s.resample("1W-FRI").last().dropna()  # 降采样到周线，前端可读
    return [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in s.items()]


def _bt_to_json(bt) -> dict:
    return {
        "strategy": bt.strategy,
        "stats": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in bt.stats.items()},
        "equity_gross_1w": _equity_json(bt.equity_gross),
        "equity_net_1w": _equity_json(bt.equity_net),
        "position_1w": _equity_json(bt.position.resample("1W-FRI").last()),
    }


def run() -> dict:
    out = {"generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "cost_model": "commission 5bps + slippage 2bps，单边，按 |Δ仓位|×收盘价 计名义额；"
                         "A股与美股统一口径（未计 A 股印花税/过户费，未模拟 T+1 与涨跌停）",
           "symbols": {}}
    for symbol in TICKERS:
        df = load_symbol(symbol)
        primary = run_backtest(df, symbol, strategy="zscore_reversion")
        secondary = run_backtest(df, symbol, strategy="sma_cross")
        out["symbols"][symbol] = {
            "zscore_reversion": _bt_to_json(primary),
            "sma_cross": _bt_to_json(secondary),
        }
        s = primary.stats
        print(f"  {symbol:<5} 净收益={s['net_total_return']:+8.2%}  (毛 {s['gross_total_return']:+8.2%})"
              f"  买入持有={s['buy_and_hold']:+8.2%}  净夏普={s['net_sharpe']:.2f}"
              f"  净回撤={s['net_max_drawdown']:.2%}  交易次数={s['num_trades']}"
              f"  费用拖累={s['fee_drag']:.2%}")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "backtest.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                             encoding="utf-8")
    print(f"  → {ARTIFACTS / 'backtest.json'}")
    return out


if __name__ == "__main__":
    run()
