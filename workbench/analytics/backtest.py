# -*- coding: utf-8 -*-
"""带手续费回测引擎：信号 → 毛收益/净收益/费用明细 → 绩效统计。

成本模型：每次调仓按 |Δ仓位| × 当日收盘价 计名义额，佣金 + 滑点（bps）单边收取；
满仓进出（仓位 0/1）的简化假设在统计中注明。
统计指标（波动/回撤/夏普）调用 gs-quant 的 timeseries 原生实现（见 risk.py）。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from workbench.config import (COMMISSION_BPS, INITIAL_CAPITAL, SLIPPAGE_BPS,
                              SMA_FAST, SMA_SLOW, ZSCORE_ENTRY, ZSCORE_EXIT,
                              ZSCORE_WINDOW)
from workbench.analytics import risk as risk_mod


# ── 信号生成 ─────────────────────────────────────────────────────────────
def sma_cross_signals(close: pd.Series, fast: int = SMA_FAST, slow: int = SMA_SLOW) -> pd.Series:
    """双均线趋势：fast SMA > slow SMA 时持有多头，否则空仓。"""
    return (close.rolling(fast).mean() > close.rolling(slow).mean()).astype(float)


def zscore_reversion_signals(close: pd.Series, window: int = ZSCORE_WINDOW,
                             entry: float = ZSCORE_ENTRY, exit_: float = ZSCORE_EXIT):
    """z-score 均值回归：z < entry 建多，z >= exit_ 平仓。返回 (仓位, z序列)。"""
    mu, sd = close.rolling(window).mean(), close.rolling(window).std()
    z = (close - mu) / sd
    pos = pd.Series(0.0, index=close.index)
    state = 0.0
    for i in range(len(z)):
        zi = z.iloc[i]
        if state == 0.0 and pd.notna(zi) and zi < entry:
            state = 1.0
        elif state == 1.0 and pd.notna(zi) and zi >= exit_:
            state = 0.0
        pos.iloc[i] = state
    return pos, z


# ── 回测结果 ─────────────────────────────────────────────────────────────
@dataclass
class BTResult:
    symbol: str
    strategy: str
    equity_gross: pd.Series
    equity_net: pd.Series
    position: pd.Series
    zscore: pd.Series | None
    fees_ret: pd.Series        # 每日费用（收益率形式）
    stats: dict


def compute_stats(gross_ret: pd.Series, net_ret: pd.Series, turnover_daily: pd.Series,
                  close: pd.Series, pos: pd.Series, commission_bps: float,
                  slippage_bps: float, initial_capital: float,
                  equity_gross: pd.Series, equity_net: pd.Series) -> dict:
    """毛/净两套口径的绩效统计；波动、回撤、夏普走 gs-quant 原生实现。"""
    def _side(rets: pd.Series, equity: pd.Series) -> dict:
        total = float(equity.iloc[-1] / initial_capital - 1)
        n = max(len(rets.dropna()), 1)
        cagr = float((1 + total) ** (252 / n) - 1)
        return {
            "total_return": total,
            "cagr": cagr,
            "ann_vol": risk_mod.annual_vol(rets.dropna()),
            "sharpe": risk_mod.sharpe(equity),
            "max_drawdown": risk_mod.max_drawdown(equity),
        }

    buy_hold = float(close.iloc[-1] / close.iloc[0] - 1)
    trades = turnover_daily[turnover_daily > 0]
    return {
        **{f"gross_{k}": v for k, v in _side(gross_ret, equity_gross).items()},
        **{f"net_{k}": v for k, v in _side(net_ret, equity_net).items()},
        "num_trades": int(len(trades)),
        "turnover_total": float(turnover_daily.sum()),
        "exposure": float((pos > 0).mean()),
        "buy_and_hold": buy_hold,
        "commission_bps": commission_bps,
        "slippage_bps": slippage_bps,
        "fee_drag": float(equity_gross.iloc[-1] / initial_capital
                          - equity_net.iloc[-1] / initial_capital),
        "net_minus_buy_hold": float(equity_net.iloc[-1] / initial_capital - 1 - buy_hold),
    }


def run_backtest(df: pd.DataFrame, symbol: str, strategy: str = "zscore_reversion",
                 commission_bps: float = COMMISSION_BPS,
                 slippage_bps: float = SLIPPAGE_BPS,
                 initial_capital: float = INITIAL_CAPITAL) -> BTResult:
    """对单一标的执行带手续费回测，返回净值曲线与统计。"""
    close = df["adjclose"].astype(float)
    if strategy == "zscore_reversion":
        pos, z = zscore_reversion_signals(close)
    elif strategy == "sma_cross":
        pos, z = sma_cross_signals(close), None
    else:
        raise ValueError(f"unknown strategy: {strategy}")

    ret = close.pct_change().fillna(0.0)
    pos_prev = pos.shift(1).fillna(0.0)
    gross_ret = pos_prev * ret
    turnover_daily = pos.diff().abs().fillna(pos.iloc[0])
    cost_rate = (commission_bps + slippage_bps) / 1e4
    fees_ret = turnover_daily * cost_rate
    net_ret = gross_ret - fees_ret

    equity_gross = initial_capital * (1 + gross_ret).cumprod()
    equity_net = initial_capital * (1 + net_ret).cumprod()

    stats = compute_stats(gross_ret, net_ret, turnover_daily, close, pos,
                          commission_bps, slippage_bps, initial_capital,
                          equity_gross, equity_net)
    return BTResult(symbol, strategy, equity_gross, equity_net, pos, z,
                    fees_ret, stats)
