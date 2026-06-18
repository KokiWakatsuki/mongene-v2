"""SubQuestion 構築（§27）"""
from __future__ import annotations

from typing import Dict, List, Optional

import sympy

from apps.api.src.core.abc.atoms import NounAtom
from apps.api.src.core.abc.blueprint import SubQuestionStrategy
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    SubQuestion,
)


def build_sub_questions(
    strategy: Optional[SubQuestionStrategy],
    sampled_nouns: Dict[str, NounAtom],
    logic_steps_all: List[LogicStep],
    logic_steps_by_slot: Optional[Dict[str, LogicStep]] = None,
) -> List[SubQuestion]:
    if not logic_steps_all:
        raise ValueError("logic_steps_all が空")

    if strategy is None or strategy.strategy_type == "single":
        return [
            SubQuestion(
                label="",
                prompt_hint=(strategy.final_question if strategy else "次を求めなさい"),
                logic_steps=list(logic_steps_all),
                answer=_extract_final_answer(logic_steps_all),
            )
        ]

    if strategy.strategy_type == "incremental":
        sub_qs: List[SubQuestion] = []
        use_slots = bool(strategy.intermediate_slots) and logic_steps_by_slot is not None
        for i, intermediate in enumerate(strategy.intermediate_outputs):
            # slot 名指定があれば logic_steps_by_slot[slot] を使う
            if use_slots and i < len(strategy.intermediate_slots):
                slot = strategy.intermediate_slots[i]
                step = logic_steps_by_slot.get(slot) if logic_steps_by_slot else None
                if step is not None:
                    relevant_steps = [step]
                else:
                    relevant_steps = _slice_steps_for(logic_steps_all, intermediate) or [
                        logic_steps_all[min(i, len(logic_steps_all) - 1)]
                    ]
            else:
                relevant_steps = _slice_steps_for(logic_steps_all, intermediate)
                if not relevant_steps:
                    relevant_steps = [logic_steps_all[min(i, len(logic_steps_all) - 1)]]
            sub_qs.append(
                SubQuestion(
                    label=f"({i + 1})",
                    prompt_hint=intermediate,
                    logic_steps=relevant_steps,
                    answer=_extract_intermediate_answer(relevant_steps),
                    depends_on=[f"({j + 1})" for j in range(i)],
                )
            )
        # 最終問題
        if strategy.final_slot and logic_steps_by_slot and strategy.final_slot in logic_steps_by_slot:
            final_steps = [logic_steps_by_slot[strategy.final_slot]]
        else:
            final_steps = list(logic_steps_all)
        sub_qs.append(
            SubQuestion(
                label=f"({len(strategy.intermediate_outputs) + 1})",
                prompt_hint=strategy.final_question,
                logic_steps=final_steps,
                answer=_extract_final_answer(final_steps),
                depends_on=[f"({j + 1})" for j in range(len(strategy.intermediate_outputs))],
            )
        )
        return sub_qs

    if strategy.strategy_type == "guided":
        # ヒント問題 N-1 個 + 本題 1 個。各 intermediate は本題への独立した補助問題
        sub_qs = []
        for i, hint in enumerate(strategy.intermediate_outputs):
            relevant_steps = _slice_steps_for(logic_steps_all, hint)
            if not relevant_steps:
                relevant_steps = [logic_steps_all[min(i, len(logic_steps_all) - 1)]]
            sub_qs.append(
                SubQuestion(
                    label=f"({i + 1})",
                    prompt_hint=f"[ヒント] {hint}",
                    logic_steps=relevant_steps,
                    answer=_extract_intermediate_answer(relevant_steps),
                    depends_on=[],
                )
            )
        sub_qs.append(
            SubQuestion(
                label=f"({len(strategy.intermediate_outputs) + 1})",
                prompt_hint=strategy.final_question,
                logic_steps=list(logic_steps_all),
                answer=_extract_final_answer(logic_steps_all),
                depends_on=[f"({j + 1})" for j in range(len(strategy.intermediate_outputs))],
            )
        )
        return sub_qs

    if strategy.strategy_type == "ladder":
        # 同種の問題を難易度順に並べる: 全 logic_steps を 1 段ずつスライス
        n = max(1, strategy.target_count)
        sub_qs = []
        chunk = max(1, len(logic_steps_all) // n)
        for i in range(n):
            start = i * chunk
            end = (i + 1) * chunk if i < n - 1 else len(logic_steps_all)
            slice_steps = logic_steps_all[start:end] or [logic_steps_all[-1]]
            sub_qs.append(
                SubQuestion(
                    label=f"({i + 1})",
                    prompt_hint=f"{strategy.final_question}（難易度 {i + 1}/{n}）",
                    logic_steps=slice_steps,
                    answer=_extract_intermediate_answer(slice_steps),
                    depends_on=[],
                )
            )
        return sub_qs

    return [
        SubQuestion(
            label="",
            prompt_hint=strategy.final_question or "次を求めなさい",
            logic_steps=list(logic_steps_all),
            answer=_extract_final_answer(logic_steps_all),
        )
    ]


def _slice_steps_for(all_steps: List[LogicStep], intermediate_label: str) -> List[LogicStep]:
    keyword = _extract_keyword(intermediate_label)
    return [
        s
        for s in all_steps
        if keyword in s.narration_hint or keyword in s.operation_name
    ]


def _extract_final_answer(steps: List[LogicStep]) -> AnswerObject:
    if not steps:
        raise ValueError("Empty logic_steps")
    last = steps[-1]

    # Proof 系 Verb の場合は LogicStep.operands の末尾に JSON 化された ProofOutput が入る
    if last.operation_name.startswith("prove_"):
        import json

        proof_output = None
        for operand in last.operands:
            if isinstance(operand, str) and operand.startswith("{"):
                try:
                    proof_output = json.loads(operand)
                    break
                except json.JSONDecodeError:
                    continue
        text_form = (
            proof_output.get("to_prove", "証明された") if proof_output else "証明された"
        )
        return AnswerObject(
            type="proof",
            sympy_form=last.sympy_expr,
            text_form=text_form,
            extras={"proof_output": proof_output} if proof_output else {},
        )

    is_number = bool(getattr(last.sympy_expr, "is_number", False))
    return AnswerObject(
        type="numeric" if is_number else "expression",
        sympy_form=last.sympy_expr,
        text_form=_sympy_to_japanese(last.sympy_expr),
    )


def _extract_intermediate_answer(sub_steps: List[LogicStep]) -> AnswerObject:
    return _extract_final_answer(sub_steps)


def _extract_keyword(label: str) -> str:
    for kw in ["体積", "面積", "長さ", "周", "角度", "角", "確率", "距離", "高さ"]:
        if kw in label:
            return kw
    parts = label.split()
    return parts[-1] if parts else label


def _sympy_to_japanese(expr: sympy.Expr, unit: str = "") -> str:
    if getattr(expr, "is_number", False):
        return f"{expr}{unit}".strip()
    try:
        return f"${sympy.latex(expr)}${unit}".strip()
    except Exception:
        return f"{expr}{unit}".strip()
