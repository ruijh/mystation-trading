#!/usr/bin/env bash
# magic-trace：按上游 debian/rules 的官方配方构建（OxCaml 5.2.0+ox + pinned opam repo）
LOG=/mnt/e/交易桌/artifacts/logs
{
set -x
export DEBIAN_FRONTEND=noninteractive
export PATH="/usr/lib/llvm-18/bin:$PATH"
cd ~/magic-trace || exit 1
opam switch create -y 5.2.0+ox --repos "ox=git+https://github.com/oxcaml/opam-repository.git#231c88c2e564fdca40e15e750aacad5fb0887435,default" >"$LOG/mt_ox_switch.log" 2>&1
RC=$?
echo "SWITCH_EXIT=$RC"
[ $RC -ne 0 ] && tail -15 "$LOG/mt_ox_switch.log"
eval "$(opam env 2>/dev/null)" || true
opam install -y --assume-depexts -j3 . --deps-only >"$LOG/mt_ox_deps.log" 2>&1
RC=$?
echo "DEPS_EXIT=$RC"
[ $RC -ne 0 ] && grep -iE "error|failure" "$LOG/mt_ox_deps.log" | tail -8
eval "$(opam env 2>/dev/null)" || true
dune build >"$LOG/mt_ox_build.log" 2>&1
RC=$?
echo "DUNE_BUILD_EXIT=$RC"
[ $RC -ne 0 ] && tail -20 "$LOG/mt_ox_build.log"
ls -la _build/default/bin/ 2>/dev/null | head
./_build/default/bin/main.exe --version 2>&1 | head -2
echo MAGIC_TRACE_OX_DONE
} >"$LOG/mt_ox_out.log" 2>&1
