# -*- coding: utf-8 -*-
"""JPMorgan python-training 演示：用 nbclient 无头执行精选官方笔记本。

选取（避开需要 API key / 网络抓取的笔记本）：
  1_basic.ipynb        —— Python/Jupyter 基础
  2_straddle.ipynb     —— numpy 期权 straddle 定价
  3_flights.ipynb      —— pandas 文件处理与分组聚合
  9_3d_plotting.ipynb  —— pandas/plotly 收益率曲线 3D
输出：artifacts/jpm_training.json
"""
from __future__ import annotations

import json
import time
import traceback

from workbench.config import ARTIFACTS, ROOT

NB_DIR = ROOT / "vendor" / "python-training" / "notebooks"
NOTEBOOKS = ["1_basic.ipynb", "2_straddle.ipynb", "3_flights.ipynb", "9_3d_plotting.ipynb"]
KERNEL = "workbench-py312"


def _snippets(node, max_chars=220) -> list:
    out = []
    for cell in node.cells:
        for o in cell.get("outputs", []):
            if o.get("output_type") == "stream":
                out.append("".join(o.get("text", [])))
            elif o.get("output_type") == "execute_result":
                out.append(str(o.get("data", {}).get("text/plain", "")))
        if len(out) >= 4:
            break
    return [t.strip()[:max_chars] for t in out[:4] if t.strip()]


def run() -> dict:
    import nbformat
    from nbclient import NotebookClient

    # 已知的上游过时依赖（2026 视角）：JPM 笔记本写于 2019 年前后的 perspective API。
    # psp(df) 仅用于表格预览展示；shim 成返回 DataFrame 本身，保持计算与流程不变，透明记录。
    PSP_SHIM = (
        "from perspective import psp",
        "# [workbench compat] 2026 版 perspective-python 已移除 psp 预览 API；\n"
        "def psp(df):  # shim：返回 DataFrame 本身（原用途仅为表格预览，不影响计算）\n"
        "    return df",
    )

    results = {}
    for nb_name in NOTEBOOKS:
        path = NB_DIR / nb_name
        entry = {"path": str(path), "exists": path.exists()}
        if not path.exists():
            entry["ok"] = False
            entry["error"] = "notebook 文件不存在"
            results[nb_name] = entry
            continue
        node = nbformat.read(str(path), as_version=4)
        entry["cells"] = len(node.cells)
        patches = []
        for cell in node.cells:
            if cell.cell_type != "code":
                continue
            src = cell.source if isinstance(cell.source, str) else "".join(cell.source)
            old, shim = PSP_SHIM
            if old in src:
                cell.source = src.replace(old, shim)
                patches.append("psp → DataFrame shim（perspective 新版移除预览 API）")
        entry["compat_patches"] = patches
        client = NotebookClient(node, timeout=300, kernel_name=KERNEL,
                                resources={"metadata": {"path": str(NB_DIR)}})
        t0 = time.time()
        try:
            client.execute()
            entry["ok"] = True
            entry["error"] = None
        except Exception as exc:  # noqa: BLE001
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
            entry["traceback_tail"] = traceback.format_exc()[-500:]
        entry["seconds"] = round(time.time() - t0, 1)
        entry["output_snippets"] = _snippets(node)
        results[nb_name] = entry
        print(f"  {nb_name:<22} ok={entry['ok']}  {entry['seconds']}s  "
              f"{(entry['error'] or '')[:80]}")

    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "repo": "jpmorganchase/python-training",
        "kernel": KERNEL,
        "notebooks": results,
        "passed": all(r.get("ok") for r in results.values()),
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "jpm_training.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
    print(f"  → {ARTIFACTS / 'jpm_training.json'}")
    return out


if __name__ == "__main__":
    run()
