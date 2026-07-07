"""G1 答え漏洩 (answer_leakage)

spec `docs/phase2_eval_gates_spec.md` §3-G1:
- 正解値の集合 = 各 sub_question の「最終出力」= logic_steps 末尾の sympy_expr、
  および answer.sympy_form/text_form。
- content_problem_text（＋各 sub_question の prompt_text）に正解値が出現したら FAIL。
- 例外: 正解値がたまたま入力オペランド(G2の必要数値)と一致する場合は誤検出になりうるので
  WARN に格下げ。

LLM は使わない。純粋な文字列/数値の正規化突合のみ。
"""
from __future__ import annotations

from typing import Any

from apps.api.src.core.evaluation.leakage import detect_leaked_values
from scripts.eval_gates.common import GateResult, dedupe_preserve_order

GATE_ID = "G1"


def _answer_values(ground_truth: dict[str, Any]) -> list[str]:
    """ground truth から「正解値」の集合を集める（sympy_form/text_form + 末尾 logic_step）。"""
    values: list[str] = []
    for sq in ground_truth.get("sub_questions", []) or []:
        answer = sq.get("answer") or {}
        for key in ("sympy_form", "text_form"):
            v = answer.get(key)
            if v is not None and str(v).strip() and str(v).strip().lower() != "none":
                values.append(str(v))
        logic_steps = sq.get("logic_steps", []) or []
        if logic_steps:
            last = logic_steps[-1]
            expr = last.get("sympy_expr")
            if expr is not None and str(expr).strip() and str(expr).strip().lower() != "none":
                values.append(str(expr))
    return dedupe_preserve_order(values)


def _input_operands(ground_truth: dict[str, Any]) -> list[str]:
    """G2 と同じ「必要入力数値」= logic_steps[].operands の数値集合。"""
    operands: list[str] = []
    for sq in ground_truth.get("sub_questions", []) or []:
        for step in sq.get("logic_steps", []) or []:
            for operand in step.get("operands", []) or []:
                operands.append(str(operand))
    return dedupe_preserve_order(operands)


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    """content_problem_text（+ prompt_text）に正解値が漏洩していないか判定する。"""
    answer_values = _answer_values(ground_truth)
    if not answer_values:
        return GateResult(GATE_ID, "N/A", "ground truth に答え値が見つからない")

    content = product.get("content_problem_text", "") or ""
    prompt_texts = [
        sq.get("prompt_text", "") or "" for sq in product.get("sub_questions", []) or []
    ]
    full_text = content + "\n" + "\n".join(prompt_texts)

    operand_values = _input_operands(ground_truth)

    # ランタイム翻訳器と同一の共有コアで判定する（evaluator = verifier）。
    leaked, leaked_but_also_operand = detect_leaked_values(
        full_text, answer_values, operand_values
    )

    if leaked:
        return GateResult(
            GATE_ID,
            "FAIL",
            f"正解値が問題文に出現: {leaked}",
            details={"leaked": leaked},
        )
    if leaked_but_also_operand:
        return GateResult(
            GATE_ID,
            "WARN",
            f"正解値と一致する数値が出現するが、入力オペランドとも一致するため誤検出の可能性: {leaked_but_also_operand}",
            details={"ambiguous": leaked_but_also_operand},
        )
    return GateResult(GATE_ID, "PASS", "正解値の漏洩なし")
