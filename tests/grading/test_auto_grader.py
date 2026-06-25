"""自動採点（経路A）のテスト。"""
from __future__ import annotations

from apps.api.src.core.grading.auto_grader import grade_answer


def test_numeric_exact() -> None:
    o = grade_answer("5", "5", "numeric")
    assert o.is_correct and o.gradable


def test_numeric_negative_and_spaces() -> None:
    assert grade_answer("-3", " -3 ", "numeric").is_correct


def test_numeric_fraction_decimal_equivalent() -> None:
    assert grade_answer("1/2", "0.5", "numeric").is_correct


def test_expression_commutative() -> None:
    assert grade_answer("x + 2", "2 + x", "expression").is_correct


def test_strips_lhs_equals() -> None:
    # "x = 2" のような左辺付き入力は右辺を採点
    assert grade_answer("2", "x = 2", "numeric").is_correct


def test_sqrt_symbol_normalized() -> None:
    assert grade_answer("sqrt(2)", "√2", "expression").is_correct


def test_incorrect() -> None:
    o = grade_answer("5", "6", "numeric")
    assert not o.is_correct and o.gradable and o.error_type == "incorrect"


def test_blank() -> None:
    o = grade_answer("5", "   ", "numeric")
    assert not o.is_correct and o.gradable and o.error_type == "blank"


def test_parse_error() -> None:
    o = grade_answer("5", ")(@#", "numeric")
    assert not o.is_correct and o.gradable and o.error_type == "parse_error"


def test_unsupported_form_routes_to_vision() -> None:
    o = grade_answer("Q.E.D.", "証明...", "proof")
    assert not o.gradable and o.error_type == "unsupported_form"


def test_no_answer_key() -> None:
    o = grade_answer(None, "5", "numeric")
    assert not o.gradable and o.error_type == "no_answer_key"
