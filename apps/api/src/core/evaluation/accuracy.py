"""Accuracy 検証: LLM 出力テキスト → 数式逆抽出 → SymPy 照合（§12.5）"""
from __future__ import annotations

import re
from typing import Optional

import sympy


def _extract_latex_expressions(text: str) -> list[str]:
    """`$...$` で囲まれた LaTeX 数式を抽出"""
    return re.findall(r"\$([^$]+)\$", text)


def _try_parse_latex(latex_str: str) -> Optional[sympy.Expr]:
    """sympy.parsing.latex で LaTeX をパース（失敗時 None）"""
    try:
        from sympy.parsing.latex import parse_latex
    except ImportError:
        return None
    try:
        return parse_latex(latex_str)
    except Exception:
        return None


def verify_accuracy(problem_text: str, expected: sympy.Expr) -> bool:
    """テキスト内の数式が expected と一致するものを 1 つ以上含むか"""
    for latex_str in _extract_latex_expressions(problem_text):
        parsed = _try_parse_latex(latex_str)
        if parsed is None:
            continue
        try:
            if sympy.simplify(parsed - expected) == 0:
                return True
        except Exception:
            continue
    return False
