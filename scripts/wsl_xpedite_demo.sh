#!/usr/bin/env bash
# Morgan Stanley Xpedite：WSL 全流程 install.sh → build.sh → demo（record + report）
LOG=/mnt/e/交易桌/artifacts/logs
ART=/mnt/e/交易桌/artifacts
mkdir -p "$LOG" "$ART"
{
set -x
export DEBIAN_FRONTEND=noninteractive
cd ~ || exit 1
rm -rf ~/xpedite && mkdir -p ~/xpedite
cp -a "/mnt/e/交易桌/vendor/xpedite/." ~/xpedite/ || exit 1
cd ~/xpedite || exit 1
# Windows git autocrlf 把脚本转成了 CRLF，Linux 下 shebang 会坏 —— 全部转回 LF
grep -rlI $'\r' --include="*.sh" --include="*.py" . 2>/dev/null | while read -r f; do sed -i 's/\r$//' "$f"; done
grep -rlI $'\r' scripts/bin demo demo.sh install.sh build.sh 2>/dev/null | while read -r f; do sed -i 's/\r$//' "$f"; done
echo "CRLF_CLEANED"

echo "=== [1/4] install.sh（创建 venv + python 依赖）==="
./install.sh >"$LOG/xp_install.log" 2>&1
echo "INSTALL_EXIT=$?"
tail -5 "$LOG/xp_install.log"

echo "=== [1.5/4] venv 内升级 cmake + pybind11（Ubuntu 24.04 自带 cmake 3.28 < 要求的 3.31）==="
"$HOME/xpedite/install/runtime/bin/pip" install -q "cmake>=3.31" pybind11 >>"$LOG/xp_cmake.log" 2>&1
export PATH="$HOME/xpedite/install/runtime/bin:$PATH"
cmake --version | head -1
export CMAKE_PREFIX_PATH="$("$HOME/xpedite/install/runtime/bin/python" -c "import pybind11; print(pybind11.get_cmake_dir())")"
echo "CMAKE_PREFIX_PATH=$CMAKE_PREFIX_PATH"

echo "=== [2/4] build.sh（cmake 构建 xpediteDemo）==="
./build.sh >"$LOG/xp_build.log" 2>&1
echo "BUILD_EXIT=$?"
ls -la install/bin/ 2>/dev/null | head -8
tail -8 "$LOG/xp_build.log"

echo "=== [3/4] demo.sh（启动 demo app + xpedite record）==="
timeout 180 ./demo/demo.sh >"$LOG/xp_demo.log" 2>&1
echo "DEMO_EXIT=$?"
tail -30 "$LOG/xp_demo.log"

echo "=== [4/4] report 生成 ==="
PROFILE_DIR=$(find /tmp -maxdepth 2 -type d -name "Profile*" 2>/dev/null | head -1)
echo "PROFILE_DIR=$PROFILE_DIR"
if [ -n "$PROFILE_DIR" ]; then
  ls "$PROFILE_DIR" | head -10
  eval "$(~/xpedite/install/runtime/bin/python -V >/dev/null 2>&1; echo '')"
  export PATH="$HOME/xpedite/install/runtime/bin:$HOME/xpedite/scripts/bin:$PATH"
  timeout 120 xpedite report -p "$PROFILE_DIR" >"$LOG/xp_report.log" 2>&1
  echo "REPORT_EXIT=$?"
  tail -20 "$LOG/xp_report.log"
  cp "$PROFILE_DIR/report"* "$ART/" 2>/dev/null || true
fi
echo XPEDITE_DEMO_DONE
} >"$LOG/xp_out.log" 2>&1
