"""golden を**1プロセスで**全部再承認する。

`for f in ...; do python -m engine.tools.spec_cli approve $f; done` は、
family ごとに `bootstrap()`（pack 登録・curriculum/families の読み込み）を
やり直すので、その固定費だけで 282 回ぶんかかる。ここは bootstrap を1回にして
`_run_approve` を回す。

**同時に2つ走らせない**（互いの golden を上書きする）。

実行: PYTHONPATH=. .venv/bin/python scratchpad/approve_all.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from engine.tools.spec_cli import _DEFAULT_GOLDEN_DIR, _run_approve

_SKIP = {"__pycache__"}


def main() -> int:
    families = sorted(
        d.name for d in Path("engine_tests/golden").iterdir()
        if d.is_dir() and d.name not in _SKIP
    )
    fails: list[str] = []
    for i, fam in enumerate(families, 1):
        try:
            rc = _run_approve(fam, _DEFAULT_GOLDEN_DIR, diff=False)
        except Exception as e:  # noqa: BLE001
            rc, e_s = 1, f"{type(e).__name__}: {e}"
            print(f"APPROVE-FAIL {fam} {e_s}", flush=True)
        if rc != 0:
            fails.append(fam)
        if i % 20 == 0:
            print(f"... {i}/{len(families)}", flush=True)
    print(f"=== approve done ({len(families)} family / 失敗 {len(fails)}) ===", flush=True)
    for f in fails:
        print("FAIL", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
