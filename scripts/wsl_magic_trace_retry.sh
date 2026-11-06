#!/usr/bin/env bash
# magic-trace 重试：补系统依赖 + --assume-depexts 跳过 depext 交互
LOG=/mnt/e/交易桌/artifacts/logs
mkdir -p "$LOG"
{
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq libzstd-dev libev-dev pkg-config m4 unzip >>"$LOG/mt_apt.log" 2>&1 || echo "apt rc=$?"
eval "$(opam env 2>/dev/null)" || true
cd ~/magic-trace || exit 1
opam install -y --assume-depexts -j3 . >"$LOG/mt_opam_install2.log" 2>&1
RC=$?
echo "OPAM_INSTALL2_EXIT=$RC"
tail -20 "$LOG/mt_opam_install2.log"
eval "$(opam env 2>/dev/null)" || true
command -v magic-trace && magic-trace --version 2>&1 | head -2
echo MAGIC_TRACE_RETRY_DONE
} >"$LOG/mt_out2.log" 2>&1
