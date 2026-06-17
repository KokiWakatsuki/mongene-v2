"""Phase 5: 実 LLM で代表 lesson をサンプリング生成し品質を確認する。

dedup / is_clean フィルタを有効化した状態で実行する（決定論モードのフラグを上書き）。
出力: reports/live_llm_sample_report.md
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

load_dotenv()

from apps.api.src.atoms.noun import (  # noqa: E402, F401
    circle_angle_atom,
    circle_atom,
    data_set_atom,
    equation_atom,
    event_atom,
    inverse_func_atom,
    line_angle_atom,
    linear_func_atom,
    moving_point_atom,
    number_atom,
    point_atom,
    polygon_atom,
    polynomial_atom,
    prism_atom,
    proportion_atom,
    pyramid_atom,
    quadratic_func_atom,
    sample_atom,
    sequence_atom,
    sphere_atom,
    square_root_atom,
)
from apps.api.src.atoms.verb import (  # noqa: E402, F401
    analyze_data_verb,
    calculate_arithmetic_verb,
    calculate_probability_verb,
    construct_geometry_verb,
    cutout_verb,
    estimate_population_verb,
    find_angle_verb,
    find_divisors_verb,
    form_shape_verb,
    generalize_formula_verb,
    intersect_verb,
    locus_verb,
    measure_geometry_verb,
    prove_algebraic_verb,
    prove_geometry_verb,
    slice_solid_verb,
    solve_eq_verb,
    solve_linear_diophantine_verb,
    transform_shape_verb,
    unfold_net_verb,
)
from apps.api.src.blueprints.registry import load_blueprint  # noqa: E402
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation  # noqa: E402
from apps.api.src.core.dedup.hash_cache import DuplicationGuard  # noqa: E402
from apps.api.src.core.evaluation.appropriateness import (  # noqa: E402
    is_appropriate,
    load_forbidden_words,
)
from apps.api.src.core.evaluation.solvability import is_clean, is_solvable  # noqa: E402
from apps.api.src.core.evaluation.standards import (  # noqa: E402
    evaluate_standards_alignment,
)
from apps.api.src.core.llm.translator import LLMTranslator  # noqa: E402
from apps.api.src.core.runner.atom_selector import AtomSelector  # noqa: E402
from apps.api.src.core.runner.blueprint_runner import (  # noqa: E402
    BlueprintRunner,
    GenerationRequest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
REPORT_PATH = REPO_ROOT / "reports" / "live_llm_sample_report.md"
DEDUP_DB = REPO_ROOT / "master_data" / "cache" / "live_dedup.db"

# 各 Blueprint から 1〜2 件ずつサンプル
SAMPLE_LESSON_IDS: List[str] = [
    "g1_l5",   # BasicCalculation
    "g1_l25",  # WordProblem
    "g3_l19",  # BasicCalculation 平方根
    "g3_l55",  # BasicDifference
    "g2_l16",  # WordProblem
    "g2_l28",  # WordProblem 1次関数
    "g3_l40",  # Function/Geometry
    "g3_l60",  # DataProbability
]


def _restore_quality_filters(mapping_entry: Dict[str, Any]) -> Dict[str, Any]:
    """決定論モード用フラグを除去し、is_clean / dedup を本来通り有効化"""
    entry = dict(mapping_entry)
    entry.pop("dedup_disabled", None)
    if "is_clean_override" in entry:
        cleaned = {k: v for k, v in entry["is_clean_override"].items() if k != "disabled"}
        entry["is_clean_override"] = cleaned
    return entry


def main() -> None:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    forbidden = load_forbidden_words()

    DEDUP_DB.parent.mkdir(parents=True, exist_ok=True)
    if DEDUP_DB.exists():
        DEDUP_DB.unlink()
    runner = BlueprintRunner(
        dedup=DuplicationGuard(db_path=str(DEDUP_DB)),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=20,
    )

    rows: List[Dict[str, Any]] = []
    for lid in SAMPLE_LESSON_IDS:
        if lid not in mapping:
            rows.append({"lesson_id": lid, "status": "SKIP (not in mapping)"})
            continue
        entry = _restore_quality_filters(mapping[lid])
        form = entry["supported_forms"][0]
        start = time.perf_counter()
        try:
            req = GenerationRequest(
                target_difficulty=int(entry["y_base"]),
                problem_form=form,
                lesson_id=lid,
            )
            gen = runner.run(req, entry)
            dur = (time.perf_counter() - start) * 1000
            ans = gen.middle_representation.sub_questions[0].answer
            row = {
                "lesson_id": lid,
                "status": "OK",
                "duration_ms": int(dur),
                "blueprint": entry["execute_blueprint"],
                "problem_text": gen.problem_text[:120],
                "answer": ans.text_form,
                "explanation": (gen.explanation_text or "")[:120],
                "solvable": is_solvable(ans.sympy_form),
                "appropriate": is_appropriate(gen.problem_text, forbidden),
                "standards_ok": evaluate_standards_alignment(gen.middle_representation, lid),
                "is_clean_answer": is_clean(ans.sympy_form) if ans.sympy_form is not None else False,
            }
        except Exception as e:
            dur = (time.perf_counter() - start) * 1000
            row = {
                "lesson_id": lid,
                "status": "ERROR",
                "duration_ms": int(dur),
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }
        rows.append(row)
        print(f"{lid}: {row.get('status')} ({row.get('duration_ms')}ms)")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = ["# Live LLM Sample Report\n"]
    ok = sum(1 for r in rows if r.get("status") == "OK")
    lines.append(f"- Total sampled: {len(rows)}")
    lines.append(f"- OK: {ok}")
    lines.append(f"- Errors: {len(rows) - ok}")
    lines.append("")
    for r in rows:
        lines.append(f"## {r['lesson_id']} — {r.get('status')}")
        if r.get("status") == "OK":
            lines.append(f"- Blueprint: {r['blueprint']}")
            lines.append(f"- Duration: {r['duration_ms']} ms")
            lines.append(f"- Solvable: {r['solvable']}, Appropriate: {r['appropriate']}, Standards: {r['standards_ok']}, Clean: {r['is_clean_answer']}")
            lines.append(f"- Answer: `{r['answer']}`")
            lines.append("- Problem text:")
            lines.append(f"  > {r['problem_text']}")
            if r.get("explanation"):
                lines.append("- Explanation:")
                lines.append(f"  > {r['explanation']}")
        else:
            lines.append(f"- {r.get('error', '')}")
        lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")


if __name__ == "__main__":
    main()
