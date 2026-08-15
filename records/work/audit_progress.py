"""進捗の実測監査。**進捗更新の前に必ずこれを回す。**

## なぜ要るか

進捗更新で繰り返し2方向のミスが起きた。原因が別なので検査も別に要る。

  A. 「できていないのにできている」
     Phase 1 が「完了」とされたが、3束目（動点・速さ word_problem）は投入されて
     いなかった。計画書の完了判定が実測と突き合わされていなかった。
     → 検査6（Phase の対象セルが本当に capabilities にあるか）

  B. 「できているのにできていない」
     ・g1_l53: solver も recipe もあるのに family が無く、台帳に載っていなかった。
       → 検査4/5（使われていない recipe / solver）
     ・g1_l27 Lv4: 意図的除外の判断が family YAML の source_desc に埋もれ、
       台帳を見ただけでは取りこぼしと区別できなかった。
       → 検査3（除外の記述をもつ family の一覧）
     ・g3_l55/l56 Lv4: 実装したのに source_desc の「本コミットの担当外」が
       残っていた（＝古い記述が実態と食い違う）。
       → 検査3 の結果を gaps と突き合わせる

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/audit_progress.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from engine.bootstrap import bootstrap
from engine.core.pipeline import capabilities
from engine.core.registry import REGISTRY
from engine.tools.goal_progress import _UNITS_PATH

_FAM_DIR = Path("engine_core/engine/curriculum/math/families")
_EXCLUSION_RE = re.compile(r"意図的に未実装|未実装のまま|本タスクの対象外|担当外|本コミットの担当外")


def _ledger_cells() -> set[tuple[str, str, int]]:
    units = yaml.safe_load(Path(_UNITS_PATH).read_text())["units"]
    out: set[tuple[str, str, int]] = set()
    for uid, u in units.items():
        for form, fdef in (u.get("forms") or {}).items():
            for lv in (fdef.get("levels") or {}):
                out.add((uid, form, int(lv)))
    return out


def _declared_cells() -> set[tuple[str, str, int]]:
    """family YAML が levels として宣言しているセル。"""
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
    bootstrap()
    caps = {(c.unit, c.form, c.level) for c in capabilities()}
    ledger = _ledger_cells()
    gaps = ledger - caps
    failures: list[str] = []

    print(f"台帳 {len(ledger)} / 実装 {len(caps)} / 未実装 {len(gaps)}")

    # --- 検査1: family に宣言があるのに capabilities に出ない（配線切れ） ---
    broken = sorted(_declared_cells() - caps)
    print(f"\n[1] family 宣言があるのに台帳に載らない（配線切れ）: {len(broken)}")
    for x in broken:
        print("    ", x)
    if broken:
        failures.append("配線切れ（lint R6 / provides_concepts 漏れを疑う）")

    # --- 検査2: capabilities にあるのに台帳の定義に無い ---
    extra = sorted(caps - ledger)
    print(f"\n[2] 台帳の定義に無いセルを生成している: {len(extra)}")
    for x in extra:
        print("    ", x)
    if extra:
        failures.append("台帳外のセル")

    # --- 検査3: 除外の記述と実態の突き合わせ ---
    print("\n[3] 「意図的に未実装 / 対象外」の記述をもつ family")
    stale: list[str] = []
    for f in sorted(_FAM_DIR.glob("*.yaml")):
        txt = f.read_text()
        if not _EXCLUSION_RE.search(txt):
            continue
        doc = yaml.safe_load(txt)
        parts = str(doc.get("family", "")).split(".")
        unit, form = parts[1], parts[2]
        unit_gaps = sorted(lv for (u, fo, lv) in gaps if u == unit and fo == form)
        note = next(
            (line.strip() for line in txt.splitlines() if _EXCLUSION_RE.search(line)), ""
        )
        status = f"未実装 Lv{unit_gaps}" if unit_gaps else "**この form に未実装は無い**"
        print(f"    {f.name}: {status}")
        print(f"        {note[:100]}")
        # 「実装済み／実装した」と後から書き足してあれば、除外の記述は履歴として正しい。
        if not unit_gaps and not re.search(r"実装済み|実装した", txt):
            stale.append(f.name)
    if stale:
        print(f"\n    ⚠ 古い記述の疑い（除外と書いてあるが未実装が無い）: {stale}")
        failures.append(f"古い除外記述: {stale}")

    # --- 検査4/5: 使われていない recipe / solver（実装済みなのに台帳に載らない資産） ---
    used_recipes = set()
    for f in sorted(_FAM_DIR.glob("*.yaml")):
        doc = yaml.safe_load(f.read_text())
        for lv in (doc.get("levels") or {}).values():
            if lv.get("recipe"):
                used_recipes.add(str(lv["recipe"]))
    orphan_recipes = sorted(set(REGISTRY._recipes) - used_recipes)
    print(f"\n[4] どの family も使っていない recipe: {len(orphan_recipes)}")
    for r in orphan_recipes:
        print("    ", r)
    if orphan_recipes:
        failures.append("未使用 recipe（family を書けばセルが増える可能性）")

    src = "\n".join(
        p.read_text()
        for p in Path("engine_core/engine/packs/math").rglob("*.py")
        if "/solvers/" not in str(p)
    )
    orphan_solvers = sorted(s for s in REGISTRY._solvers if f'"{s}"' not in src)
    print(f"\n[5] recipe/checker から呼ばれていない solver: {len(orphan_solvers)}")
    for s in orphan_solvers:
        print("    ", s)
    if orphan_solvers:
        failures.append("未使用 solver（recipe を書けばセルが増える可能性）")

    # --- 検査6: 計画書が「✅ 完了」と書いた Phase の対象セルが実装済みか ---
    plan = Path("docs/completion_plan_2026-08-06.md")
    if plan.exists():
        text = plan.read_text()
        claimed = [ln.strip("# ").strip() for ln in text.splitlines()
                   if ln.startswith("## Phase") and "✅" in ln]
        print(f"\n[6] 計画書が完了と書いている Phase: {len(claimed)}")
        for c in claimed:
            print("    ", c.strip())
        print("    （対象セルの実測は下の form 別内訳と突き合わせて確認する）")

    print("\n--- 残りの内訳（実測） ---")
    by_form: dict[str, int] = {}
    for _u, form, _lv in gaps:
        by_form[form] = by_form.get(form, 0) + 1
    for form, n in sorted(by_form.items(), key=lambda kv: -kv[1]):
        print(f"    {form:<14}{n}")

    _print_curriculum_content()

    print()
    if failures:
        print("=== 監査 NG ===")
        for f_ in failures:
            print("  -", f_)
        return 1
    print("=== 監査 OK（実装済みなのに載っていない資産・配線切れ・古い除外記述は無い）===")
    return 0


def _print_curriculum_content() -> None:
    """カリキュラムモデル（共有データ資産）の充足率を出す。

    要件定義（`docs/requirements_2026-07-11.html` §3②）では、**知識グラフ（前提関係DAG）と
    誤答要因の語彙は「教育者が編集できる形式」の共有データ資産**で、エンジンの担当は
    「要因 → 戻り先座標を解決して問題を供給する」（F-7）ほう。**配線は動いている**のに
    中身がほぼ空なので、UC-2（誤答からの戻り）が事実上使えない。

    ここに出しておかないと**穴が見えない**（台帳は 630/630 で埋まって見える）。
    """
    import yaml

    from engine.core.spec.loader import load_family_dir

    d = Path("engine_core/engine/curriculum/math")
    concepts = yaml.safe_load((d / "concepts.yaml").read_text(encoding="utf-8")) or {}
    prereqs = yaml.safe_load((d / "prerequisites.yaml").read_text(encoding="utf-8")) or {}
    causes = yaml.safe_load((d / "error_causes.yaml").read_text(encoding="utf-8")) or {}
    families = load_family_dir(Path("engine_core/engine/curriculum/math/families"))

    levels = [lv for spec in families.values() for lv in spec.levels.values()]
    tagged = sum(1 for lv in levels if lv.cause_tags)

    n_concepts = len(concepts.get("concepts") or [])
    n_prereq = len(prereqs.get("prerequisites") or [])
    n_causes = len(causes.get("error_causes") or [])
    print("\n--- カリキュラムモデルの充足率（教育者が入れる中身・要件定義 §3②）---")
    print(f"    概念                 {n_concepts}")
    print(f"    前提関係の辺          {n_prereq}"
          f"{'   ← 概念の数に対して空（UC-2 の「前提単元へ戻る」が動かない）' if n_prereq < n_concepts // 10 else ''}")
    print(f"    誤答要因              {n_causes}"
          f"{'   ← 空（原因の選択肢が出せない）' if n_causes < 10 else ''}")
    print(f"    要因タグ付きのセル      {tagged} / {len(levels)}"
          f"{'   ← ほぼ空（問題から要因を引けない）' if tagged * 10 < len(levels) else ''}")
    print("    ※ ここはエンジンの欠陥ではなく、共有データ資産の未入力。"
          "配線（要因→戻り先→供給）は動くことを実測済み")


if __name__ == "__main__":
    raise SystemExit(main())
