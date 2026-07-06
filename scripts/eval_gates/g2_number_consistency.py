"""G2 数値整合 (number_consistency)

spec §3-G2:
- 必要入力数値 = logic_steps[].operands の数値 ＋ sampled_atoms の寸法(dimensions_cm 等)。
- これらが content_problem_text に過不足なく出現するか。
  - 必要数値が欠落 → FAIL（LLMが数値を落とした/改変した）。
  - 入力にも正解にも無い「素性不明の数値」が問題文の数値スロットに出現 → WARN
    （図番号(1)(2)等は許容リストで除外）。

許容リストは `master_data/eval_lexicons.yaml` の `allowed_unattributed_numbers` を使う。
LLM は使わない。
"""
from __future__ import annotations

from typing import Any

from scripts.eval_gates.common import (
    GateResult,
    contains_number,
    dedupe_preserve_order,
    extract_numbers,
    load_lexicons,
)

GATE_ID = "G2"


def _required_input_numbers(ground_truth: dict[str, Any]) -> list[str]:
    """logic_steps[].operands + sampled_atoms の寸法(dimensions_cm等) の数値集合。"""
    values: list[str] = []
    for sq in ground_truth.get("sub_questions", []) or []:
        for step in sq.get("logic_steps", []) or []:
            for operand in step.get("operands", []) or []:
                values.append(str(operand))

    sampled_atoms = ground_truth.get("sampled_atoms", {}) or {}
    for atom_info in sampled_atoms.values():
        if not isinstance(atom_info, dict):
            continue
        dims = atom_info.get("dimensions_cm", {}) or {}
        for dim_value in dims.values():
            values.append(str(dim_value))
    return dedupe_preserve_order(values)


def _answer_numbers(ground_truth: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for sq in ground_truth.get("sub_questions", []) or []:
        answer = sq.get("answer") or {}
        for key in ("sympy_form", "text_form"):
            v = answer.get(key)
            if v:
                values.append(str(v))
    return values


def check(product: dict[str, Any], ground_truth: dict[str, Any]) -> GateResult:
    required = _required_input_numbers(ground_truth)
    content = product.get("content_problem_text", "") or ""

    missing = [v for v in required if v.strip() not in ("", "None") and not contains_number(content, v)]

    if missing:
        return GateResult(
            GATE_ID,
            "FAIL",
            f"必要な入力数値が問題文に欠落: {missing}",
            details={"missing": missing, "required": required},
        )

    # 素性不明の数値チェック（WARN）
    lexicons = load_lexicons()
    allowed_unattributed = set(str(x) for x in lexicons.get("allowed_unattributed_numbers", []))

    known_numbers = set()
    for v in required + _answer_numbers(ground_truth):
        known_numbers.update(extract_numbers(v))
    known_numbers.update(allowed_unattributed)

    content_numbers = extract_numbers(content)
    unknown = [
        n for n in content_numbers
        if n not in allowed_unattributed and not any(contains_number(n, k) or contains_number(k, n) for k in known_numbers)
    ]
    unknown = dedupe_preserve_order(unknown)

    if unknown:
        return GateResult(
            GATE_ID,
            "WARN",
            f"入力にも正解にも無い素性不明の数値が出現: {unknown}",
            details={"unknown_numbers": unknown},
        )

    if not required:
        return GateResult(GATE_ID, "N/A", "ground truth に必要入力数値が見つからない")

    return GateResult(GATE_ID, "PASS", "必要数値がすべて問題文に出現し、過不足なし")
