"""`scripts/eval_gates/common.py` の数値正規化ロジックの単体テスト（LLM不要）。

G2 の偽陽性調査で見つかった「\\left(- \\frac{1}{3}\\right)」のような、単項マイナスが
括弧付き分数と空白で分離しているケースの照合ギャップを対象にする。
"""
from __future__ import annotations

from scripts.eval_gates.common import (
    contains_number,
    extract_numbers,
    normalize_math_text,
    numbers_equal,
)


# ---------------------------------------------------------------------------
# 本題: 符号付き分数が \left( / \right) 装飾・空白と絡んでも照合できること
# ---------------------------------------------------------------------------


def test_contains_number_finds_negative_fraction_behind_left_right_and_space():
    text = r"$\left(- \frac{1}{3}\right) + \frac{8}{7}$"
    assert contains_number(text, "-1/3") is True


def test_contains_number_finds_positive_fraction_in_same_text():
    text = r"$\left(- \frac{1}{3}\right) + \frac{8}{7}$"
    assert contains_number(text, "8/7") is True


def test_contains_number_does_not_confuse_sign_for_second_operand():
    text = r"$\left(- \frac{1}{3}\right) + \frac{8}{7}$"
    assert contains_number(text, "-8/7") is False


def test_contains_number_negative_fraction_attached_no_space():
    # 空白なし密着: -\frac{1}{3}
    text = r"\left(-\frac{1}{3}\right) + \frac{8}{7}"
    assert contains_number(text, "-1/3") is True


def test_contains_number_negative_fraction_detached_with_space():
    # 空白あり分離: - \frac{1}{3}
    text = r"\left(- \frac{1}{3}\right) + \frac{8}{7}"
    assert contains_number(text, "-1/3") is True


def test_contains_number_does_not_match_wrong_sign_for_positive_fraction():
    text = r"\left(\frac{1}{3}\right)"
    assert contains_number(text, "-1/3") is False


# ---------------------------------------------------------------------------
# \left / \right 装飾除去の既存挙動（整数・小数）が壊れていないこと
# ---------------------------------------------------------------------------


def test_left_right_removed_around_positive_integer():
    assert normalize_math_text(r"\left(3\right)") == "(3)"


def test_left_right_removed_around_negative_integer():
    assert normalize_math_text(r"\left(-3\right)") == "(-3)"
    assert contains_number(r"\left(-3\right)", "-3") is True
    assert contains_number(r"\left(-3\right)", "3") is False


def test_left_right_removed_around_decimal():
    assert contains_number(r"\left(-3.5\right)", "-3.5") is True


def test_left_right_bracket_and_brace_variants_still_strip():
    assert normalize_math_text(r"\left[3\right]") == "[3]"
    assert normalize_math_text(r"\left\{3\right\}") == "{3}"


# ---------------------------------------------------------------------------
# 回帰: 既存の分数・全角・マイナス異体字の正規化が壊れていないこと
# ---------------------------------------------------------------------------


def test_dfrac_normalizes_to_parenthesized_ratio():
    assert normalize_math_text(r"\dfrac{1}{2}") == "(1/2)"


def test_fullwidth_and_unicode_minus_normalize_to_ascii_minus():
    assert contains_number("－３", "-3") is True
    assert contains_number("−３", "-3") is True


def test_binary_subtraction_not_misparsed_as_two_separate_numbers():
    # 既存仕様: 空白ありの二項減算 "5 - 3" は独立した 5 と 3 として抽出される
    assert extract_numbers("5 - 3") == ["5", "3"]


def test_unary_minus_immediately_before_digit_still_captured():
    # 既存仕様: 空白+数字が密着していれば単項マイナスとして拾う
    assert extract_numbers("5 -3") == ["5", "-3"]


def test_numbers_equal_across_fraction_and_decimal_representation():
    assert numbers_equal(r"\left(- \frac{1}{3}\right)", "-0.3") is False  # 明確に異なる値は同一視しない
    assert numbers_equal(r"\left(- \frac{1}{2}\right)", "-0.5") is True


def test_extract_numbers_plain_parenthesized_fraction_without_sign():
    assert extract_numbers("(1/3) + (8/7)") == ["1/3", "8/7"]
