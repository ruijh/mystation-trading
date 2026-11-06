# -*- coding: utf-8 -*-
"""交易工作台 Web UI：本地 Flask 服务。

数据来源：
  - 行情实时读 ArcticDB（/api/price/<symbol>）
  - 风险分析 / 回测 / 六库演示状态读 artifacts/*.json
启动：python -m workbench.server.app  → http://127.0.0.1:5055
"""
from __future__ import annotations

import json

from flask import Flask, jsonify, send_from_directory

from workbench.config import ARTIFACTS
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


if __name__ == "__main__":
    print("MyStation 交易工作台 → http://127.0.0.1:5055")
    app.run(host="127.0.0.1", port=5055, debug=False)
