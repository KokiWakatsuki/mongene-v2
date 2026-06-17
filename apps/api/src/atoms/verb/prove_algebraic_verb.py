"""ProveAlgebraicVerb（§18.2, §26）"""
from __future__ import annotations

import json
import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class ProveAlgebraicVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["NumberAtom", "PolynomialAtom"]
    tags: ClassVar[List[str]] = ["proof", "algebraic"]

    def __init__(self, proof_type: str = "even_odd") -> None:
        self.proof_type = proof_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "命題は 1 つの Atom に対応"
        n = nouns[0]
        if type(n).__name__ not in self.accepted_noun_types:
            return False, f"{type(n).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        steps = [
            {"step_number": 1, "statement": "変数を定義する（例: 2n, 2n+1）", "reason": "仮定", "references": []},
            {"step_number": 2, "statement": "式を展開・整理する", "reason": "代数演算", "references": [1]},
            {"step_number": 3, "statement": "結論を導く", "reason": f"{self.proof_type} の性質", "references": [2]},
        ]
        proof_output = {
            "given": ["対象を変数で表す"],
            "to_prove": f"{self.proof_type} に関する命題",
            "steps": steps,
            "conclusion": "よって命題は成り立つ",
        }
        return LogicStep(
            operation_name="prove_algebraic",
            operands=[type(atom).__name__, json.dumps(proof_output, ensure_ascii=False)],
            sympy_expr=sympy.Integer(1),
            narration_hint=f"{self.proof_type} に関する代数的証明（{len(steps)} ステップ）",
        )
