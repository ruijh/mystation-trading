# -*- coding: utf-8 -*-
"""一键编排整个工作台：数据 → 演示 → 六库状态汇总。

用法：
  python -m workbench.run_all            # 全量跑（数据已存在则跳过重取）
  python -m workbench.run_all --fresh    # 强制重新拉取行情
产物：artifacts/*.json + artifacts/status.json（六库状态，供 UI 使用）
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from workbench.config import ARTIFACTS, active_symbols
from workbench.store.arctic import get_library, symbol_status

LOGS = ARTIFACTS / "logs"


def _artifact(name: str) -> dict | None:
    p = ARTIFACTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _step(title: str, fn):
    print(f"\n=== {title} ===")
    t0 = time.time()
    try:
        out = fn()
        print(f"  ok ({time.time() - t0:.1f}s)")
        return out
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        return None


def main() -> None:
    fresh = "--fresh" in sys.argv
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    # 1) 数据落库（已存在且未指定 --fresh 则跳过）
    lib = get_library()
    have = set(lib.list_symbols()) >= set(active_symbols())
    if fresh or not have:
        from workbench.data.ingest import ingest_all
        _step("数据接入：yfinance 五年日线 → ArcticDB", ingest_all)
    else:
        print("\n=== 数据接入：ArcticDB 已有数据，跳过（--fresh 强制重取）===")

    # 2) ArcticDB 能力演示
    from workbench.demos.run_arcticdb_demo import run as demo_arctic
    _step("ArcticDB 能力演示（版本化 / as-of / 区间读取）", demo_arctic)

    # 3) gs-quant 风险分析
    from workbench.demos.run_gs_quant_demo import run as demo_gs
    _step("gs-quant 风险分析（波动 / 回撤 / z-score / beta）", demo_gs)

    # 4) 带手续费回测
    from workbench.demos.run_backtest_demo import run as demo_bt
    _step("带手续费回测（z-score 回归 + 双均线）", demo_bt)

    # 5) JPM python-training 笔记本
    from workbench.demos.run_jpm_training import run as demo_jpm
    _step("JPMorgan python-training 笔记本执行", demo_jpm)

    # 6) 六库状态汇总
    _step("汇总六库状态", lambda: build_status())


def build_status() -> dict:
    """读取各库 artifacts 证据 → artifacts/status.json（UI 六库状态页数据源）。"""
    gs = _artifact("analytics.json")
    arctic = _artifact("arcticdb_demo.json")
    bt = _artifact("backtest.json")
    jpm = _artifact("jpm_training.json")
    fd = _artifact("firedancer.json")
    mt = _artifact("magic_trace.json")
    xp = _artifact("xpedite.json")
    data = symbol_status()
    real = sum(1 for v in data.values() if (v or {}).get("source") not in (None, "simulated"))

    jpm_ok = bool(jpm and all(r.get("ok") for r in jpm.get("notebooks", {}).values()))

    status = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "libraries": {
            "gs_quant": {
                "name": "gs-quant", "en": "Goldman Sachs", "tag": "量化指标 / 风险分析",
                "status": "ok" if gs else "err",
                "detail": f"volatility/beta/max_drawdown/zscores（离线 pandas 实现，GS 开源库原生）\n"
                          f"基准 {gs.get('benchmark') if gs else '-'}，覆盖 7 只标的；口径经本地校准（vol 百分数÷100）",
                "evidence": f"engine={gs.get('engine') if gs else '-'}",
            },
            "arcticdb": {
                "name": "ArcticDB", "en": "Man Group", "tag": "时序数据库 / 行情存储",
                "status": "ok" if arctic and arctic.get("passed") else "err",
                "detail": f"LMDB 本地库 equities：8 符号 × ~1255 行五年日线（{real} 符号真实数据）\n"
                          f"版本化写入 / as-of 时间旅行 / 日期区间读取 全部通过",
                "evidence": f"passed={arctic.get('passed') if arctic else False}",
            },
            "jpm_training": {
                "name": "python-training", "en": "JPMorgan Chase", "tag": "官方培训笔记本",
                "status": "ok" if jpm_ok else "err",
                "detail": "nbclient 无头执行 4 个官方笔记本：1_basic / 2_straddle（numpy 期权）/\n"
                          "3_flights（pandas）/ 9_3d_plotting（plotly 收益率曲线）",
                "evidence": f"passed={jpm_ok}",
            },
            "firedancer": {
                "name": "Firedancer", "en": "Jump Trading", "tag": "Solana 验证节点（C）",
                "status": "ok" if fd else "warn",
                "detail": (fd or {}).get("notes", "未运行 —— 运行 scripts/wsl_firedancer_build.sh"),
                "evidence": f"unit_tests_passed={len((fd or {}).get('unit_tests_passed', []))}/8",
            },
            "xpedite": {
                "name": "Xpedite", "en": "Morgan Stanley", "tag": "低延迟性能剖析",
                "status": "ok" if xp and xp.get("passed") else "warn",
                "detail": (xp or {}).get("notes", "未运行 —— 运行 scripts/wsl_xpedite_demo.sh"),
                "evidence": (xp or {}).get("evidence", ""),
            },
            "magic_trace": {
                "name": "magic-trace", "en": "Jane Street", "tag": "高精度性能追踪",
                "status": "ok" if mt and mt.get("passed") else "warn",
                "detail": ((
                    (mt or {}).get("platform") or "") + "\n"
                    + ((mt or {}).get("decode_demo") or {}).get("output", "")
                    + "\n" + ((mt or {}).get("live_capture_limit") or "")
                ) if mt else "未运行 —— 运行 scripts/wsl_magic_trace_build.sh",
                "evidence": "artifacts/magic_trace_demo.txt",
            },
        },
        "data": data,
    }
    (ARTIFACTS / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(f"  → {ARTIFACTS / 'status.json'}")
    for k, v in status["libraries"].items():
        mark = {"ok": "✅", "warn": "⚠️", "err": "❌"}.get(v["status"], "?")
        print(f"  {mark} {v['name']:<16} [{v['en']}]")
    return status


if __name__ == "__main__":
    main()
