# -*- coding: utf-8 -*-
"""静态站点导出器：把工作台导出为 GitHub Pages 可托管的纯静态站。

原理：UI（index.html）已支持 window.MYSTATION_STATIC 静态模式——fetch(/api/x)
改走 data/x.json。本脚本把 Flask 各 API 的响应结构原样落成 JSON 文件：

  docs/
    index.html          （注入静态标志的 UI）
    .nojekyll           （跳过 Jekyll 处理）
    data/overview.json      （= /api/overview）
    data/status.json        （= /api/status）
    data/price/<SYM>.json   （= /api/price/<SYM>）
    data/backtest/<SYM>.json（= /api/backtest/<SYM>）

输出后可本地 `python -m http.server` 预览，或推送后由 Pages 托管
（GitHub Pages legacy 构建仅支持根目录或 /docs 路径，故输出到 docs/）。
注意：静态站是导出时刻的数据快照，不随 ArcticDB 实时更新。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from workbench.config import ARTIFACTS, ROOT
from workbench.server.app import _json  # noqa: F401 —— 复用 Flask 端的 JSON 读取
from workbench.store.arctic import load_symbol, symbol_status

SITE_DIR = ROOT / "docs"


def _price_payload(symbol: str) -> dict:
    df = load_symbol(symbol)
    weekly = df["adjclose"].resample("1W-FRI").last().dropna()
    recent = df["adjclose"].tail(120)
    return {
        "symbol": symbol,
        "weekly": [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in weekly.items()],
        "recent_daily": [[int(ts.timestamp() * 1000), round(float(v), 2)] for ts, v in recent.items()],
        "rows": int(len(df)),
        "start": str(df.index.min().date()),
        "end": str(df.index.max().date()),
        "volume_last_20d_avg": float(df["volume"].tail(20).mean()),
    }


def _overview_payload() -> dict:
    bt = _json("backtest.json") or {}
    return {
        "analytics": _json("analytics.json"),
        "backtest_stats": {sym: {k: v.get("stats") for k, v in d.items()}
                           for sym, d in bt.get("symbols", {}).items()},
        "cost_model": bt.get("cost_model"),
        "arcticdb_demo_passed": (_json("arcticdb_demo.json") or {}).get("passed"),
        "jpm": _json("jpm_training.json") or {},
    }


def export(out_dir: Path = SITE_DIR) -> Path:
    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "data" / "price").mkdir(parents=True)
    (out_dir / "data" / "backtest").mkdir(parents=True)
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")

    # index.html：注入静态标志（模板里只有一处 <script> 主块）
    html = (ROOT / "workbench" / "server" / "templates" / "index.html").read_text(encoding="utf-8")
    html = html.replace("<script>", "<script>window.MYSTATION_STATIC=true;</script>\n<script>", 1)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    status = {
        "libraries": (_json("status.json") or {}).get("libraries", {}),
        "generated_at": (_json("status.json") or {}).get("generated_at"),
        "data": symbol_status(),
    }
    (out_dir / "data" / "overview.json").write_text(
        json.dumps(_overview_payload(), ensure_ascii=False), encoding="utf-8")
    (out_dir / "data" / "status.json").write_text(
        json.dumps(status, ensure_ascii=False), encoding="utf-8")

    symbols = sorted(((_json("analytics.json") or {}).get("symbols") or {}))
    bt_all = (_json("backtest.json") or {}).get("symbols", {})
    for sym in symbols:
        (out_dir / "data" / "price" / f"{sym}.json").write_text(
            json.dumps(_price_payload(sym), ensure_ascii=False), encoding="utf-8")
        (out_dir / "data" / "backtest" / f"{sym}.json").write_text(
            json.dumps(bt_all.get(sym, {}), ensure_ascii=False), encoding="utf-8")

    n = 2 + len(symbols) * 2
    print(f"→ {out_dir}  （index.html + {n} 个 JSON，覆盖 {len(symbols)} 只标的）")
    return out_dir


if __name__ == "__main__":
    export()
