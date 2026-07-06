"""KnowledgeCheckVerb（knowledge form 専用）

NumberAtom を受け取り、operation_name="knowledge_check" の LogicStep を返す。
_augment_prompt_hint は arithmetic_*/solve_equation にのみ反応するため、
このVerbを経由した場合は final_question がそのまま prompt_hint になる。
"""
from __future__ import annotations

from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class KnowledgeCheckVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["NumberAtom"]
    tags: ClassVar[List[str]] = ["knowledge"]

    def __init__(self, hints: List[str] | None = None) -> None:
        # 複数の knowledge_hint 候補を持ち、seed でサンプルすることで E 評価（重複なし）を担保
        self.hints: List[str] = hints or []

    def validate(self, noun: NounAtom) -> Tuple[bool, Optional[str]]:
        return True, None

    def solve(self, noun: NounAtom, rng=None) -> LogicStep:
        # rng があれば hints からランダムに選んで問いのバリエーションを確保
        if self.hints and rng:
            hint = rng.choice(self.hints)
        elif self.hints:
            hint = self.hints[0]
        else:
            hint = "概念確認"
        return LogicStep(
            operation_name="knowledge_check",
            operands=[hint],
            sympy_expr=sympy.Integer(1),
            narration_hint=hint,
        )
