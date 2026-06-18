"""Accuracy 検証: LLM 出力テキスト → 数式逆抽出 → SymPy 照合（§12.5）"""
from __future__ import annotations

import re
from typing import Optional

import sympy


def _extract_latex_expressions(text: str) -> list[str]:
    """`$...$` で囲まれた LaTeX 数式を抽出"""
    return re.findall(r"\$([^$]+)\$", text)


def _extract_numeric_strings(text: str) -> list[str]:
    """日本語解説文から数値文字列を抽出（例: 「= 144」「答えは 144 cm³」）"""
    return re.findall(r"(?<!=)\s*([-\d/√π\.]+)\s*(?:cm|m|度|°|$|\s)", text)


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


def _try_parse_numeric(s: str) -> Optional[sympy.Expr]:
    """単純な数値文字列を sympy に変換"""
    try:
        s = s.strip().replace("√", "sqrt")
        return sympy.sympify(s)
    except Exception:
        return None


def verify_accuracy(explanation_text: str, expected: sympy.Expr) -> bool:
    """解説テキスト内に expected の答えが含まれるか確認する。

    LaTex 数式 + 生の数値文字列の両方で照合する。
    """
    # 1. LaTeX 数式から
    for latex_str in _extract_latex_expressions(explanation_text):
        parsed = _try_parse_latex(latex_str)
        if parsed is None:
            continue
        try:
            if sympy.simplify(parsed - expected) == 0:
                return True
        except Exception:
            continue

    # 2. 生の数値文字列から（解説に「= 144」と書いてあれば一致）
    expected_str = str(expected).replace(" ", "")
    if expected_str and expected_str in explanation_text.replace(" ", ""):
        return True

    # 3. 浮動小数点近似での緩い照合
    try:
        expected_float = float(sympy.nsimplify(expected).evalf())
        for num_str in _extract_numeric_strings(explanation_text):
            parsed_num = _try_parse_numeric(num_str)
            if parsed_num is None:
                continue
            try:
                if abs(float(parsed_num.evalf()) - expected_float) < 0.01:
                    return True
            except Exception:
                continue
    except Exception:
        pass

    return False
