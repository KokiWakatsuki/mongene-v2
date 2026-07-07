"""答え漏洩の検出コア（LLMフリー・evaluator = verifier）。

オフライン評価ゲート G1（`scripts/eval_gates/g1_answer_leakage.py`）と、ランタイムの
LLM 翻訳器（`apps/api/src/core/llm/translator.py`）が **同一のロジック** で
「正解値が問題文に漏れていないか」を判定するための共有コア（HANDOFF §4 の
evaluator=verifier 昇格＝generate-then-verify 反転の骨格）。

- moat 不変: SymPy が計算した数値は一切変えない。ここは text を検査するだけ。
- LLM は使わない。数値正規化（`number_normalize`）による決定論突合のみ。
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Tuple

from apps.api.src.core.evaluation.number_normalize import (
    contains_number,
    dedupe_preserve_order,
    normalize_math_text,
)

_BLANK_TOKENS = {"", "none", "nan"}


def _is_blank(value: Any) -> bool:
    return value is None or str(value).strip().lower() in _BLANK_TOKENS


def _is_numeric(value: str) -> bool:
    """value が数値（整数/小数/分数/符号付き）として解釈できるか。"""
    from apps.api.src.core.evaluation.number_normalize import _to_fraction

    return _to_fraction(normalize_math_text(value)) is not None


def detect_leaked_values(
    text: str,
    answer_values: Iterable[str],
    operand_values: Iterable[str],
    *,
    numeric_only: bool = False,
) -> Tuple[List[str], List[str]]:
    """`text` 中に正解値が漏れているか判定する共有コア。

    戻り値 `(hard_leaked, ambiguous_leaked)`:
    - hard_leaked: 正解値が出現し、かつ入力オペランドとは一致しない（＝真の漏洩）。
    - ambiguous_leaked: 正解値が出現するが入力オペランドとも一致（誤検出の可能性）。

    `numeric_only=True` のときは数値として解釈できる正解値のみを対象にする
    （proof/knowledge 等の非数値 text_form が問題文に正当に現れるケースの誤棄却を避ける）。
    """
    operands = [op for op in operand_values if not _is_blank(op)]
    hard: List[str] = []
    ambiguous: List[str] = []
    for value in answer_values:
        if _is_blank(value):
            continue
        v = str(value).strip()
        if numeric_only and not _is_numeric(v):
            continue
        if contains_number(text, v):
            if any(contains_number(v, op) or contains_number(op, v) for op in operands):
                ambiguous.append(v)
            else:
                hard.append(v)
    return dedupe_preserve_order(hard), dedupe_preserve_order(ambiguous)


# ---------------------------------------------------------------------------
# MiddleRepresentation から正解値・オペランドを取り出すヘルパ（ランタイム側）
# ---------------------------------------------------------------------------

def answer_values_from_mr(mr: Any) -> List[str]:
    """MR の各 sub_question から正解値を集める（answer.sympy_form/text_form + 末尾 logic_step）。

    G1 ゲートが corpus dict から集めるのと同じ集合をオブジェクトから取り出す。
    """
    values: List[str] = []
    for sq in getattr(mr, "sub_questions", []) or []:
        answer = getattr(sq, "answer", None)
        if answer is not None:
            for attr in ("sympy_form", "text_form"):
                v = getattr(answer, attr, None)
                if not _is_blank(v):
                    values.append(str(v))
        steps = getattr(sq, "logic_steps", []) or []
        if steps:
            expr = getattr(steps[-1], "sympy_expr", None)
            if not _is_blank(expr):
                values.append(str(expr))
    return dedupe_preserve_order(values)


def operand_values_from_mr(mr: Any) -> List[str]:
    """MR の全 logic_steps[].operands の数値集合（G2/G1 の「必要入力数値」）。"""
    operands: List[str] = []
    for sq in getattr(mr, "sub_questions", []) or []:
        for step in getattr(sq, "logic_steps", []) or []:
            for operand in getattr(step, "operands", []) or []:
                if not _is_blank(operand):
                    operands.append(str(operand))
    return dedupe_preserve_order(operands)


def find_problem_answer_leak(
    problem_text: str,
    sub_prompt_texts: Optional[Iterable[str]],
    mr: Any,
    *,
    numeric_only: bool = True,
) -> List[str]:
    """問題文（＋小問プロンプト）に正解値が漏れていれば漏洩値リストを返す（ランタイム受理判定）。

    ランタイムは既定で `numeric_only=True`（数値解答の漏洩のみで棄却）。
    非数値解答の漏洩はオフライン G1 が WARN/FAIL で拾う（誤棄却を避ける保守設計）。
    """
    parts: List[str] = [problem_text or ""]
    if sub_prompt_texts:
        parts.extend(t or "" for t in sub_prompt_texts)
    full_text = "\n".join(parts)
    hard, _ambiguous = detect_leaked_values(
        full_text,
        answer_values_from_mr(mr),
        operand_values_from_mr(mr),
        numeric_only=numeric_only,
    )
    return hard
