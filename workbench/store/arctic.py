# -*- coding: utf-8 -*-
"""ArcticDB（Man Group）封装：LMDB 本地存储的行情库。

演示能力：库管理、符号写入、版本化、日期区间读取、as-of 读取。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
from arcticdb import Arctic

from workbench.config import STORE_PATH, ensure_dirs

LIB_NAME = "equities"


def get_arctic() -> Arctic:
    ensure_dirs()
    return Arctic(f"lmdb://{STORE_PATH}")


def get_library():
    arctic = get_arctic()
    if LIB_NAME not in arctic.list_libraries():
        arctic.create_library(LIB_NAME)
    return arctic[LIB_NAME]


def write_symbol(df: pd.DataFrame, symbol: str, source: str, extra_meta: dict | None = None) -> None:
    """写入/覆盖一个符号的日线数据，附带来源元数据（ArcticDB 版本化保留历史）。"""
    lib = get_library()
    meta = {
        "source": source,
        "ingested_at": dt.datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(df)),
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
    }
    if extra_meta:
        meta.update(extra_meta)
    lib.write(symbol, df, metadata=meta)


def load_symbol(symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame:
    lib = get_library()
    date_range = (pd.Timestamp(start), pd.Timestamp(end)) if start and end else None
    return lib.read(symbol, date_range=date_range).data


def load_asof(symbol: str, asof: dt.datetime) -> pd.DataFrame:
    """as-of 读取：取 asof 时间点之前的最新版本（时间旅行能力演示）。"""
    return get_library().read(symbol, as_of=asof).data


def symbol_status() -> dict:
    """列出全部符号及其元数据/版本数，用于工作台状态页。"""
    lib = get_library()
    out = {}
    for sym in lib.list_symbols():
        try:
            versions = lib.list_versions(sym)
            latest = [v for v in versions if not getattr(v, "deleted", False)]
            meta = lib.read_metadata(sym).metadata or {}
            out[sym] = {
                "rows": meta.get("rows"),
                "source": meta.get("source"),
                "start": meta.get("start"),
                "end": meta.get("end"),
                "ingested_at": meta.get("ingested_at"),
                "versions": len(latest),
            }
        except Exception as exc:  # noqa: BLE001
            out[sym] = {"error": str(exc)}
    return out
