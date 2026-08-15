"""EstimatePopulationVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

EstimationType = Literal["proportion", "mean", "total_count"]


@register_verb
class EstimatePopulationVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["SampleAtom"]
    tags: ClassVar[List[str]] = ["estimation", "sampling"]

    def __init__(self, estimation_type: EstimationType = "total_count") -> None:
        self.estimation_type: EstimationType = estimation_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "SampleAtom 1 つを要求"
        s = nouns[0]
        if type(s).__name__ != "SampleAtom":
            return False, "SampleAtom のみ受理"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        s = nouns[0]
        symbols = s.get_symbols()
        expr = symbols.get("population_estimate", sympy.Integer(0))
        return LogicStep(
            operation_name=f"estimate_{self.estimation_type}",
            operands=["SampleAtom"],
            sympy_expr=sympy.simplify(expr),
            narration_hint=f"標本から母集団の {self.estimation_type} を推定",
        )
