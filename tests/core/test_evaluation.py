"""Evaluation 層のテスト"""
from __future__ import annotations

import sympy

from apps.api.src.core.evaluation.appropriateness import is_appropriate
from apps.api.src.core.evaluation.solvability import (
    has_degenerate_step,
    is_clean,
    is_degenerate_step,
    is_solvable,
)
from apps.api.src.core.evaluation.standards import evaluate_standards_alignment
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)


def test_is_solvable_with_concrete_number() -> None:
    assert is_solvable(sympy.Integer(3)) is True


def test_is_solvable_with_none() -> None:
    assert is_solvable(None) is False


def test_is_clean_accepts_integer() -> None:
    assert is_clean(sympy.Integer(7)) is True


def test_is_clean_rejects_large_denominator() -> None:
    expr = sympy.Rational(1, 12345)
    assert is_clean(expr) is False


def test_is_clean_rejects_large_radicand() -> None:
    expr = sympy.sqrt(99999)
    assert is_clean(expr) is False


def test_is_clean_accepts_small_radicand() -> None:
    expr = sympy.sqrt(2)
    assert is_clean(expr) is True


def test_is_appropriate_no_forbidden_words() -> None:
    assert is_appropriate("太郎は学校で勉強した", ["殺す", "撃つ"]) is True


def test_is_appropriate_with_forbidden_word() -> None:
    assert is_appropriate("敵を殺す", ["殺す"]) is False


def _make_mr_with_tags(tags: list[str]) -> MiddleRepresentation:
    step = LogicStep(
        operation_name="arithmetic_+",
        operands=["1", "2"],
        sympy_expr=sympy.Integer(3),
        narration_hint="和",
    )
    return MiddleRepresentation(
        problem_structure_type="X",
        selected_tags=tags,
        difficulty_score=10.0,
        problem_form="calculation",
        sub_questions=[
            SubQuestion(
                label="",
                prompt_hint="計算",
                logic_steps=[step],
                answer=AnswerObject(type="numeric", sympy_form=sympy.Integer(3), text_form="3"),
            )
        ],
        visual_dsl=None,
        seed=1234,
        blueprint_id="X",
        blueprint_version="v1",
    )


def test_standards_alignment_grade1_rejects_square_root() -> None:
    mr = _make_mr_with_tags(["square_root"])
    assert evaluate_standards_alignment(mr, "g1_l5") is False


def test_standards_alignment_grade3_allows_pythagorean() -> None:
    mr = _make_mr_with_tags(["pythagorean", "space_geometry"])
    assert evaluate_standards_alignment(mr, "g3_l55") is True


# --- 退化検出ゲート（打開策2） ---
def test_degenerate_zero_area_is_rejected() -> None:
    # 三角形の面積 0 は退化（同一切片の直線で座標軸と作る三角形など）
    assert is_degenerate_step("triangle_area", sympy.Integer(0)) is True
    assert is_degenerate_step("measure_area", sympy.Integer(0)) is True
    assert is_degenerate_step("measure_volume", sympy.Integer(-5)) is True


def test_nonzero_area_is_ok() -> None:
    assert is_degenerate_step("triangle_area", sympy.Rational(25, 4)) is False


def test_degenerate_probability_out_of_range() -> None:
    assert is_degenerate_step("calculate_probability", sympy.Integer(0)) is True
    assert is_degenerate_step("calculate_probability", sympy.Integer(1)) is True
    assert is_degenerate_step("calculate_probability", sympy.Rational(3, 2)) is True
    assert is_degenerate_step("calculate_probability", sympy.Rational(1, 2)) is False


def test_non_magnitude_op_zero_is_ok() -> None:
    # 一般の計算結果 0（例: 加算結果 0）は退化ではない
    assert is_degenerate_step("arithmetic_+", sympy.Integer(0)) is False


def test_has_degenerate_step_scans_all() -> None:
    good = LogicStep(operation_name="intersect", operands=[], sympy_expr=sympy.Integer(4), narration_hint="")
    bad = LogicStep(operation_name="triangle_area", operands=[], sympy_expr=sympy.Integer(0), narration_hint="")
    assert has_degenerate_step([good, bad]) is True
    assert has_degenerate_step([good]) is False
