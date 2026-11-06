# MyStation —— 华尔街六库交易工作台

一个**能跑、能演示**的本地交易工作台，把六家华尔街机构的开源库串成一条真实数据管道：

```
yfinance 五年日线（真实数据）
        │
        ▼
┌─────────────────┐     ┌──────────────────────────┐     ┌──────────────────────┐
│ ArcticDB (Man)  │ ──▶ │ gs-quant (Goldman Sachs) │ ──▶ │  带手续费回测引擎     │
│ LMDB 版本化落库  │     │ 波动 / 回撤 / z-score / β │     │  佣金万5 + 滑点万2    │
└─────────────────┘     └──────────────────────────┘     └──────────────────────┘
        │                                                        │
        ▼                                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                Flask 工作台 UI  →  http://127.0.0.1:5055                 │
└─────────────────────────────────────────────────────────────────────────┘

旁路演示（WSL2 Ubuntu）：
  JPMorgan python-training 官方笔记本（nbclient 无头执行）
  Jump Firedancer          单元测试构建 + 运行
  Morgan Stanley Xpedite   demo app → record → report 全流程
  Jane Street magic-trace  源码构建 + perf-script fixture 解码
```

## 快速开始

```bash
cd E:\交易桌
# 1) 一键全量跑（首次会拉取行情，之后跳过）
.venv\Scripts\python.exe -X utf8 -m workbench.run_all

# 2) 启动工作台 UI
.venv\Scripts\python.exe -X utf8 -m workbench.server.app
# 打开 http://127.0.0.1:5055
```

## 分模块演示

| 模块 | 命令 | 产物 |
|---|---|---|
| 数据落库 | `python -m workbench.data.ingest` | ArcticDB `equities` 库（8 符号×~1255 行） |
| ArcticDB 能力 | `python -m workbench.demos.run_arcticdb_demo` | artifacts/arcticdb_demo.json |
| gs-quant 分析 | `python -m workbench.demos.run_gs_quant_demo` | artifacts/analytics.json |
| 手续费回测 | `python -m workbench.demos.run_backtest_demo` | artifacts/backtest.json |
| JPM 笔记本 | `python -m workbench.demos.run_jpm_training` | artifacts/jpm_training.json |
| 六库状态汇总 | `python -m workbench.run_all`（末步） | artifacts/status.json |

WSL 侧（Ubuntu 24.04，需 `wsl -d MiniStation`）：

| 模块 | 命令 | 产物 |
|---|---|---|
| Firedancer | `bash scripts/wsl_firedancer_build.sh`（root） | artifacts/firedancer.json |
| Xpedite | `bash scripts/wsl_xpedite_demo.sh`（root） | artifacts/xpedite.json |
| magic-trace | `bash scripts/wsl_magic_trace_build.sh`（root） | artifacts/magic_trace.json |

## 各库演示要点

1. **ArcticDB（Man Group）** — `lmdb://~/.trade_workbench/arctic_store`（LMDB 不支持非 ASCII 路径，故放用户目录）。演示：同一符号多版本写入、`read(as_of=版本号)` 时间旅行、日期区间读取、版本元数据（来源/新鲜度）。
2. **gs-quant（Goldman Sachs）** — 全部用 GS 开源库原生函数（`timeseries.econometrics` 的 `volatility/beta/max_drawdown` + `timeseries.statistics` 的 `zscores`），离线即可跑，不需要 GS API 凭据。口径经 pandas 基准校准：`volatility` 输出为百分数（×100）；`beta(prices=True)` 与 pandas rolling cov/var 一致；`sharpe_ratio` 需 GS 无风险曲线（API），工作台用「零利率 + gs-quant 波动率」近似并注明。
3. **python-training（JPMorgan）** — `vendor/python-training` 官方仓库，nbclient + ipykernel 无头执行 4 个笔记本；唯一的 compat：`2_straddle` 中 2019 版 perspective 的 `psp()` 预览 API 已被上游移除，shim 成返回 DataFrame（透明记录在 jpm_training.json 的 compat_patches）。
4. **Firedancer（Jump）** — Linux/Solana 全节点软件，Windows 上经由 WSL2 构建 `make unit-test`（80+ 测试目标）并运行 8 个代表性单元测试（test_util/bmtree/sha256/aes/cstr/alloc/tpool/hex）全部通过。
5. **Xpedite（Morgan Stanley）** — WSL2 全流程：`install.sh`（venv）→ `build.sh`（cmake 构建 xpediteDemo）→ `demo/demo.sh`（启动 demo app + `xpedite record` 采集）→ `xpedite report` 生成报告。
6. **magic-trace（Jane Street）** — 无官方 release，WSL2 按**上游 debian/rules 的官方 CI 配方**从源码构建：OxCaml `5.2.0+ox` 编译器（pinned oxcaml opam-repository）+ llvm-20 + Jane Street v0.18~preview 全家桶，`dune build` exit=0，产出 `magic_trace_bin.exe`（attach/decode/run 三子命令）。核心演示：`demo_decode/mt_decode_demo.exe`（本工作台补充的解码驱动，复用与官方测试套件相同的 `Perf_decode` 管线）把 Jane Street 真实捕获的 `test/*.perf` fixture 解码成**纳秒级函数时间线**，输出存档 `artifacts/magic_trace_demo.txt`。Intel PT 实时采集需要裸机 Intel Skylake+（虚拟机不支持，上游 README 亦注明），WSL 下 live run 报错已留档。

## 真实数据

- **美股**（AAPL/MSFT/NVDA/JPM/GS/XOM/TSLA + 基准 SPY）：yfinance 真实日线，约 1253 行/只，含复权收盘价。
- **A股**（600519/300750/601318/000858/002594/600556 + 基准 000300）：东方财富公开 API 前复权日线，1215 行/只。
- **降级链**（`workbench/data/ingest.py::fetch_one`，来源标记进 ArcticDB 元数据，UI 数据源徽标可见）：
  - A股：东财直连 → akshare（前复权，锁版本 1.20.34）→ GBM 模拟
  - 美股：yfinance → akshare（东财源，市场前缀 105/106/107 自动试探）→ Stooq → GBM 模拟
  - 兜底与主源同源（akshare 封装东财接口），逐行一致性已验证（close 最大差 0.000000）。

## 回测口径（带手续费）

- 成本模型：每次调仓按 `|Δ仓位| × 收盘价` 计名义额，**佣金万 5 + 滑点万 2，单边收取**；仓位 0/1（满仓进出）简化假设。
- 指标：毛/净收益、净夏普、净最大回撤、交易次数、持仓暴露、**费用拖累**（毛收益 − 净收益）。
- 策略：z-score 均值回归（z<−1 建多，z≥0 平仓）与双均线趋势（SMA20/60）对比。
