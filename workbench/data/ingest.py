# -*- coding: utf-8 -*-
"""数据接入：yfinance 五年日线 → ArcticDB。

真实数据优先级：yfinance → Stooq（免费日线 CSV，无需 key）→ 模拟数据兜底。
每个符号的来源与新鲜度写入 ArcticDB 元数据，工作台状态页可见。
"""
from __future__ import annotations

import datetime as dt
import time

import pandas as pd

from workbench.config import HISTORY, active_symbols, ensure_dirs
from workbench.data.eastmoney import fetch_eastmoney
from workbench.data.simulate import simulate_daily
from workbench.store.arctic import write_symbol

COLS = ["open", "high", "low", "close", "adjclose", "volume"]
MIN_ROWS = 900          # 5 年 ≈ 1260 个交易日，低于 900 视为数据不足
FRESH_DAYS = 10         # 最新日期距今超过 10 天视为过期


def _normalize(df: pd.DataFrame) -> pd.DataFrame | None:
    """统一为 workbench 标准六列、DatetimeIndex、按日期排序。"""
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    close = "adj close" if "adj close" in df.columns else ("adjclose" if "adjclose" in df.columns else "close")
    out = pd.DataFrame(index=pd.DatetimeIndex(pd.to_datetime(df.index), name="date"))
    out["open"] = df.get("open")
    out["high"] = df.get("high")
    out["low"] = df.get("low")
    out["close"] = df.get("close")
    out["adjclose"] = df.get(close, df.get("close"))
    out["volume"] = df.get("volume", 0)
    out = out.dropna(subset=["close"]).sort_index()
    if "volume" in out:
        out["volume"] = out["volume"].fillna(0).astype("int64")
    return out.dropna(how="all") if not out.empty else None


def fetch_yfinance(symbol: str, retries: int = 2) -> pd.DataFrame | None:
    """yfinance 五年日线；429/限流时重试。"""
    try:
        import yfinance as yf
    except ImportError:
        return None
    for attempt in range(retries + 1):
        try:
            df = yf.download(symbol, period=HISTORY, interval="1d", auto_adjust=True,
                             progress=False, threads=False)
            norm = _normalize(df)
            if norm is not None and len(norm) >= MIN_ROWS:
                return norm
        except Exception as exc:  # noqa: BLE001
            print(f"  [yfinance] {symbol} attempt {attempt + 1} failed: {exc}")
        time.sleep(2 * (attempt + 1))
    return None


def fetch_stooq(symbol: str) -> pd.DataFrame | None:
    """Stooq 免费日线兜底（真实数据，未复权，注意口径差异）。"""
    url = f"https://stooq.com/q/d/l/?s={symbol.lower()}.us&i=d"
    try:
        df = pd.read_csv(url, parse_dates=["Date"], index_col="Date")
        if df.empty:
            return None
        df = df.rename(columns=str.lower)
        df["adjclose"] = df["close"]          # Stooq 此端点未复权
        norm = _normalize(df)
        if norm is not None and len(norm) >= MIN_ROWS:
            return norm.tail(int(MIN_ROWS * 5 / 4))  # 截到约5年
    except Exception as exc:  # noqa: BLE001
        print(f"  [stooq] {symbol} failed: {exc}")
    return None


def fetch_one(symbol: str) -> tuple[pd.DataFrame, str, str]:
    """返回 (df, source, note)。

    降级链：A股 东财直连 → akshare → 模拟；
            港股 东财(116/100) → 模拟（yfinance 无港股个股）；
            恒指基准 HSI.HK: yfinance ^HSI → 东财 100.HSI → 模拟；
            美股 yfinance → akshare（东财源前复权）→ Stooq → 模拟。
    """
    from workbench.config import is_cn, is_hk
    from workbench.data.akshare_src import fetch_ak_cn, fetch_ak_us
    if symbol == "HSI.HK":  # 恒指基准
        df = fetch_yfinance("^HSI")
        if df is not None:
            return df, "yfinance", "恒生指数 ^HSI"
        df = fetch_eastmoney(symbol)
        if df is not None:
            return df, "eastmoney", "恒生指数（东财 100.HSI）"
        return simulate_daily(symbol), "simulated", "真实数据源均不可用，使用 GBM 模拟数据"
    if is_cn(symbol):
        df = fetch_eastmoney(symbol)
        if df is not None:
            return df, "eastmoney", "东方财富前复权日线（yfinance 无 A 股数据）"
        df = fetch_ak_cn(symbol)
        if df is not None:
            return df, "akshare", "东财直连失败，akshare 兜底（前复权）"
        return simulate_daily(symbol), "simulated", "真实数据源均不可用，使用 GBM 模拟数据"
    if is_hk(symbol):
        df = fetch_eastmoney(symbol)
        if df is not None:
            return df, "eastmoney", "东方财富港股前复权日线（116 通道）"
        return simulate_daily(symbol), "simulated", "真实数据源均不可用，使用 GBM 模拟数据"
    df = fetch_yfinance(symbol)
    if df is not None:
        return df, "yfinance", ""
    df = fetch_ak_us(symbol)
    if df is not None:
        return df, "akshare", "yfinance 不可用，akshare（东财源前复权）兜底"
    df = fetch_stooq(symbol)
    if df is not None:
        return df, "stooq", "yfinance 不可用，改用 Stooq 真实日线（未复权）"
    return simulate_daily(symbol), "simulated", "真实数据源均不可用，使用 GBM 模拟数据"


def ingest_all() -> dict:
    """全量落库：真实数据优先，不足则模拟兜底；写 ArcticDB 并返回状态。"""
    ensure_dirs()
    status = {}
    for symbol in active_symbols():
        df, source, note = fetch_one(symbol)
        stale = (pd.Timestamp.today() - df.index.max()).days > FRESH_DAYS
        if source != "simulated" and stale:
            note += f"；数据过期（最新 {df.index.max().date()}），标记为受限真实数据"
        write_symbol(df, symbol, source, extra_meta={"stale": stale, "note": note})
        status[symbol] = {
            "source": source, "rows": int(len(df)),
            "start": str(df.index.min().date()), "end": str(df.index.max().date()),
            "note": note, "stale": bool(stale),
        }
        print(f"  {symbol:<6} {source:<10} rows={len(df):>5} "
              f"({df.index.min().date()} → {df.index.max().date()}) {note}")
    return status


if __name__ == "__main__":
    from workbench.store.arctic import symbol_status
    st = ingest_all()
    print("\nArcticDB 库内状态：")
    for k, v in symbol_status().items():
        print(f"  {k:<6} {v}")
