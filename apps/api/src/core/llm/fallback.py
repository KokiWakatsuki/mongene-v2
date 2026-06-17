"""LLM 翻訳失敗時のテンプレ展開（§35.4）"""
from __future__ import annotations

import sympy

from apps.api.src.core.representation.middle_representation import MiddleRepresentation


def template_fallback_text(mr: MiddleRepresentation) -> str:
    """LLM 翻訳がすべて失敗した時の最後の砦"""
    lines: list[str] = []
    for sq in mr.sub_questions:
        label = f"{sq.label} " if sq.label else ""
        lines.append(f"{label}{sq.prompt_hint}")
        for step in sq.logic_steps:
            try:
                expr_str = sympy.latex(step.sympy_expr)
            except Exception:
                expr_str = str(step.sympy_expr)
            lines.append(f"  {step.narration_hint}: ${expr_str}$")
    return "\n".join(lines)
