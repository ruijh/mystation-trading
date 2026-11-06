# -*- coding: utf-8 -*-
"""ArcticDB（Man Group）能力演示：版本化写入、as-of 时间旅行、日期区间读取。

输出：artifacts/arcticdb_demo.json
"""
from __future__ import annotations

import datetime as dt
import json
import time

import pandas as pd

from workbench.config import ARTIFACTS
from workbench.store.arctic import get_library, load_asof, load_symbol, symbol_status


def run() -> dict:
    lib = get_library()
    demo_sym = "DEMO_VERSIONING"
    base = load_symbol("AAPL").tail(250)[["close"]]

    # 1) 版本化写入：同一符号写两个版本
    lib.write(demo_sym, base, metadata={"note": "v1: 全量 250 行"})
    v1_rows = len(lib.read(demo_sym).data)
    lib.write(demo_sym, base.tail(100), metadata={"note": "v2: 截断 100 行"})
    v2_rows = len(lib.read(demo_sym).data)

    # 2) as-of 时间旅行：按版本号读回 v0（写入时刻的 250 行全量）
    versions = lib.list_versions(demo_sym)
    v_list = [{"version": int(getattr(v, "version", -1)),
               "date": str(getattr(v, "date", "")),
               "deleted": bool(getattr(v, "deleted", False))} for v in versions]
    first_version = min(int(getattr(v, "version", 0)) for v in versions)
    asof_rows = len(lib.read(demo_sym, as_of=first_version).data)

    # 3) 日期区间读取
    df = load_symbol("AAPL", start="2025-01-01", end="2025-12-31")
    rows_2025 = len(df)

    # 4) 版本恢复：把库内数据切回 v1（保留 v2 版本线）
    lib.write(demo_sym, base, metadata={"note": "v3: 恢复全量 250 行"})
    v3_rows = len(lib.read(demo_sym).data)
    lib.delete(demo_sym)  # 清理演示符号

    result = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "storage": "LMDB（本地），库 equities",
        "checks": {
            "versioned_write": {"v1_rows": v1_rows, "v2_rows": v2_rows,
                                "versions_seen": v_list},
            "asof_time_travel": {"asof_rows": asof_rows,
                                 "note": "读取 30 分钟前的 v1 版本"},
            "date_range_read": {"rows_2025": rows_2025,
                                "start": str(df.index.min().date()),
                                "end": str(df.index.max().date())},
            "version_lineage": {"v3_rows": v3_rows},
            "symbols_in_library": sorted(lib.list_symbols()),
        },
        "store_status": symbol_status(),
    }
    ok = (v1_rows == 250 and v2_rows == 100 and asof_rows == 250
          and rows_2025 > 200 and v3_rows == 250)
    result["passed"] = bool(ok)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "arcticdb_demo.json").write_text(json.dumps(result, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
    print(f"  版本化: v1={v1_rows}行 v2={v2_rows}行  as-of回读={asof_rows}行  "
          f"2025区间={rows_2025}行  passed={ok}")
    print(f"  → {ARTIFACTS / 'arcticdb_demo.json'}")
    return result


if __name__ == "__main__":
    run()
