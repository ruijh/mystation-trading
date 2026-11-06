#!/usr/bin/env bash
# Jane Street magic-trace：无官方 release → opam 从源码构建
LOG=/mnt/e/交易桌/artifacts/logs
mkdir -p "$LOG"
{
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq opam libev-dev pkg-config m4 unzip >>"$LOG/mt_apt.log" 2>&1 || echo "apt rc=$?"
opam init -y --disable-sandboxing -j3 >"$LOG/mt_opam_init.log" 2>&1 || echo "opam init rc=$?"
eval "$(opam env 2>/dev/null)" || true
rm -rf ~/magic-trace && mkdir -p ~/magic-trace
cp -a "/mnt/e/交易桌/vendor/magic-trace/." ~/magic-trace/ || exit 1
cd ~/magic-trace || exit 1
opam install -y -j3 . >"$LOG/mt_opam_install.log" 2>&1
RC=$?
echo "OPAM_INSTALL_EXIT=$RC"
tail -25 "$LOG/mt_opam_install.log"
eval "$(opam env 2>/dev/null)" || true
command -v magic-trace && magic-trace --version 2>&1 | head -2
echo MAGIC_TRACE_BUILD_DONE
} >"$LOG/mt_out.log" 2>&1
