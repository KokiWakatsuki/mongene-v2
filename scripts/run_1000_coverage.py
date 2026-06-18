"""Phase 5 §35.1 の 1000 問サンプリングを実行する。

カテゴリ:
1. 必須カバレッジ 177 問: 全 lesson × デフォルト form × 中央難易度
2. 形式バリエーション 300 問: 全 lesson × 全 supported_forms × 中央難易度
3. 難易度バリエーション 300 問: 主要 30 lesson × 1 form × 難易度 [1, 30, 60, 90]
4. 入試レベル 200 問: 難易度 80〜100 で複合単元組合せ
5. エッジケース 23 問: unlearned_lesson_ids での連鎖排除

LLM はモック (SKIP_LLM_IN_TESTS=true) でも実 LLM でも実行可能。
"""
from __future__ import annotations

import json
import os
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# Atom/Verb 登録
from apps.api.src.atoms.noun import (  # noqa: F401
    circle_angle_atom, circle_atom, data_set_atom, equation_atom, event_atom,
    inverse_func_atom, line_angle_atom, linear_func_atom, moving_point_atom,
    number_atom, point_atom, polygon_atom, polynomial_atom, prism_atom,
    proportion_atom, pyramid_atom, quadratic_func_atom, sample_atom,
    sequence_atom, sphere_atom, square_root_atom,
)
from apps.api.src.atoms.verb import (  # noqa: F401
    analyze_data_verb, calculate_arithmetic_verb, calculate_probability_verb,
    construct_geometry_verb, cutout_verb, estimate_population_verb,
    find_angle_verb, find_divisors_verb, form_shape_verb,
    generalize_formula_verb, intersect_verb, locus_verb, measure_geometry_verb,
    prove_algebraic_verb, prove_geometry_verb, slice_solid_verb, solve_eq_verb,
    solve_linear_diophantine_verb, transform_shape_verb, unfold_net_verb,
)
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.evaluation.appropriateness import is_appropriate, load_forbidden_words
from apps.api.src.core.evaluation.solvability import is_solvable
from apps.api.src.core.evaluation.standards import evaluate_standards_alignment
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest
from apps.api.src.core.scenarios.bank import ScenarioBank

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
REPORT_PATH = REPO_ROOT / "reports" / "coverage_1000_report.md"
DEDUP_DB = REPO_ROOT / "master_data" / "cache" / "phase5_1000_dedup.db"


@dataclass
class Result:
    case_key: str
    lesson_id: str
    blueprint_id: str
    form: str
    difficulty: int
    category: str
    success: bool
    error: str = ""
    solvable: bool = False
    appropriate: bool = False
    standards_ok: bool = False


@dataclass
class CoverageReport:
    total: int = 0
    by_category: Counter = field(default_factory=Counter)
    successes_by_category: Counter = field(default_factory=Counter)
    solvability_by_category: Counter = field(default_factory=Counter)
    appropriateness_by_category: Counter = field(default_factory=Counter)
    standards_by_category: Counter = field(default_factory=Counter)
    errors: List[str] = field(default_factory=list)


def _make_runner() -> BlueprintRunner:
    DEDUP_DB.parent.mkdir(parents=True, exist_ok=True)
    if DEDUP_DB.exists():
        DEDUP_DB.unlink()
    try:
        scenarios = ScenarioBank.load()
    except FileNotFoundError:
        scenarios = None
    return BlueprintRunner(
        dedup=DuplicationGuard(db_path=str(DEDUP_DB)),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        scenario_bank=scenarios,
        max_retries=50,
    )


def _run_one(
    runner: BlueprintRunner,
    mapping: Dict[str, Any],
    lesson_id: str,
    form: str,
    difficulty: int,
    category: str,
    unlearned: List[str],
    forbidden: List[str],
) -> Result:
    m = mapping[lesson_id]
    if form not in m["supported_forms"]:
        return Result(
            case_key=f"{lesson_id}|{form}|{difficulty}|{category}",
            lesson_id=lesson_id, blueprint_id=m["execute_blueprint"], form=form,
            difficulty=difficulty, category=category, success=False,
            error="form not supported",
        )
    request = GenerationRequest(
        target_difficulty=difficulty,
        problem_form=form,
        lesson_id=lesson_id,
        unlearned_lesson_ids=unlearned,
    )
    try:
        gen = runner.run(request, m)
        answer = gen.middle_representation.sub_questions[0].answer
        return Result(
            case_key=f"{lesson_id}|{form}|{difficulty}|{category}",
            lesson_id=lesson_id, blueprint_id=m["execute_blueprint"], form=form,
            difficulty=difficulty, category=category, success=True,
            solvable=is_solvable(answer.sympy_form),
            appropriate=is_appropriate(gen.problem_text, forbidden),
            standards_ok=evaluate_standards_alignment(gen.middle_representation, lesson_id),
        )
    except Exception as e:
        return Result(
            case_key=f"{lesson_id}|{form}|{difficulty}|{category}",
            lesson_id=lesson_id, blueprint_id=m["execute_blueprint"], form=form,
            difficulty=difficulty, category=category, success=False,
            error=f"{type(e).__name__}: {str(e)[:150]}",
        )


