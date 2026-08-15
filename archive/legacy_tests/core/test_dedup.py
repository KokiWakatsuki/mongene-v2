"""DuplicationGuard と DiversityRotation のテスト"""
from __future__ import annotations

from pathlib import Path

import sympy

from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)


def _make_mr(answer_value: int, seed: int = 1234) -> MiddleRepresentation:
    expr = sympy.Integer(answer_value)
    step = LogicStep(
        operation_name="arithmetic_+",
        operands=["1", "2"],
        sympy_expr=expr,
        narration_hint="和を計算する",
    )
    return MiddleRepresentation(
        problem_structure_type="BasicCalculationStructure",
        selected_tags=["number"],
        difficulty_score=11.0,
        problem_form="calculation",
        sub_questions=[
            SubQuestion(
                label="",
                prompt_hint="次の計算",
                logic_steps=[step],
                answer=AnswerObject(type="numeric", sympy_form=expr, text_form=str(answer_value)),
            )
        ],
        visual_dsl=None,
        seed=seed,
        blueprint_id="BasicCalculationStructure",
        blueprint_version="v1",
    )


def test_duplication_guard_detects_same_answer(tmp_path: Path) -> None:
    db = tmp_path / "dedup.db"
    guard = DuplicationGuard(db_path=str(db))
    mr = _make_mr(3)
    assert guard.is_duplicate(mr) is False
    guard.register(mr, "TEST")
    assert guard.is_duplicate(mr) is True


def test_duplication_guard_distinguishes_different_answers(tmp_path: Path) -> None:
    db = tmp_path / "dedup.db"
    guard = DuplicationGuard(db_path=str(db))
    guard.register(_make_mr(3), "A")
    assert guard.is_duplicate(_make_mr(4)) is False


def test_diversity_rotation_filters_after_threshold() -> None:
    rot = DiversityRotation(max_consecutive=2)
    rot.record_pick("slot", "NumberAtom")
    rot.record_pick("slot", "NumberAtom")
    # 2 連続後、次の filter で同じクラスが除外される
    class _A:
        pass

    class _B:
        pass

    _A.__name__ = "NumberAtom"
    _B.__name__ = "OtherAtom"
    filtered = rot.filter_candidates("slot", [_A, _B])
    assert _A not in filtered
    assert _B in filtered
