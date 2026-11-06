# -*- coding: utf-8 -*-
"""akshare 兜底数据源（东财封装，前复权）。

- A股: stock_zh_a_hist；指数（000300 等）回落到 index_zh_a_hist
- 美股: stock_us_hist，市场前缀 105(纳斯达克)/106(纽交所)/107(AMEX) 逐个试探

注意：akshare import 约 1.2s，全部懒加载——只在主源失败时才付出这笔开销。
"""
from __future__ import annotations

import pandas as pd

from workbench.config import HISTORY

MIN_ROWS = 900

_COLS = {"日期": "date", "开盘": "open", "收盘": "close", "最高": "high",
         "最低": "low", "成交量": "volume"}


def _date_range() -> tuple[str, str]:
    days = {"5y": 1830}.get(HISTORY, 1830)
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y%m%d")
    end = pd.Timestamp.today().strftime("%Y%m%d")
    return start, end


def _normalize(df: pd.DataFrame) -> pd.DataFrame | None:
    """akshare 中文列 → workbench 标准六列。"""
    if df is None or df.empty:
        return None
    missing = [c for c in _COLS if c not in df.columns]
    if missing:
        return None
    out = df[list(_COLS)].rename(columns=_COLS)
    out.index = pd.DatetimeIndex(pd.to_datetime(out.pop("date")), name="date")
    out = out.astype(float)
    out["adjclose"] = out["close"]                    # qfq 前复权
    out["volume"] = (out["volume"] * 100).astype("int64")  # 手 → 股
    out = out[["open", "high", "low", "close", "adjclose", "volume"]]
    out = out.dropna(subset=["close"]).sort_index()
    return out if len(out) >= MIN_ROWS else None


def fetch_ak_cn(symbol: str) -> pd.DataFrame | None:
    """A股/指数兜底：先个股接口，指数回落 index 接口。"""
    try:
        import akshare as ak
    except ImportError:
        return None
    code = symbol.split(".")[0]
    start, end = _date_range()
    for fn in (ak.stock_zh_a_hist, ak.index_zh_a_hist):
        try:
            df = fn(symbol=code, period="daily", start_date=start, end_date=end,
                    adjust="qfq")
            norm = _normalize(df)
            if norm is not None:
                return norm
        except Exception:  # noqa: BLE001 —— 指数走个股接口会抛错，逐个尝试
            continue
    return None


def fetch_ak_us(symbol: str) -> pd.DataFrame | None:
    """美股兜底：东财源前复权，市场前缀逐个试探。"""
    try:
        import akshare as ak
    except ImportError:
        return None
    code = symbol.split(".")[0]
    start, end = _date_range()
    for prefix in ("105", "106", "107"):  # NASDAQ / NYSE / AMEX
        try:
            df = ak.stock_us_hist(symbol=f"{prefix}.{code}", period="daily",
                                  start_date=start, end_date=end, adjust="qfq")
            norm = _normalize(df)
            if norm is not None:
                return norm
        except Exception:  # noqa: BLE001
            continue
    return None
