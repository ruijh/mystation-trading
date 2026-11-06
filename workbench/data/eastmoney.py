# -*- coding: utf-8 -*-
"""A 股/港股数据接入：东方财富公开日线 API（前复权，无需 key）。

secid 规则：沪市 1.XXXXXX，深市 0.XXXXXX，港股 116.XXXXX（5 位），
恒指等港股指数 100.XXXXX。
klines 字段序：日期,开盘,收盘,最高,最低,成交量,成交额。
A股成交量单位为「手」（×100 转股）；港股/指数单位已是「股」，不换算。
"""
from __future__ import annotations

import json
import urllib.request

import pandas as pd

from workbench.config import HISTORY

URL = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
       "?secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
       "&fields2=f51,f52,f53,f54,f55,f56,f57&klt=101&fqt=1&beg={beg}&end=20500101")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 港股指数（恒指基准等）：workbench 符号 → 东财 secid 前缀
HK_INDEX = {"HSI": "100"}


def _secid(symbol: str) -> str:
    code = symbol.split(".")[0]
    if symbol.endswith(".SS"):
        return f"1.{code}"
    if symbol.endswith(".HK"):
        if code in HK_INDEX:
            return f"{HK_INDEX[code]}.{code}"
        return f"116.{code}"
    return f"0.{code}"


def _volume_shares(symbol: str) -> bool:
    """A股成交量是「手」需要 ×100；港股/指数已经是「股」。"""
    return symbol.endswith((".SS", ".SZ")) and symbol.split(".")[0].isdigit()


def _beg() -> str:
    days = {"5y": 1830}.get(HISTORY, 1830)
    return str((pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y%m%d"))


def eastmoney_name(symbol: str) -> str | None:
    """取东财返回的证券名称（如 贵州茅台/腾讯控股）；失败返回 None。"""
    if not symbol.endswith((".SS", ".SZ", ".HK")):
        return None
    try:
        req = urllib.request.Request(URL.format(secid=_secid(symbol), beg=_beg()),
                                     headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        name = (data.get("data") or {}).get("name")
        return str(name) if name else None
    except Exception:  # noqa: BLE001
        return None


def fetch_eastmoney(symbol: str, retries: int = 2) -> pd.DataFrame | None:
    """东财前复权日线 → workbench 标准六列。"""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(URL.format(secid=_secid(symbol), beg=_beg()),
                                         headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            klines = (data.get("data") or {}).get("klines") or []
            if not klines:
                return None
            rows = [k.split(",") for k in klines]
            df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low",
                                             "volume", "amount"])
            idx = pd.DatetimeIndex(pd.to_datetime(df.pop("date")), name="date")
            out = df[["open", "high", "low", "close", "volume"]].astype(float)
            out.index = idx
            out["adjclose"] = out["close"]          # fqt=1 前复权
            if _volume_shares(symbol):              # A股 手→股；港股/指数不换算
                out["volume"] = (out["volume"] * 100).astype("int64")
            else:
                out["volume"] = out["volume"].astype("int64")
            out = out[["open", "high", "low", "close", "adjclose", "volume"]]
            out = out.dropna(subset=["close"]).sort_index()
            if len(out) >= 900:
                return out
        except Exception as exc:  # noqa: BLE001
            print(f"  [eastmoney] {symbol} attempt {attempt + 1} failed: {exc}")
    return None
