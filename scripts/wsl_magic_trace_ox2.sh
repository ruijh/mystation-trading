#!/usr/bin/env bash
# magic-trace 最终构建：完全对齐上游 debian/rules CI 配方
# llvm-20 + autoconf + OxCaml 5.2.0+ox（pinned opam repo）
LOG=/mnt/e/交易桌/artifacts/logs
{
set -x
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -qq autoconf llvm-20 llvm-20-dev lld >>"$LOG/mt_apt.log" 2>&1 || echo "apt rc=$?"
export PATH="/usr/lib/llvm-20/bin:$PATH"
llvm-config --version 2>/dev/null || /usr/lib/llvm-20/bin/llvm-config --version
opam switch remove -y 5.2.0+ox >/dev/null 2>&1 || true
opam switch create -y --assume-depexts 5.2.0+ox --repos "ox=git+https://github.com/oxcaml/opam-repository.git#231c88c2e564fdca40e15e750aacad5fb0887435,default" >"$LOG/mt_ox_switch2.log" 2>&1
RC=$?
echo "SWITCH_EXIT=$RC"
[ $RC -ne 0 ] && tail -10 "$LOG/mt_ox_switch2.log"
eval "$(opam env 2>/dev/null)" || true
opam install -y --assume-depexts -j3 . --deps-only >"$LOG/mt_ox_deps2.log" 2>&1
RC=$?
echo "DEPS_EXIT=$RC"
[ $RC -ne 0 ] && grep -iE "^# Error|failure" "$LOG/mt_ox_deps2.log" | tail -8
eval "$(opam env 2>/dev/null)" || true
dune build >"$LOG/mt_ox_build2.log" 2>&1
RC=$?
echo "DUNE_BUILD_EXIT=$RC"
[ $RC -ne 0 ] && tail -20 "$LOG/mt_ox_build2.log"
ls -la _build/default/bin/ 2>/dev/null | head -5
./_build/default/bin/main.exe --version 2>&1 | head -2
echo MAGIC_TRACE_OX2_DONE
} >"$LOG/mt_ox_out2.log" 2>&1
