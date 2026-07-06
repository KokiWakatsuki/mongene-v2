"""決定論ゲート全走査スクリプト（フェーズ2 §2b-1 / §2b-2）。

`tests/fixtures/reference_corpus/ground_truth/` を読み込み、
- **G6（難易度単調性）**: product 不要。同一 (lesson, form) の min/mid/max 3問をグループ化して判定。
- **G1/G2/G3/G4/G5/G7（1:1ゲート）**: `tests/fixtures/reference_corpus/product/` に対応する
  product JSON があれば走らせる（無ければそのキーはスキップし、レポートに「product無し」件数として記録）。

**LLM は一切呼ばない**。ground truth は事前に `build_ground_truth_corpus.py` で生成済みのものを読むだけ。

使い方:
    .venv/bin/python scripts/run_gates.py
    .venv/bin/python scripts/run_gates.py --out reports/gate_report.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

GROUND_TRUTH_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth"
PRODUCT_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "product"
DEFAULT_REPORT_PATH = REPO_ROOT / "reports" / "gate_report.md"

# ground truth ファイル名: {lesson}_{form}_{level}.json
_GT_FILENAME_RE = re.compile(r"^(?P<lesson>.+)_(?P<form>word_problem|calculation|proof|knowledge|visual)_(?P<level>min|mid|max)\.json$")

ONE_TO_ONE_GATE_IDS = ("G1", "G2", "G3", "G4", "G5", "G7")


def _import_gates():
    from scripts.eval_gates import g1_answer_leakage, g2_number_consistency, g3_answer_correctness
    from scripts.eval_gates import g4_form_conformance, g5_syllabus_range, g6_difficulty_monotonicity
    from scripts.eval_gates import g7_render_sanity

    return {
        "G1": g1_answer_leakage.check,
        "G2": g2_number_consistency.check,
        "G3": g3_answer_correctness.check,
        "G4": g4_form_conformance.check,
        "G5": g5_syllabus_range.check,
        "G7": g7_render_sanity.check,
    }, g6_difficulty_monotonicity.check_monotonicity


def load_ground_truth_corpus(corpus_dir: Path = GROUND_TRUTH_DIR) -> dict[str, dict[str, dict[str, Any]]]:
    """`{lesson}_{form}_{level}.json` を読み、`{(lesson, form): {level: data}}` に整理する。"""
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    if not corpus_dir.exists():
        return {}
    for path in sorted(corpus_dir.glob("*.json")):
        m = _GT_FILENAME_RE.match(path.name)
        if not m:
            continue  # ground_truth_build_failures.json 等は無視
        lesson = m.group("lesson")
        form = m.group("form")
        level = m.group("level")
        data = json.loads(path.read_text(encoding="utf-8"))
        grouped[(lesson, form)][level] = data
    return grouped


def load_product_corpus(product_dir: Path = PRODUCT_DIR) -> dict[str, dict[str, dict[str, Any]]]:
    """product 側コーパス（あれば）を同じキー構造で読む。無ければ空 dict。"""
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(dict)
    if not product_dir.exists():
        return {}
    for path in sorted(product_dir.glob("*.json")):
        m = _GT_FILENAME_RE.match(path.name)
        if not m:
            continue
        lesson = m.group("lesson")
        form = m.group("form")
        level = m.group("level")
        data = json.loads(path.read_text(encoding="utf-8"))
        grouped[(lesson, form)][level] = data
    return grouped


def run_g6_monotonicity(
    ground_truth_grouped: dict[tuple[str, str], dict[str, Any]],
    check_monotonicity_fn,
) -> list[dict[str, Any]]:
    """全 (lesson, form) について G6 を評価する。min/mid/max が揃っていないキーは N/A。"""
    results: list[dict[str, Any]] = []
    for (lesson, form), levels in sorted(ground_truth_grouped.items()):
        if not all(lv in levels for lv in ("min", "mid", "max")):
            results.append(
                {
                    "lesson_id": lesson,
                    "form": form,
                    "verdict": "N/A",
                    "reason": f"min/mid/max が揃っていない（保有: {sorted(levels.keys())}）",
                }
            )
            continue
        gate_result = check_monotonicity_fn(levels["min"], levels["mid"], levels["max"])
        results.append(
            {
                "lesson_id": lesson,
                "form": form,
                "verdict": gate_result.verdict,
                "reason": gate_result.reason,
                "details": gate_result.details,
            }
        )
    return results


def run_one_to_one_gates(
    ground_truth_grouped: dict[tuple[str, str], dict[str, Any]],
    product_grouped: dict[tuple[str, str], dict[str, Any]],
    gate_fns: dict[str, Any],
) -> list[dict[str, Any]]:
    """product が存在するキーだけ G1/G2/G3/G4/G5/G7 を走らせる。"""
    results: list[dict[str, Any]] = []
    for (lesson, form), gt_levels in sorted(ground_truth_grouped.items()):
        product_levels = product_grouped.get((lesson, form), {})
        for level in ("min", "mid", "max"):
            gt = gt_levels.get(level)
            product = product_levels.get(level)
            if gt is None:
                continue
            if product is None:
                results.append(
                    {
                        "lesson_id": lesson,
                        "form": form,
                        "level": level,
                        "product_available": False,
                        "gates": {},
                    }
                )
                continue
            gate_verdicts = {}
            for gate_id, fn in gate_fns.items():
                result = fn(product, gt)
                gate_verdicts[gate_id] = {"verdict": result.verdict, "reason": result.reason}
            results.append(
                {
                    "lesson_id": lesson,
                    "form": form,
                    "level": level,
                    "product_available": True,
                    "gates": gate_verdicts,
                }
            )
    return results


def _build_generation_failure_summary() -> list[dict[str, Any]]:
    fail_log = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth_build_failures.json"
    if not fail_log.exists():
        return []
    return json.loads(fail_log.read_text(encoding="utf-8"))


def render_report(
    g6_results: list[dict[str, Any]],
    one_to_one_results: list[dict[str, Any]],
    generation_failures: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("# 決定論ゲート走査レポート（フェーズ2 run_gates.py）")
    lines.append("")
    lines.append("LLM は一切使用していません。ground truth は `/problems/inspect` 相当（SKIP_LLM_IN_TESTS=true）。")
    lines.append("")

    # --- G6 難易度単調性 サマリ ---
    lines.append("## G6 難易度単調性（product不要・LLMゼロ）")
    lines.append("")
    total = len(g6_results)
    pass_count = sum(1 for r in g6_results if r["verdict"] == "PASS")
    fail_count = sum(1 for r in g6_results if r["verdict"] == "FAIL")
    na_count = sum(1 for r in g6_results if r["verdict"] == "N/A")
    rate = (pass_count / total * 100) if total else 0.0
    lines.append(f"- 対象 (lesson, form) 件数: {total}")
    lines.append(f"- PASS: {pass_count} ({rate:.1f}%)")
    lines.append(f"- FAIL: {fail_count}")
    lines.append(f"- N/A: {na_count}")
    lines.append("")

    # 形式別マトリクス
    lines.append("### 形式別 PASS 率")
    lines.append("")
    lines.append("| form | total | PASS | FAIL | N/A | PASS率 |")
    lines.append("|---|---|---|---|---|---|")
    by_form: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in g6_results:
        by_form[r["form"]].append(r)
    for form, rows in sorted(by_form.items()):
        t = len(rows)
        p = sum(1 for r in rows if r["verdict"] == "PASS")
        f = sum(1 for r in rows if r["verdict"] == "FAIL")
        n = sum(1 for r in rows if r["verdict"] == "N/A")
        pr = (p / t * 100) if t else 0.0
        lines.append(f"| {form} | {t} | {p} | {f} | {n} | {pr:.1f}% |")
    lines.append("")

    lines.append("### G6 FAIL 一覧（難易度が min<mid<max で単調増加しない lesson, form）")
    lines.append("")
    fails = [r for r in g6_results if r["verdict"] == "FAIL"]
    if not fails:
        lines.append("(なし)")
    else:
        lines.append("| lesson_id | form | reason |")
        lines.append("|---|---|---|")
        for r in fails:
            lines.append(f"| {r['lesson_id']} | {r['form']} | {r['reason']} |")
    lines.append("")

    lines.append("### G6 N/A 一覧（min/mid/maxが揃わず判定不能）")
    lines.append("")
    nas = [r for r in g6_results if r["verdict"] == "N/A"]
    if not nas:
        lines.append("(なし)")
    else:
        lines.append("| lesson_id | form | reason |")
        lines.append("|---|---|---|")
        for r in nas:
            lines.append(f"| {r['lesson_id']} | {r['form']} | {r['reason']} |")
    lines.append("")

    # --- 1:1 ゲート ---
    lines.append("## G1/G2/G3/G4/G5/G7（1:1ゲート、product 必要）")
    lines.append("")
    with_product = [r for r in one_to_one_results if r["product_available"]]
    without_product = [r for r in one_to_one_results if not r["product_available"]]
    lines.append(f"- product あり: {len(with_product)} 件")
    lines.append(f"- product なし（今回はスキップ・2b-2で生成予定）: {len(without_product)} 件")
    lines.append("")
    if with_product:
        lines.append("### 形式別・ゲート別 通過率マトリクス")
        lines.append("")
        lines.append("| form | " + " | ".join(ONE_TO_ONE_GATE_IDS) + " |")
        lines.append("|---|" + "---|" * len(ONE_TO_ONE_GATE_IDS))
        by_form_11: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in with_product:
            by_form_11[r["form"]].append(r)
        for form, rows in sorted(by_form_11.items()):
            cells = []
            for gate_id in ONE_TO_ONE_GATE_IDS:
                verdicts = [row["gates"].get(gate_id, {}).get("verdict") for row in rows]
                applicable = [v for v in verdicts if v not in (None, "N/A")]
                p = sum(1 for v in applicable if v == "PASS")
                t = len(applicable)
                cells.append(f"{p}/{t}" if t else "N/A")
            lines.append(f"| {form} | " + " | ".join(cells) + " |")
        lines.append("")
    else:
        lines.append("(product コーパスが無いため今回は集計なし。2b-2 で `tests/fixtures/reference_corpus/product/` を作れば自動的にこのセクションが埋まる)")
        lines.append("")

    # --- ground truth 生成失敗一覧 ---
    lines.append("## ground truth 生成の失敗一覧")
    lines.append("")
    lines.append(f"- 失敗件数: {len(generation_failures)}")
    lines.append("")
    if generation_failures:
        lines.append("| lesson_id | form | level | error |")
        lines.append("|---|---|---|---|")
        for f in generation_failures:
            err = f.get("error", "").replace("\n", " ")
            lines.append(f"| {f['lesson_id']} | {f['form']} | {f['level_label']} | {err} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ground-truth-dir", default=str(GROUND_TRUTH_DIR))
    parser.add_argument("--product-dir", default=str(PRODUCT_DIR))
    parser.add_argument("--out", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()

    gate_fns, check_monotonicity_fn = _import_gates()

    ground_truth_grouped = load_ground_truth_corpus(Path(args.ground_truth_dir))
    product_grouped = load_product_corpus(Path(args.product_dir))

    g6_results = run_g6_monotonicity(ground_truth_grouped, check_monotonicity_fn)
    one_to_one_results = run_one_to_one_gates(ground_truth_grouped, product_grouped, gate_fns)
    generation_failures = _build_generation_failure_summary()

    report = render_report(g6_results, one_to_one_results, generation_failures)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    total = len(g6_results)
    pass_count = sum(1 for r in g6_results if r["verdict"] == "PASS")
    print(f"G6: {pass_count}/{total} PASS ({(pass_count/total*100 if total else 0):.1f}%)")
    print(f"レポート: {out_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
