# -*- coding: utf-8 -*-
"""交易工作台全局配置：标的、费率、路径、回测参数。

兼容性处理（Windows 中文工作区实测）：
  - curl_cffi/yfinance 无法从含非 ASCII 字符的路径加载 CA 证书 → 启动时把
    certifi 的 cacert.pem 复制到 ASCII 路径并设置 SSL_CERT_FILE
  - ArcticDB 的 LMDB 存储不支持非 ASCII 路径 → 存储默认放 ~/.trade_workbench
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
ARTIFACTS = ROOT / "artifacts"                  # 演示产物（JSON/CSV/HTML）目录
REPORTS = ROOT / "reports"

# ── ASCII 证书修复（必须在 import yfinance / requests 之前执行）──────────
_WORKBENCH_HOME = Path.home() / ".trade_workbench"


def ensure_ascii_cert() -> str | None:
    try:
        import certifi
        src = certifi.where()
        if src.isascii():
            return None
        _WORKBENCH_HOME.mkdir(parents=True, exist_ok=True)
        dst = _WORKBENCH_HOME / "cacert.pem"
        if not dst.exists() or Path(src).stat().st_size != dst.stat().st_size:
            shutil.copyfile(src, dst)
        os.environ["SSL_CERT_FILE"] = str(dst)
        return str(dst)
    except Exception:  # noqa: BLE001
        return None


CERT_PATH = ensure_ascii_cert()

# ── ArcticDB 存储（LMDB 不支持非 ASCII 路径，放 ASCII 位置，可用环境变量覆盖）
STORE_PATH = Path(os.environ.get("TRADE_WORKBENCH_STORE",
                                 str(_WORKBENCH_HOME / "arctic_store")))

# ── 标的池 ────────────────────────────────────────────────────────────────
US_TICKERS = ["AAPL", "MSFT", "NVDA", "JPM", "GS", "XOM", "TSLA"]
CN_TICKERS = [                                  # A 股：沪市 .SS / 深市 .SZ
    "600519.SS",   # 贵州茅台
    "300750.SZ",   # 宁德时代
    "601318.SS",   # 中国平安
    "000858.SZ",   # 五粮液
    "002594.SZ",   # 比亚迪
    "600556.SS",   # 天下秀
]
TICKERS = US_TICKERS + CN_TICKERS
BENCHMARKS = {"US": "SPY", "CN": "000300.SS"}   # 分市场 beta 基准
ALL_SYMBOLS = TICKERS + list(BENCHMARKS.values())
HISTORY = "5y"                                  # 五年日线


def is_cn(symbol: str) -> bool:
    """A股代码：6 位数字 + .SS/.SZ 后缀。"""
    code, _, _suffix = symbol.partition(".")
    return symbol.endswith((".SS", ".SZ")) and code.isdigit() and len(code) == 6


def benchmark_of(symbol: str) -> str:
    return BENCHMARKS["CN"] if is_cn(symbol) else BENCHMARKS["US"]

# ── 交易成本（带手续费回测）──────────────────────────────────────────────
COMMISSION_BPS = 5.0     # 单边佣金，万5
SLIPPAGE_BPS = 2.0       # 单边滑点，万2
INITIAL_CAPITAL = 100_000.0

# ── 策略参数 ─────────────────────────────────────────────────────────────
ZSCORE_WINDOW = 20       # 价格 z-score 窗口
ZSCORE_ENTRY = -1.0      # z < -1 建多（超卖回归）
ZSCORE_EXIT = 0.0        # z >= 0 平仓
SMA_FAST = 20
SMA_SLOW = 60

ANNUALIZATION = 252


def ensure_dirs() -> None:
    for d in (DATA_DIR, ARTIFACTS, REPORTS, STORE_PATH.parent):
        d.mkdir(parents=True, exist_ok=True)
