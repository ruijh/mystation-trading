#!/usr/bin/env bash
# Jump Firedancer：拷贝到 WSL 本地盘 → deps → 构建 unit-test 目标 → 跑核心单测
LOG=/mnt/e/交易桌/artifacts/logs
mkdir -p "$LOG"
{
set -x
export DEBIAN_FRONTEND=noninteractive
cd ~ || exit 1
rm -rf ~/firedancer
mkdir -p ~/firedancer
cp -a "/mnt/e/交易桌/vendor/firedancer/." ~/firedancer/ || exit 1
cd ~/firedancer || exit 1
./deps.sh >"$LOG/fd_deps.log" 2>&1 || echo "deps.sh rc=$? (继续，缺依赖会在 make 阶段暴露)"
make -j4 unit-test >"$LOG/fd_build.log" 2>&1
RC=$?
echo "MAKE_UNIT_TEST_EXIT=$RC"
tail -30 "$LOG/fd_build.log"
echo "---unit-test binaries---"
find build -path "*unit-test*" -type f -name "test_*" 2>/dev/null | head -40
if [ $RC -eq 0 ]; then
  TESTBIN=$(find build -path "*unit-test*" -type f -name test_util | head -1)
  echo "TESTBIN=$TESTBIN"
  [ -n "$TESTBIN" ] && timeout 300 "$TESTBIN" 2>&1 | tail -15
fi
echo FIREDANCER_BUILD_DONE
} >"$LOG/fd_out.log" 2>&1
