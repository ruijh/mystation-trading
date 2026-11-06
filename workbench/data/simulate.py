# -*- coding: utf-8 -*-
"""模拟数据兜底：几何布朗运动生成日线 OHLCV（仅在真实数据不可用时使用）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

# 各标的的伪参数（年化漂移 / 波动率），让模拟数据保持股性差异
PARAMS = {
    "AAPL": (0.15, 0.26), "MSFT": (0.18, 0.24), "NVDA": (0.45, 0.48),
    "JPM": (0.10, 0.22), "GS": (0.12, 0.25), "XOM": (0.06, 0.28),
    "TSLA": (0.20, 0.55), "SPY": (0.09, 0.16),
}


def simulate_daily(symbol: str, days: int = 1260, end: pd.Timestamp | None = None,
                   start_price: float = 150.0) -> pd.DataFrame:
    """生成 days 个交易日的 OHLCV；带轻微动量与波动聚集，回测才有形态可看。"""
    mu, sigma = PARAMS.get(symbol, (0.10, 0.30))
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    end = end or pd.Timestamp.today().normalize()
    idx = pd.bdate_range(end=end, periods=days)

    daily_sigma = sigma / np.sqrt(252)
    daily_mu = mu / 252
    ret = np.zeros(days)
    vol_state = 1.0
    for i in range(days):
        vol_state = 0.95 * vol_state + 0.05 * max(0.2, 1 + rng.normal(0, 0.35))
        ret[i] = daily_mu + daily_sigma * vol_state * rng.standard_normal()
    close = start_price * np.exp(np.cumsum(ret))

    intraday = np.abs(rng.normal(0, daily_sigma, days)) + 0.002
    open_ = np.empty(days)
    open_[0] = close[0] * (1 + rng.normal(0, 0.005))
    open_[1:] = close[:-1] * (1 + rng.normal(0, 0.004, days - 1))
    high = np.maximum(open_, close) * (1 + intraday)
    low = np.minimum(open_, close) * (1 - intraday * rng.uniform(0.6, 1.0, days))
    volume = (2e7 * (1 + 6 * np.abs(ret)) * rng.lognormal(0, 0.3, days)).astype("int64")

    df = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close,
         "adjclose": close, "volume": volume},
        index=pd.DatetimeIndex(idx, name="date"),
    )
    return df.round(4)
