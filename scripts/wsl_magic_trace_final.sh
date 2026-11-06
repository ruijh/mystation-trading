#!/usr/bin/env bash
# magic-trace 构建收尾：显式使用 5.2.0+ox switch（依赖已装好）
LOG=/mnt/e/交易桌/artifacts/logs
{
set -x
export PATH="/usr/lib/llvm-20/bin:$PATH"
eval "$(opam env --switch=5.2.0+ox 2>/dev/null)" || true
command -v dune && dune --version | head -1
cd ~/magic-trace || exit 1
dune build >"$LOG/mt_ox_build3.log" 2>&1
RC=$?
echo "DUNE_BUILD3_EXIT=$RC"
[ $RC -ne 0 ] && tail -25 "$LOG/mt_ox_build3.log"
ls -la _build/default/bin/ 2>/dev/null | head -5
./_build/default/bin/main.exe --version 2>&1 | head -2
echo MAGIC_TRACE_FINAL_DONE
} >"$LOG/mt_final.log" 2>&1