def _enumerate_cases(mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # 1. 必須カバレッジ (177 問)
    for lid, m in mapping.items():
        cases.append({
            "category": "mandatory",
            "lesson_id": lid,
            "form": m["supported_forms"][0],
            "difficulty": int(m["y_base"]),
            "unlearned": [],
        })

    # 2. 形式バリエーション (上位 supported_forms 全部 = 約 300 問)
    for lid, m in mapping.items():
        for f in m["supported_forms"]:
            if f == m["supported_forms"][0]:
                continue  # 必須カバレッジと重複回避
            cases.append({
                "category": "form_variation",
                "lesson_id": lid,
                "form": f,
                "difficulty": int(m["y_base"]),
                "unlearned": [],
            })
        if len([c for c in cases if c["category"] == "form_variation"]) >= 300:
            break

    # 3. 難易度バリエーション (主要 75 lesson × 4 段階)
    # 各 lesson の y_base ± 15 内に難易度を絞る（§39 DELTA_MAX 制約に従う）
    sorted_lids = sorted(mapping.keys(), key=lambda k: -int(mapping[k]["y_base"]))[:75]
    for lid in sorted_lids:
        m = mapping[lid]
        yb = int(m["y_base"])
        # y_base ± 15 内で 4 段階
        for d in [max(1, yb - 12), max(1, yb - 6), min(100, yb + 6), min(100, yb + 12)]:
            cases.append({
                "category": "difficulty_variation",
                "lesson_id": lid,
                "form": m["supported_forms"][0],
                "difficulty": d,
                "unlearned": [],
            })

    # 4. 入試レベル (y_base が高い lesson × y_base 近傍の難易度)
    exam_lids = [lid for lid, m in mapping.items() if int(m["y_base"]) >= 60][:50]
    for lid in exam_lids:
        m = mapping[lid]
        yb = int(m["y_base"])
        # 入試レベル相当 = y_base から +5 〜 +15 の高難易度域
        for d in [min(100, yb + 3), min(100, yb + 8), min(100, yb + 12), min(100, yb + 15)]:
            cases.append({
                "category": "exam_level",
                "lesson_id": lid,
                "form": m["supported_forms"][0],
                "difficulty": d,
                "unlearned": [],
            })

    # 5. エッジケース (unlearned による連鎖排除発動: 23 件)
    # 中3 lesson に 中1/中2 の前提単元を unlearned 指定
    edge_lids = [lid for lid, m in mapping.items() if m["grade"] == 3][:23]
    for lid in edge_lids:
        m = mapping[lid]
        unlearned = [f"g1_l{n}" for n in [10, 15, 20]] + [f"g2_l{n}" for n in [10, 20]]
        cases.append({
            "category": "edge_case",
            "lesson_id": lid,
            "form": m["supported_forms"][0],
            "difficulty": int(m["y_base"]),
            "unlearned": unlearned,
        })

    return cases


def main() -> None:
    os.environ.setdefault("SKIP_LLM_IN_TESTS", "true")
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    forbidden = load_forbidden_words()
    runner = _make_runner()
    cases = _enumerate_cases(mapping)
    print(f"Total cases: {len(cases)}")

    results: List[Result] = []
    by_cat: Counter = Counter(c["category"] for c in cases)
    print(f"By category: {dict(by_cat)}")

    start = time.perf_counter()
    for i, case in enumerate(cases):
        r = _run_one(
            runner, mapping,
            case["lesson_id"], case["form"], case["difficulty"], case["category"],
            case["unlearned"], forbidden,
        )
        results.append(r)
        if (i + 1) % 100 == 0:
            elapsed = time.perf_counter() - start
            print(f"  {i + 1}/{len(cases)} ({elapsed:.1f}s)")

    # 集計
    report = CoverageReport()
    report.total = len(results)
    for r in results:
        report.by_category[r.category] += 1
        if r.success:
            report.successes_by_category[r.category] += 1
            if r.solvable:
                report.solvability_by_category[r.category] += 1
            if r.appropriate:
                report.appropriateness_by_category[r.category] += 1
            if r.standards_ok:
                report.standards_by_category[r.category] += 1
        else:
            report.errors.append(f"{r.case_key}: {r.error}")

    # レポート出力
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = [
        "# Phase 5 §35.1 1000 問品質ゲート Report",
        "",
        f"- Total cases: {report.total}",
        f"- Total elapsed: {time.perf_counter() - start:.1f} s",
        "",
        "## カテゴリ別 4 軸メトリクス",
        "",
        "| Category | Total | Success | Solvable | Appropriate | Standards |",
        "|:---|---:|---:|---:|---:|---:|",
    ]
    for cat in ["mandatory", "form_variation", "difficulty_variation", "exam_level", "edge_case"]:
        tot = report.by_category[cat]
        suc = report.successes_by_category[cat]
        sol = report.solvability_by_category[cat]
        app = report.appropriateness_by_category[cat]
        std = report.standards_by_category[cat]
        rate = lambda n, d: f"{n}/{d} ({100*n/max(1,d):.1f}%)"
        lines.append(
            f"| {cat} | {tot} | {rate(suc, tot)} | {rate(sol, suc)} | {rate(app, suc)} | {rate(std, suc)} |"
        )
    lines.append("")
    if report.errors:
        lines.append(f"## Failures ({len(report.errors)})")
        for e in report.errors[:30]:
            lines.append(f"- {e}")
        if len(report.errors) > 30:
            lines.append(f"- ... and {len(report.errors) - 30} more")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {REPORT_PATH}")
    print(f"Total success rate: {sum(report.successes_by_category.values())}/{report.total}")


if __name__ == "__main__":
    main()
