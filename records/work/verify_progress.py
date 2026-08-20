"""進捗の徹底検証。**台帳の数字を「実際に生成できるか」まで遡って確かめる。**

なぜ要るか: `capabilities()` は「family が宣言していて lint が通る」セルを返すだけで、
**実際に問題が生成できるかは見ていない**。したがって coverage_page の「実装 N セル」も
宣言ベースの数字である。ここでは各セルを実際に generate して、

  A. capabilities に出るセルが本当に生成できるか（偽の「できている」）
  B. 台帳にあって capabilities に無いセルが、本当に未実装か（偽の「できていない」）
  C. 台帳・family 宣言・capabilities の三者が食い違っていないか

を実測する。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/verify_progress.py [seeds]
"""
from __future__ import annotations

import sys
import traceback
from collections import Counter
from pathlib import Path

import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Problem, Unsupported
from engine.core.pipeline import capabilities, generate
from engine.eval._harness import make_env
from engine.tools.goal_progress import _UNITS_PATH
from engine_paths import FAMILIES_DIR  # エンジンの場所は1か所で解決する

_FAM_DIR = FAMILIES_DIR


def _ledger_cells() -> set[tuple[str, str, int]]:
    units = yaml.safe_load(Path(_UNITS_PATH).read_text())["units"]
    return {
        (uid, form, int(lv))
        for uid, u in units.items()
        for form, fdef in (u.get("forms") or {}).items()
        for lv in (fdef.get("levels") or {})
    }


def _declared_cells() -> set[tuple[str, str, int]]:
    out: set[tuple[str, str, int]] = set()
    for f in sorted(_FAM_DIR.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text())
        parts = str(doc.get("family", "")).split(".")
        if len(parts) != 3:
            continue
        for lv in (doc.get("levels") or {}):
            out.add((parts[1], parts[2], int(lv)))
    return out


def main() -> int:
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    bootstrap()
    env = make_env()

    ledger = _ledger_cells()
    declared = _declared_cells()
    caps = {(c.unit, c.form, c.level) for c in capabilities()}

    print(f"台帳 {len(ledger)} / family 宣言 {len(declared)} / capabilities {len(caps)}")

    # --- C: 三者の食い違い ---
    print("\n[C1] family 宣言があるのに台帳に無い:", sorted(declared - ledger) or "なし")
    print("[C2] family 宣言があるのに capabilities に出ない（lint 落ち）:",
          sorted(declared - caps) or "なし")
    print("[C3] capabilities にあるのに family 宣言に無い:", sorted(caps - declared) or "なし")

    # --- A: capabilities のセルが本当に生成できるか ---
    fails: list[str] = []
    unsupported: list[str] = []
    for unit, form, level in sorted(caps):
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    GenerateRequest(subject="math", unit=unit, form=form, level=level, seed=seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception as exc:  # noqa: BLE001 - 何が起きても記録して続ける
                fails.append(f"{unit}.{form}.Lv{level} seed{seed}: {type(exc).__name__}: {exc}")
                traceback.print_exc(limit=1)
                break
            if isinstance(res, Unsupported):
                unsupported.append(f"{unit}.{form}.Lv{level} seed{seed}: code={res.code}")
                break
            if not isinstance(res, Problem):
                fails.append(f"{unit}.{form}.Lv{level} seed{seed}: 未知の戻り値 {type(res)}")
                break

    print(f"\n[A] capabilities {len(caps)} セル × {seeds} seed の生成実測")
    print(f"    例外で落ちた: {len(fails)}")
    for line in fails[:20]:
        print("      ", line)
    print(f"    Unsupported が返った: {len(unsupported)}")
    for line in unsupported[:20]:
        print("      ", line)

    generatable = len(caps) - len({f.split(" ")[0] for f in fails + unsupported})
    print(f"    ★実際に生成できたセル数: {generatable} / {len(caps)}")

    # --- B: 未実装セルの内訳 ---
    missing = ledger - caps
    byform = Counter(form for _u, form, _l in missing)
    print(f"\n[B] 未実装 {len(missing)} セル")
    for form, n in byform.most_common():
        cells = sorted(f"{u}:Lv{lv}" for u, f2, lv in missing if f2 == form)
        shown = cells if len(cells) <= 12 else cells[:12] + [f"... 他{len(cells) - 12}"]
        print(f"    {form:12s} {n:3d}  {' '.join(shown)}")

    ok = not fails and not unsupported and not (declared - ledger) and not (caps - declared)
    print("\n=== 検証 OK ===" if ok else "\n=== 検証 NG ===")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
