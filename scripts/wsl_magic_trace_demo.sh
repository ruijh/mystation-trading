#!/usr/bin/env bash
# magic-trace 演示：版本 + perf-script 解码测试套件（13 个真实捕获 fixture）+ PT 限制记录
LOG=/mnt/e/交易桌/artifacts/logs
ART=/mnt/e/交易桌/artifacts
{
set -x
eval "$(opam env 2>/dev/null)" || true
cd ~/magic-trace || exit 1
MT=_build/default/bin/main.exe
echo "=== magic-trace --version ==="
$MT --version 2>&1 | head -2
echo "=== perf-script 解码测试（Jane Street 官方 fixture 回归）==="
dune runtest test/ >"$LOG/mt_runtest.log" 2>&1
RC=$?
echo "RUNTEST_EXIT=$RC"
tail -5 "$LOG/mt_runtest.log"
echo "=== live PT 采集限制（诚实记录，虚拟机不支持 Intel PT）==="
timeout 60 $MT run -- /bin/echo hello >"$LOG/mt_live.log" 2>&1
echo "LIVE_EXIT=$?"
tail -6 "$LOG/mt_live.log"
echo "=== fixture 样例（真实 perf script 输入）==="
head -3 test/hello_world_userspace.perf
echo MAGIC_TRACE_DEMO_DONE
} >"$LOG/mt_demo.log" 2>&1
