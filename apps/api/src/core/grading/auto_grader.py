"""SymPy による厳密自動採点。

`grade_answer` は生徒の入力文字列を解析し、期待値（生成時に保持した sympy_form 文字列）と
`simplify(a - b) == 0` で比較する。数値型は浮動小数点近似でもフォールバック照合する。

対象は answer.type ∈ {numeric, expression} のみ。それ以外（proof/set/graph）は
``GradeOutcome(gradable=False)`` を返し、呼び出し側が ScoGene（経路B）へ振り分ける。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import sympy

# 自動採点できる answer.type
GRADABLE_TYPES = {"numeric", "expression"}


@dataclass
class GradeOutcome:
    is_correct: bool
    gradable: bool
    error_type: Optional[str] = None  # "blank" / "parse_error" / "incorrect" / "unsupported_form" / None


def _normalize_input(s: str) -> str:
    s = s.strip()
    # よくある記号ゆれを正規化
    s = (
        s.replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
        .replace("π", "pi")
        .replace("−", "-")  # 全角マイナス
    )
    # 括弧なしの √2 / √x を sqrt(2) / sqrt(x) に。√(...) は残りの置換で sqrt(...) になる
    s = re.sub(r"√\s*([0-9]+(?:\.[0-9]+)?|[A-Za-z]+)", r"sqrt(\1)", s)
    s = s.replace("√", "sqrt")
    # "x = 2" や "= 2" のように左辺がある場合は右辺を採点対象にする
    if "=" in s:
        s = s.split("=")[-1].strip()
    return s


def _parse(s: str) -> sympy.Expr:
    """文字列を SymPy 式に変換（有理数優先）。"""
    return sympy.sympify(_normalize_input(s), rational=True)


def grade_answer(
    expected_sympy_form: Optional[str],
    student_answer: Optional[str],
    answer_type: str,
) -> GradeOutcome:
    """生徒の解答を厳密採点する。"""
    if answer_type not in GRADABLE_TYPES:
        return GradeOutcome(is_correct=False, gradable=False, error_type="unsupported_form")
    if not expected_sympy_form:
        return GradeOutcome(is_correct=False, gradable=False, error_type="no_answer_key")
    if student_answer is None or not student_answer.strip():
        return GradeOutcome(is_correct=False, gradable=True, error_type="blank")

    try:
        expected = _parse(expected_sympy_form)
        got = _parse(student_answer)
    except Exception:
        return GradeOutcome(is_correct=False, gradable=True, error_type="parse_error")

    # 1. 記号的厳密照合
    try:
        if sympy.simplify(got - expected) == 0:
            return GradeOutcome(is_correct=True, gradable=True)
    except Exception:
        pass

    # 2. 数値近似フォールバック（√・分数など評価可能な場合）
    try:
        if abs(float(got.evalf()) - float(expected.evalf())) < 1e-6:
            return GradeOutcome(is_correct=True, gradable=True)
    except (TypeError, ValueError, AttributeError):
        pass

    return GradeOutcome(is_correct=False, gradable=True, error_type="incorrect")
