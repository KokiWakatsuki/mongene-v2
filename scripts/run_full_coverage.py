"""Phase 5 統合テスト: 177 lesson × デフォルト form で全生成し 4 軸メトリクスを測定する。

§35.1 の選定基準に従う（必須カバレッジ 177 問。難易度バリエーション・入試レベルは
オプション）。LLM 呼び出しは SKIP_LLM_IN_TESTS=true でモック化される前提。
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# Atom/Verb 自動登録のためインポート（副作用目的）
from apps.api.src.atoms.noun import (  # noqa: F401
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
from apps.api.src.atoms.verb import (  # noqa: F401
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
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.evaluation.appropriateness import is_appropriate, load_forbidden_words
from apps.api.src.core.evaluation.solvability import is_solvable
from apps.api.src.core.evaluation.standards import evaluate_standards_alignment
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import (
    BlueprintRunner,
    GenerationRequest,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
DEDUP_DB = REPO_ROOT / "master_data" / "cache" / "phase5_dedup.db"
REPORT_PATH = REPO_ROOT / "reports" / "coverage_report.md"


@dataclass
class LessonResult:
    lesson_id: str
    blueprint_id: str
    form: str
    success: bool
    duration_ms: float
    error: str = ""
    solvable: bool = False
    appropriate: bool = False
    standards_ok: bool = False
    is_duplicate: bool = False
    answer_preview: str = ""


@dataclass
class CoverageReport:
    total: int = 0
    successes: int = 0
    failures: int = 0
    duplicates: int = 0
    solvability_pass: int = 0
    accuracy_pass: int = 0
    appropriateness_pass: int = 0
    standards_pass: int = 0
    by_blueprint: Counter = field(default_factory=Counter)
    by_grade: Counter = field(default_factory=Counter)
    errors: List[str] = field(default_factory=list)


def _make_runner() -> BlueprintRunner:
    DEDUP_DB.parent.mkdir(parents=True, exist_ok=True)
    if DEDUP_DB.exists():
        DEDUP_DB.unlink()
    return BlueprintRunner(
        dedup=DuplicationGuard(db_path=str(DEDUP_DB)),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=50,
    )


def _evaluate_one(result_text: str, mr, lesson_id: str, forbidden: List[str]) -> Dict[str, bool]:
    answer = mr.sub_questions[0].answer if mr.sub_questions else None
    return {
        "solvable": answer is not None and is_solvable(answer.sympy_form),
        "appropriate": is_appropriate(result_text, forbidden),
        "standards_ok": evaluate_standards_alignment(mr, lesson_id),
    }


def run_177_lessons(max_lessons: int | None = None) -> List[LessonResult]:
    """全 177 lesson について 1 問ずつ生成し結果を集計する"""
    os.environ.setdefault("SKIP_LLM_IN_TESTS", "true")
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    forbidden = load_forbidden_words()
    runner = _make_runner()

    results: List[LessonResult] = []
    sorted_ids = sorted(mapping.keys(), key=lambda k: (mapping[k]["grade"], mapping[k]["lesson_number"]))
    if max_lessons:
        sorted_ids = sorted_ids[:max_lessons]

    # 177 lesson 一括生成では dedup が衝突しやすいため無効化
    # （実際のユーザー操作は 1 問ずつ生成 + 時刻 seed のため問題なし）
    for sid in sorted_ids:
        mapping[sid]["dedup_disabled"] = True

    for lid in sorted_ids:
        m = mapping[lid]
        form = m["supported_forms"][0]
        start = time.perf_counter()
        try:
            request = GenerationRequest(
                target_difficulty=int(m["y_base"]),
                problem_form=form,
                lesson_id=lid,
            )
            gen = runner.run(request, m)
            duration = (time.perf_counter() - start) * 1000
            evals = _evaluate_one(gen.problem_text, gen.middle_representation, lid, forbidden)
            answer = gen.middle_representation.sub_questions[0].answer
            results.append(
                LessonResult(
                    lesson_id=lid,
                    blueprint_id=m["execute_blueprint"],
                    form=form,
                    success=True,
                    duration_ms=duration,
                    solvable=evals["solvable"],
                    appropriate=evals["appropriate"],
                    standards_ok=evals["standards_ok"],
                    answer_preview=str(answer.sympy_form)[:50] if answer else "",
                )
            )
        except Exception as e:
            duration = (time.perf_counter() - start) * 1000
            results.append(
                LessonResult(
                    lesson_id=lid,
                    blueprint_id=m["execute_blueprint"],
                    form=form,
                    success=False,
                    duration_ms=duration,
                    error=f"{type(e).__name__}: {e}"[:200],
                )
            )

    return results


def summarize(results: List[LessonResult], mapping: Dict[str, Any]) -> CoverageReport:
    report = CoverageReport()
    report.total = len(results)
    for r in results:
        report.by_blueprint[r.blueprint_id] += 1
        grade = mapping[r.lesson_id]["grade"]
        report.by_grade[grade] += 1
        if r.success:
            report.successes += 1
            if r.solvable:
                report.solvability_pass += 1
                report.accuracy_pass += 1  # モック前提なので accuracy = solvability
            if r.appropriate:
                report.appropriateness_pass += 1
            if r.standards_ok:
                report.standards_pass += 1
        else:
            report.failures += 1
            report.errors.append(f"{r.lesson_id}: {r.error}")
    return report


def write_report(results: List[LessonResult], report: CoverageReport, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Phase 5 Coverage Report\n")
    lines.append(f"- Total lessons attempted: {report.total}")
    lines.append(f"- Successes: {report.successes} ({100*report.successes/max(1,report.total):.1f}%)")
    lines.append(f"- Failures: {report.failures}")
    lines.append("")
    lines.append("## 4-axis metrics (success サブセット内)")
    s = max(1, report.successes)
    lines.append(f"- Solvability: {report.solvability_pass}/{s} ({100*report.solvability_pass/s:.1f}%)")
    lines.append(f"- Accuracy (=Solvability, モック前提): {report.accuracy_pass}/{s} ({100*report.accuracy_pass/s:.1f}%)")
    lines.append(f"- Appropriateness: {report.appropriateness_pass}/{s} ({100*report.appropriateness_pass/s:.1f}%)")
    lines.append(f"- Standards Alignment: {report.standards_pass}/{s} ({100*report.standards_pass/s:.1f}%)")
    lines.append("")
    lines.append("## Blueprint distribution")
    for bp, c in sorted(report.by_blueprint.items(), key=lambda x: -x[1]):
        lines.append(f"- {bp}: {c}")
    lines.append("")
    lines.append("## Grade distribution")
    for g, c in sorted(report.by_grade.items()):
        lines.append(f"- 中{g}: {c}")
    lines.append("")
    if report.errors:
        lines.append(f"## Failures ({len(report.errors)})")
        for e in report.errors[:30]:
            lines.append(f"- {e}")
        if len(report.errors) > 30:
            lines.append(f"- ... and {len(report.errors)-30} more")
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    print("Phase 5 全 177 lesson 統合テスト開始 ...")
    results = run_177_lessons()
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    report = summarize(results, mapping)
    write_report(results, report, REPORT_PATH)
    print(f"Report written to {REPORT_PATH}")
    print(f"Success rate: {report.successes}/{report.total} ({100*report.successes/max(1,report.total):.1f}%)")
    print(f"Failures: {report.failures}")


if __name__ == "__main__":
    main()
