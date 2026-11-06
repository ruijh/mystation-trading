#!/usr/bin/env bash
# magic-trace 第三轮：补 llvm-dev 后重装（依赖已缓存，只重编 magic-trace 本体）
LOG=/mnt/e/交易桌/artifacts/logs
{
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq llvm-dev clang >>"$LOG/mt_apt.log" 2>&1 || echo "apt rc=$?"
eval "$(opam env 2>/dev/null)" || true
cd ~/magic-trace || exit 1
opam install -y --assume-depexts -j3 . >"$LOG/mt_opam_install3.log" 2>&1
RC=$?
echo "OPAM_INSTALL3_EXIT=$RC"
grep -iE "error|failure" "$LOG/mt_opam_install3.log" | tail -6
eval "$(opam env 2>/dev/null)" || true
command -v magic-trace && magic-trace --version 2>&1 | head -2
echo MAGIC_TRACE_RETRY3_DONE
} >"$LOG/mt_out3.log" 2>&1
