"""word_problem 数値接地の検証器（generate-then-verify 反転 ④-3）の単体テスト。

- `apps/api/src/core/evaluation/grounding.py` を敵対的入力で固める。
- 保守設計（非ゼロ整数のみ・絶対値照合・分数/小数/記号式/0 は対象外）を検証。
- LLM は使わない（決定論）。
"""
from __future__ import annotations

import sympy

from apps.api.src.core.evaluation.grounding import (
    find_missing_required_numbers,
    required_integer_magnitudes_from_mr,
)
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)


def _wp_mr(operands, answer_sympy, answer_text, form="word_problem"):
    step = LogicStep(operation_name="op", operands=list(operands), sympy_expr=answer_sympy, narration_hint="")
    return MiddleRepresentation(
        problem_structure_type="X",
        selected_tags=[],
        difficulty_score=10.0,
        problem_form=form,
        sub_questions=[
            SubQuestion(
                label="(1)",
                prompt_hint="場面に即して計算しなさい",
                logic_steps=[step],
                answer=AnswerObject(type="numeric", sympy_form=answer_sympy, text_form=answer_text),
            )
        ],
        visual_dsl=None,
        seed=1,
        blueprint_id="X",
        blueprint_version="v1",
    )


# ── required_integer_magnitudes_from_mr ───────────────────────────

def test_required_magnitudes_abs_of_integers():
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    assert required_integer_magnitudes_from_mr(mr) == [30, 7]


def test_required_magnitudes_excludes_symbolic():
    mr = _wp_mr(["3*sqrt(2)", "3*(2*sqrt(2))"], sympy.sympify("9*sqrt(2)"), "9*sqrt(2)")
    assert required_integer_magnitudes_from_mr(mr) == []


def test_required_magnitudes_excludes_zero():
    mr = _wp_mr(["0", "5"], sympy.Integer(5), "5")
    assert required_integer_magnitudes_from_mr(mr) == [5]


def test_required_magnitudes_excludes_fraction():
    # 分数は自然文で言語化されやすい → 対象外
    mr = _wp_mr(["1/2", "3"], sympy.sympify("7/2"), "7/2")
    assert required_integer_magnitudes_from_mr(mr) == [3]


# ── find_missing_required_numbers ─────────────────────────────────

def test_no_missing_when_magnitudes_present():
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    miss = find_missing_required_numbers("倉庫から 30 個ずつ 7 回搬出した。", [], mr)
    assert miss == []


def test_negative_operand_matched_by_magnitude_with_direction_words():
    # 符号を方向語で表す faithful な翻訳を誤棄却しない（絶対値照合）
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    miss = find_missing_required_numbers("気温が 30 度ずつ 7 回下がった。", [], mr)
    assert miss == []


def test_dropped_number_detected():
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    miss = find_missing_required_numbers("倉庫から 30 個を搬出した。", [], mr)
    assert miss == ["7"]


def test_changed_number_detected():
    # LLM が 30 を 50 に改変 → 30 が欠落として検出
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    miss = find_missing_required_numbers("倉庫から 50 個ずつ 7 回搬出した。", [], mr)
    assert miss == ["30"]


def test_number_in_sub_prompt_counts_as_present():
    mr = _wp_mr(["-30", "-7"], sympy.Integer(210), "210")
    miss = find_missing_required_numbers("次の場面を考える。", ["(1) 30 と 7 を使う"], mr)
    assert miss == []


def test_symbolic_operand_never_flagged_missing():
    # 平方根題材（g3_l23 型）は記号 operand を対象にせず誤棄却しない
    mr = _wp_mr(["3*sqrt(2)", "3*(2*sqrt(2))"], sympy.sympify("9*sqrt(2)"), "9*sqrt(2)")
    miss = find_missing_required_numbers("根号を含む場面。", [], mr)
    assert miss == []


# ── 打開策4: 誤棄却回避の精緻化 ──────────────────────────────
def test_probability_derived_operands_not_required():
    """確率の適合数・標本空間（導出値）は入力量でないため必須にしない（誤棄却回避）。"""
    step = LogicStep(
        operation_name="calculate_probability",
        operands=["1", "36"],  # 適合1 / 全事象36（導出値）
        sympy_expr=sympy.Rational(1, 36),
        narration_hint="2つのさいころの和が2になる確率",
    )
    mr = MiddleRepresentation(
        problem_structure_type="DataProbabilityStructure",
        selected_tags=[], difficulty_score=40.0, problem_form="word_problem",
        sub_questions=[SubQuestion(
            label="", prompt_hint="確率を求めなさい", logic_steps=[step],
            answer=AnswerObject(type="numeric", sympy_form=sympy.Rational(1, 36), text_form="1/36"),
        )],
        visual_dsl=None, seed=1, blueprint_id="DataProbabilityStructure", blueprint_version="v1",
    )
    # 36 も 1 も問題文に無くても欠落扱いしない
    miss = find_missing_required_numbers("2つのさいころを投げて出た目の和が2になる確率を求めなさい。", [], mr)
    assert miss == []


def test_magnitude_one_not_required():
    """大きさ 1（暗黙の係数 y=x 等）は問題文に現れなくても欠落扱いしない。"""
    mags = required_integer_magnitudes_from_mr(_wp_mr(["1", "3"], sympy.Integer(3), "3"))
    assert 1 not in mags
    assert 3 in mags
