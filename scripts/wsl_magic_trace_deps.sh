#!/usr/bin/env bash
# magic-trace：在 5.2.0+ox switch 上显式安装依赖并构建（--switch 全程显式）
LOG=/mnt/e/交易桌/artifacts/logs
{
set -x
export PATH="/usr/lib/llvm-20/bin:$PATH"
opam switch set 5.2.0+ox 2>/dev/null || true
cd ~/magic-trace || exit 1
opam install --switch=5.2.0+ox -y --assume-depexts -j3 . --deps-only >"$LOG/mt_deps3.log" 2>&1
RC=$?
echo "DEPS3_EXIT=$RC"
[ $RC -ne 0 ] && grep -iE "^# Error|failure|Error:" "$LOG/mt_deps3.log" | tail -8
opam exec --switch=5.2.0+ox -- dune --version
opam exec --switch=5.2.0+ox -- dune build >"$LOG/mt_ox_build4.log" 2>&1
RC=$?
echo "DUNE_BUILD4_EXIT=$RC"
[ $RC -ne 0 ] && tail -25 "$LOG/mt_ox_build4.log"
ls -la _build/default/bin/ 2>/dev/null | head -5
./_build/default/bin/main.exe --version 2>&1 | head -2
echo MAGIC_TRACE_DEPS_BUILD_DONE
} >"$LOG/mt_deps_out.log" 2>&1
