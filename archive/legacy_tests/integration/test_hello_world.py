"""Hello World 統合テスト（§41.2 step 24, §15.4 Phase 1）

中1 の四則計算問題を 1 問生成し、以下を確認する：
1. SymPy で計算が完了している
2. LLM 翻訳（モック）が完了している
3. 重複チェックを通過している
4. 学年範囲外単元タグが含まれていない
"""
from __future__ import annotations

from pathlib import Path

import sympy

from apps.api.src.atoms.noun import number_atom  # noqa: F401 -- register_noun 実行
from apps.api.src.atoms.verb import calculate_arithmetic_verb  # noqa: F401
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.evaluation.solvability import is_solvable
from apps.api.src.core.evaluation.standards import evaluate_standards_alignment
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import (
    BlueprintRunner,
    GenerationRequest,
)


def _make_runner(tmp_db: Path) -> BlueprintRunner:
    dedup = DuplicationGuard(db_path=str(tmp_db))
    return BlueprintRunner(
        dedup=dedup,
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=20,
    )


def _hello_mapping() -> dict:
    return {
        "target_lesson_id": "g1_l5",
        "title": "加法と減法の混じった計算",
        "grade": 1,
        "lesson_number": 5,
        "execute_blueprint": "BasicCalculationStructure",
        "required_tags": ["number"],
        "optional_tags": [],
        "atom_constraints": {
            "NumberAtom": {
                "allow_negative": True,
                "max_value": 20,
                "force_fraction": False,
            }
        },
        "visual_component": "NullRenderer",
        "y_base": 13,
        "supported_forms": ["calculation"],
    }


def test_hello_world_end_to_end(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(
        target_difficulty=15,
        problem_form="calculation",
        lesson_id="g1_l5",
    )
    result = runner.run(request, _hello_mapping())

    mr = result.middle_representation
    assert mr.blueprint_id == "BasicCalculationStructure"
    assert len(mr.sub_questions) == 1

    answer = mr.sub_questions[0].answer
    assert answer.sympy_form is not None
    assert is_solvable(answer.sympy_form)

    # 答が整数 (NumberAtom + NumberAtom の和) になっていること
    assert sympy.simplify(answer.sympy_form).is_Integer

    # LLM 翻訳（モック）が文字列を返している
    assert isinstance(result.problem_text, str)
    assert len(result.problem_text) > 0

    # 学年範囲外単元タグが含まれていない
    assert evaluate_standards_alignment(mr, "g1_l5") is True


def test_hello_world_deduplication_blocks_repeats(tmp_path: Path) -> None:
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(
        target_difficulty=15,
        problem_form="calculation",
        lesson_id="g1_l5",
    )
    # 同じ runner（同じ dedup DB）で 5 問生成し、すべて成功すれば dedup が
    # パラメータ空間内で別の問題を返している
    seen_answers: set[str] = set()
    for _ in range(5):
        result = runner.run(request, _hello_mapping())
        ans = str(result.middle_representation.sub_questions[0].answer.sympy_form)
        seen_answers.add(ans)
    # 5 回試行で少なくとも 2 種類の異なる答えが出ること
    assert len(seen_answers) >= 2
