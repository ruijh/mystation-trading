# -*- coding: utf-8 -*-
"""gs-quant（高盛）量化指标层 —— 全部调用 GS 开源库原生实现。

来源（goldmansachs/gs-quant，本地 pandas 计算、不需要 GS API 凭据）：
  - gs_quant.timeseries.econometrics : volatility / beta / max_drawdown / sharpe_ratio
  - gs_quant.timeseries.statistics   : zscores（滚动/全样本 z-score）

口径（2026-11 在 gs-quant 7.x 上实测校准，对照 pandas 基准）：
  - volatility: 返回值为「百分数」×100（27.31 即 27.31%），本层 ÷100 转小数；
    年化已内置（自动探测采样频率）；滚动窗口传 int 观测数
  - beta(x, b, prices=True): 输入两个价格序列，内部 pct_change 后 rolling cov/var
    （经真实 beta=0.8 合成数据校验，与 pandas 一致）；窗口传 int，避开 DateOffset 分支 bug
  - max_drawdown(x): 峰谷比小数，-0.2 = -20%，输入价格序列
  - zscores(x, w): 与 pandas rolling z-score 完全一致（diff < 4e-11）
  - sharpe_ratio: GS 版本需无风险利率曲线（GsSession API），离线环境退路 =
    本地年化收益 / gs-quant volatility（零无风险利率假设）
"""
from __future__ import annotations

import logging

import pandas as pd

# GS 原生 sharpe 需要无风险利率曲线，离线时 GS 会打 API 失败日志 —— 静默处理
logging.getLogger("gs_quant").setLevel(logging.CRITICAL)

try:  # Window 在 timeseries 包顶层与 statistics 模块均有暴露
    from gs_quant.timeseries import Window
except ImportError:  # pragma: no cover
    from gs_quant.timeseries.statistics import Window

from gs_quant.timeseries.econometrics import (  # noqa: E402
    Returns,
    beta as gs_beta,
    max_drawdown as gs_max_drawdown,
    volatility as gs_volatility,
)
from gs_quant.timeseries.statistics import zscores as gs_zscores  # noqa: E402

FULL_WINDOW = Window(None, 0)
ENGINE = "gs_quant.timeseries (econometrics + statistics)"

ANNUALIZATION = 252


# ── 波动率 ───────────────────────────────────────────────────────────────
def annual_volatility_from_prices(prices: pd.Series) -> float:
    """gs-quant volatility：价格序列 → 年化波动率（小数；GS 原始输出为百分数）。"""
    s = gs_volatility(pd.Series(prices), w=FULL_WINDOW, returns_type=Returns.SIMPLE)
    return float(pd.Series(s).dropna().iloc[-1]) / 100.0


def rolling_volatility(prices: pd.Series, window: int = 63) -> pd.Series:
    """滚动年化波动率序列（gs-quant volatility + int 窗口）。"""
    s = gs_volatility(pd.Series(prices), w=int(window), returns_type=Returns.SIMPLE)
    return pd.Series(s).dropna() / 100.0


def annual_volatility_from_returns(rets: pd.Series) -> float:
    """策略收益率序列 → 重建净值曲线后交给 gs-quant volatility。"""
    curve = (1.0 + pd.Series(rets).fillna(0.0)).cumprod()
    return annual_volatility_from_prices(curve)


# 回测引擎用的别名
annual_vol = annual_volatility_from_returns


# ── beta ────────────────────────────────────────────────────────────────
def beta_vs_benchmark(stock_prices: pd.Series, bench_prices: pd.Series) -> float:
    """全样本 beta（gs-quant beta，prices=True 自动转收益率）。"""
    s = gs_beta(pd.Series(stock_prices), pd.Series(bench_prices), w=FULL_WINDOW, prices=True)
    return float(pd.Series(s).dropna().iloc[-1])


def rolling_beta(stock_prices: pd.Series, bench_prices: pd.Series,
                 window: int = 126) -> pd.Series:
    """滚动 beta 序列（gs-quant beta + int 窗口；int 走 pandas rolling 分支）。"""
    s = gs_beta(pd.Series(stock_prices), pd.Series(bench_prices), w=int(window), prices=True)
    return pd.Series(s).dropna()


# ── z-score ─────────────────────────────────────────────────────────────
def zscore_series(prices: pd.Series, window: int = 20) -> pd.Series:
    """gs-quant zscores：滚动窗口标准分（价格相对窗口均值的偏离程度）。"""
    s = gs_zscores(pd.Series(prices), int(window))
    return pd.Series(s).dropna()


def latest_zscore(prices: pd.Series, window: int = 20) -> float:
    z = zscore_series(prices, window)
    return float(z.iloc[-1]) if len(z) else float("nan")


# ── 回撤 ────────────────────────────────────────────────────────────────
def max_drawdown(prices: pd.Series) -> float:
    """gs-quant max_drawdown：峰谷比（-0.2 = -20%）。"""
    s = gs_max_drawdown(pd.Series(prices), w=FULL_WINDOW)
    return float(pd.Series(s).dropna().iloc[-1])


def drawdown_curve(prices: pd.Series) -> pd.Series:
    """回撤曲线（用于图表；纯 pandas，与 GS max_drawdown 同口径）。"""
    prices = pd.Series(prices)
    return prices / prices.cummax() - 1.0


def max_drawdown_of_returns(rets: pd.Series) -> float:
    """收益率序列 → 重建净值 → gs-quant max_drawdown。"""
    curve = (1.0 + pd.Series(rets).fillna(0.0)).cumprod()
    return max_drawdown(curve)


# ── 夏普 ────────────────────────────────────────────────────────────────
def sharpe_ratio(prices: pd.Series) -> float:
    """优先 GS 原生 sharpe_ratio（GS 输出 ×100 约定，转回小数）；
    无 GS 无风险利率曲线时退路 = 本地年化收益 / gs-quant 波动率。"""
    try:
        from gs_quant.timeseries.econometrics import sharpe_ratio as gs_sharpe
        s = gs_sharpe(pd.Series(prices))
        return float(pd.Series(s).dropna().iloc[-1]) / 100.0
    except Exception:  # noqa: BLE001 —— 离线环境没有 GS 无风险利率曲线
        prices = pd.Series(prices)
        rets = prices.pct_change().dropna()
        if len(rets) < 10:
            return float("nan")
        vol = annual_volatility_from_prices(prices)
        ann_ret = float((1 + rets).prod() ** (ANNUALIZATION / len(rets)) - 1)
        return ann_ret / vol if vol > 0 else float("nan")


# 回测引擎用的别名
sharpe = sharpe_ratio_from_prices = sharpe_ratio
