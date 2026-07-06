"""G3 答え正当性 (answer_correctness)

spec §3-G3:
- スコープを明示: `calculation` 形式のみ自動化。content_problem_text と各
  sub_questions[].prompt_text から数式を抽出し（content を先に試し、無ければ各
  prompt_text を順に試す）、最初に抽出できた数式で SymPy 再解答、
  ground truth の答えと一致するか判定する。
  実LLM生成では計算式が content ではなく prompt_text に入るケースが多いため。
- 非計算形式は N/A（G1/G2/G4 で代替）。過剰な自然言語パースを試みない（誤判定を避ける）。
- 誤判定を出さない方を優先（高精度・中再現率でよい）。

LLM は使わない。SymPy による決定論的な再計算のみ。
"""
from __future__ import annotations

import re
from typing import Any, Optional

import sympy
from sympy.parsing.sympy_parser import parse_expr, standard_transformations, implicit_multiplication_application

from scripts.eval_gates.common import GateResult, normalize_math_text, numbers_equal

GATE_ID = "G3"

_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)

# content 中の $...$ (インライン数式) を抜き出す
_DOLLAR_EXPR_RE = re.compile(r"\$([^$]+)\$")

# 「答え: X」「答え：X」パターン（あれば式部分から除外するため）
_ANSWER_LABEL_RE = re.compile(r"答え\s*[:：]")


def _latex_to_sympy_str(latex: str) -> str:
    """ごく限定的な LaTeX → sympy パース可能文字列への変換。

    フル LaTeX パーサは実装しない（誤判定リスクが高いため）。対応するのは
    本システムが実際に出す程度の単純な四則演算・分数・べき乗のみ。
    """
    s = normalize_math_text(latex)
    # \times, \cdot -> *
    s = s.replace(r"\times", "*").replace(r"\cdot", "*")
    s = s.replace(r"\div", "/")
    # ^{n} -> **n, ^n -> **n
    s = re.sub(r"\^\{([^{}]+)\}", r"**(\1)", s)
    s = re.sub(r"\^(\d+)", r"**\1", s)
    # sqrt{x} (normalize_math_text の frac 変換は既に (a/b) にしている)
    s = re.sub(r"\\?sqrt\{([^{}]+)\}", r"sqrt(\1)", s)
    return s


def _extract_calculation_expr(content: str) -> Optional[str]:
    """content_problem_text から「計算対象の数式」らしきものを1つ抽出する。

    保守的に: 最初の $...$ を対象とする。ただし「答え:」以降にある式は除外
    （既に答えが書かれているケースを誤って再解答対象にしないため）。
    """
    label_match = _ANSWER_LABEL_RE.search(content)
    search_region = content[: label_match.start()] if label_match else content

    matches = _DOLLAR_EXPR_RE.findall(search_region)
    if not matches:
        return None
    # 最初に見つかった、かつ数字・演算子を含む式を採用
    for m in matches:
        if re.search(r"\d", m):
            return m
    return None


def _try_eval(expr_str: str) -> Optional[sympy.Expr]:
    try:
        sympy_str = _latex_to_sympy_str(expr_str)
        expr = parse_expr(sympy_str, transformations=_TRANSFORMATIONS)
        return sympy.simplify(expr)
    except Exception:
        return None


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    problem_form = ground_truth.get("problem_form")
    if problem_form != "calculation":
        return GateResult(GATE_ID, "N/A", f"calculation 形式ではないため対象外 (problem_form={problem_form})")

    sub_questions_gt = ground_truth.get("sub_questions", []) or []
    if not sub_questions_gt:
        return GateResult(GATE_ID, "N/A", "ground truth に sub_questions が無い")

    content = product.get("content_problem_text", "") or ""
    prompt_texts = [sq.get("prompt_text", "") or "" for sq in product.get("sub_questions", []) or []]

    expr_str = None
    for candidate_text in [content, *prompt_texts]:
        expr_str = _extract_calculation_expr(candidate_text)
        if expr_str is not None:
            break

    if expr_str is None:
        return GateResult(GATE_ID, "N/A", "問題文から再解答可能な数式を抽出できなかった")

    recomputed = _try_eval(expr_str)
    if recomputed is None:
        return GateResult(GATE_ID, "N/A", f"抽出した数式 '{expr_str}' を SymPy で解釈できなかった")

    # ground truth の答え（最初の sub_question を基準にする。複数ある場合は最初のみ照合）
    answer = (sub_questions_gt[0].get("answer") or {})
    gt_value = answer.get("sympy_form") or answer.get("text_form")
    if not gt_value:
        return GateResult(GATE_ID, "N/A", "ground truth に答え値が無い")

    gt_expr = _try_eval(str(gt_value))
    if gt_expr is None:
        # sympy で解釈できない場合は文字列正規化での比較にフォールバック
        if numbers_equal(str(recomputed), str(gt_value)):
            return GateResult(GATE_ID, "PASS", "再計算結果が ground truth と一致（文字列比較）")
        return GateResult(GATE_ID, "N/A", f"ground truth の答え '{gt_value}' を SymPy で解釈できなかった")

    try:
        is_equal = bool(sympy.simplify(recomputed - gt_expr) == 0)
    except Exception:
        is_equal = numbers_equal(str(recomputed), str(gt_expr))

    if is_equal:
        return GateResult(
            GATE_ID,
            "PASS",
            f"再計算結果 {recomputed} が ground truth {gt_expr} と一致",
        )
    return GateResult(
        GATE_ID,
        "FAIL",
        f"再計算結果 {recomputed} が ground truth {gt_expr} と不一致",
        details={"recomputed": str(recomputed), "expected": str(gt_expr), "source_expr": expr_str},
    )
