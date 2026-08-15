"""SubQuestion 構築（§27）"""
from __future__ import annotations

import re
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
        hint = strategy.final_question if strategy else "次を求めなさい"
        # §12.1: 計算問題 / 方程式問題は operands から式を生成して prompt_hint に追加
        if logic_steps_all:
            last_op = logic_steps_all[-1].operation_name
            if last_op.startswith("arithmetic_") or last_op in ("solve_equation", "solve_proportion", "factorize"):
                hint = _augment_prompt_hint(hint, logic_steps_all[-1])
        return [
            SubQuestion(
                label="",
                prompt_hint=hint,
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

    # Knowledge 系 Verb: narration_hint が問いの概念テキストになっている
    if last.operation_name == "knowledge_check":
        hint = last.narration_hint or "概念確認"
        return AnswerObject(
            type="knowledge",
            sympy_form=None,
            text_form="（概念説明・用語定義）",
            extras={"knowledge_hint": hint},
        )

    # Construction 系 Verb の場合は LogicStep.operands の末尾に JSON 化された steps リストが入る
    if last.operation_name.startswith("construct_"):
        import json

        construction_steps = None
        for operand in reversed(last.operands):
            if isinstance(operand, str) and operand.startswith("["):
                try:
                    construction_steps = json.loads(operand)
                    break
                except json.JSONDecodeError:
                    continue
        return AnswerObject(
            type="expression",
            sympy_form=last.sympy_expr,
            text_form=last.narration_hint,
            extras={"construction_steps": construction_steps} if construction_steps else {},
        )

    is_number = bool(getattr(last.sympy_expr, "is_number", False))
    return AnswerObject(
        type="numeric" if is_number else "expression",
        sympy_form=last.sympy_expr,
        text_form=_sympy_to_japanese(last.sympy_expr),
    )


def _extract_intermediate_answer(sub_steps: List[LogicStep]) -> AnswerObject:
    return _extract_final_answer(sub_steps)


_OP_SYMBOL = {
    "arithmetic_+": "+",
    "arithmetic_-": "-",
    "arithmetic_*": "\\times",
    "arithmetic_/": "\\div",
    "arithmetic_**": "^",
    "solve_equation": "=",
}


def _operand_to_latex(op_str: str) -> str:
    """operand 文字列を SymPy 経由で LaTeX に変換する"""
    try:
        expr = sympy.sympify(op_str)
        return sympy.latex(expr)
    except Exception:
        # SymPy で解析できない場合はそのまま（Python の ** 等を残す）
        return op_str


def _format_calc_expression(step: LogicStep) -> str:
    """§12.1: 計算問題・方程式問題用に operands から LaTeX 式を生成する。

    arithmetic_ 系: '$(-3x^{2} - x - 2) + ...$'
    solve_equation: '$lhs = rhs$'
    """
    sym = _OP_SYMBOL.get(step.operation_name, "")
    ops = [o for o in step.operands if not o.startswith("{")]  # JSON chunk を除外

    # 方程式 "lhs = rhs" の特別処理
    if step.operation_name == "solve_equation" and len(ops) >= 2:
        lhs_latex = _operand_to_latex(ops[0])
        rhs_latex = _operand_to_latex(ops[1])
        return f"${lhs_latex} = {rhs_latex}$"

    # 比例式 "a:b = c:x" の特別処理
    if step.operation_name == "solve_proportion" and len(ops) >= 3:
        return f"${ops[0]}:{ops[1]} = {ops[2]}:x$"

    # 因数分解 "展開形 を因数分解" の特別処理
    if step.operation_name == "factorize" and len(ops) >= 1:
        try:
            expr = sympy.sympify(ops[0])
            return f"${sympy.latex(expr)}$"
        except Exception:
            return f"${ops[0]}$"

    if sym and len(ops) >= 2:
        latex_ops = [_operand_to_latex(o) for o in ops]

        def _wrap(s: str) -> str:
            # 多項式や負の式はカッコで包む
            if s.startswith("-") or "+" in s or "-" in s[1:]:
                return f"\\left({s}\\right)"
            return s

        terms = [_wrap(latex_ops[0])] + [f"{sym} {_wrap(lt)}" for lt in latex_ops[1:]]
        return "$" + " ".join(terms) + "$"
    return ""


def _augment_prompt_hint(hint: str, step: LogicStep) -> str:
    """計算問題の prompt_hint に実際の式を追加する（§12.1 operands の活用）"""
    expr = _format_calc_expression(step)
    if not expr:
        return hint
    # 既に式が含まれていれば追加しない
    if "$" in hint:
        return hint
    return f"{hint}\n{expr}"


def _extract_keyword(label: str) -> str:
    for kw in ["体積", "面積", "長さ", "周", "角度", "角", "確率", "距離", "高さ"]:
        if kw in label:
            return kw
    parts = label.split()
    return parts[-1] if parts else label


def _sympy_to_japanese(expr: sympy.Expr, unit: str = "") -> str:
    # 整数のみ素のテキスト表現、それ以外（分数・根号等）は LaTeX で返す
    if isinstance(expr, sympy.Integer):
        return f"{expr}{unit}".strip()
    try:
        return f"${sympy.latex(expr)}${unit}".strip()
    except Exception:
        return f"{expr}{unit}".strip()
