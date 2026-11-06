# -*- coding: utf-8 -*-
"""交易工作台 Web UI：本地 Flask 服务。

数据来源：
  - 行情实时读 ArcticDB（/api/price/<symbol>）
  - 风险分析 / 回测 / 六库演示状态读 artifacts/*.json
启动：python -m workbench.server.app  → http://127.0.0.1:5055
"""
from __future__ import annotations

import json
import time

from flask import Flask, jsonify, request, send_from_directory

from workbench.config import (ARTIFACTS, TICKERS, active_tickers, benchmark_of, is_cn,
                              is_hk, normalize_symbol, save_custom)
from workbench.data.eastmoney import eastmoney_name
from workbench.store.arctic import load_symbol, symbol_status

app = Flask(__name__, static_folder="static", template_folder="templates")


def _json(name: str):
    p = ARTIFACTS / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@app.route("/")
def index():
    return send_from_directory(app.template_folder, "index.html")


@app.route("/api/status")
def status():
    status_doc = _json("status.json") or {}
    return jsonify({
        "libraries": status_doc.get("libraries", {}),
        "generated_at": status_doc.get("generated_at"),
        "data": symbol_status(),
    })


@app.route("/api/overview")
def overview():
    bt = (_json("backtest.json") or {})
    return jsonify({
        "analytics": _json("analytics.json"),
        "backtest_stats": {sym: {k: v.get("stats") for k, v in d.items()}
                           for sym, d in bt.get("symbols", {}).items()},
        "cost_model": bt.get("cost_model"),
        "arcticdb_demo_passed": (_json("arcticdb_demo.json") or {}).get("passed"),
        "jpm": _json("jpm_training.json") or {},
    })


@app.route("/api/price/<symbol>")
def price(symbol):
    df = load_symbol(symbol)
    weekly = df["adjclose"].resample("1W-FRI").last().dropna()
    recent = df["adjclose"].tail(120)
    return jsonify({
        "symbol": symbol,
        "weekly": [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in weekly.items()],
        "recent_daily": [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in recent.items()],
        "rows": int(len(df)),
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
        "volume_last_20d_avg": float(df["volume"].tail(20).mean()),
    })


@app.route("/api/backtest/<symbol>")
def backtest_one(symbol):
    bt = _json("backtest.json") or {}
    return jsonify(bt.get("symbols", {}).get(symbol.upper(), {}))


@app.route("/api/health")
def health():
    try:
        n = len(symbol_status())
        return jsonify({"ok": True, "symbols": n})
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── 页面添加标的（美股/A股/港股）─────────────────────────────────────────
def _pretty_market(symbol: str) -> str:
    return "CN" if is_cn(symbol) else ("HK" if is_hk(symbol) else "US")


@app.route("/api/symbols", methods=["GET"])
def list_symbols():
    return jsonify({"tickers": active_tickers(),
                    "benchmarks": {"US": "SPY", "CN": "000300.SS", "HK": "HSI.HK"}})


@app.route("/api/symbols", methods=["POST"])
def add_symbol():
    """添加标的：取五年日线 → ArcticDB → gs-quant 指标 → 带手续费回测 → 持久化。"""
    payload = request.get_json(silent=True) or {}
    market, code = str(payload.get("market", "")).strip(), str(payload.get("code", "")).strip()
    if not market or not code:
        return jsonify({"ok": False, "error": "请提供 market（US/CN/HK）和 code"}), 400
    try:
        symbol = normalize_symbol(market, code)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    if symbol in active_tickers():
        return jsonify({"ok": False, "error": f"{symbol} 已在标的池中"}), 409

    t0 = time.time()
    from workbench.data.ingest import fetch_one
    from workbench.store.arctic import write_symbol
    try:
        df, source, note = fetch_one(symbol)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"ok": False, "error": f"数据获取失败：{exc}"}), 502
    write_symbol(df, symbol, source, extra_meta={"note": note})

    # 增量计算并合并进 artifacts（供概览表/风险页/回测页即时可用）
    from workbench.demos.run_backtest_demo import backtest_symbol
    from workbench.demos.run_gs_quant_demo import analyze_symbol
    analytics = _json("analytics.json") or {}
    analytics.setdefault("symbols", {})[symbol] = analyze_symbol(symbol)
    (ARTIFACTS / "analytics.json").write_text(json.dumps(analytics, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    bt = _json("backtest.json") or {}
    bt.setdefault("symbols", {})[symbol] = backtest_symbol(symbol)
    (ARTIFACTS / "backtest.json").write_text(json.dumps(bt, ensure_ascii=False, indent=1),
                                             encoding="utf-8")

    pool = active_tickers() + [symbol]
    seen, dedup = set(), []
    for s in pool:
        if s not in seen:
            seen.add(s)
            dedup.append(s)
    save_custom([s for s in dedup if s not in TICKERS])  # 只持久化自定义部分

    name = eastmoney_name(symbol) if (is_cn(symbol) or is_hk(symbol)) else None
    return jsonify({
        "ok": True, "symbol": symbol, "name": name,
        "market": _pretty_market(symbol), "benchmark": benchmark_of(symbol),
        "source": source, "note": note, "rows": int(len(df)),
        "start": str(df.index.min().date()), "end": str(df.index.max().date()),
        "elapsed_s": round(time.time() - t0, 1),
    })


if __name__ == "__main__":
    print("MyStation 交易工作台 → http://127.0.0.1:5055")
    app.run(host="127.0.0.1", port=5055, debug=False)
