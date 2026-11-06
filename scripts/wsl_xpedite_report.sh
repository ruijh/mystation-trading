#!/usr/bin/env bash
# Xpedite 证据落盘：用官方命令重新生成 report，拷贝到 artifacts
LOG=/mnt/e/交易桌/artifacts/logs
ART=/mnt/e/交易桌/artifacts
{
set -x
export PATH="$HOME/xpedite/install/runtime/bin:$HOME/xpedite/scripts/bin:$PATH"
cd ~/xpedite || exit 1
echo "=== xpedite cpuInfo（工具自检）==="
xpedite cpuInfo 2>&1 | head -8
echo "=== xpedite probes（探针清单）==="
xpedite probes -p demo/profileInfo.py 2>&1 | head -12
echo "=== xpedite report（重新生成 runId 1793905883 的报告）==="
xpedite report -p demo/profileInfo.py -r 1793905883 2>&1 | tee "$LOG/xp_report.log" | head -40
REPORT_EXIT=$?
echo "REPORT_EXIT=$REPORT_EXIT"
echo "=== 报告文件 ==="
find /tmp/xpedite* /dev/shm -maxdepth 3 \( -name "*.txt" -o -name "*.ipynb" -o -name "*.html" \) -newermt "today" 2>/dev/null | grep -i xpedite | head -10
find /tmp/xpedite* /dev/shm -maxdepth 3 -type f -newermt "today" 2>/dev/null | grep -iE "xpedite|XpediteDemo" | while read -r f; do
  case "$f" in
    *XpediteDemo*report*.txt|*XpediteDemo*.txt) cp "$f" "$ART/xpedite_report.txt" ;;
    *XpediteDemo*.ipynb) cp "$f" "$ART/xpedite_report.ipynb" ;;
  esac
done
ls -la "$ART" | grep xpedite
echo XPEDITE_EVIDENCE_DONE
} >"$LOG/xp_evidence.log" 2>&1
