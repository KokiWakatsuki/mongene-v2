"""FindAngleVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Theorem = Literal[
    "parallel_alternate",
    "interior_angle_sum",
    "exterior_angle",
    "inscribed_angle",
    "tangent_chord",
    "inscribed_quadrilateral",
]


@register_verb
class FindAngleVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["LineAngleAtom", "CircleAngleAtom", "PolygonAtom"]
    tags: ClassVar[List[str]] = ["angle_calculation"]

    def __init__(self, theorem: Theorem = "parallel_alternate") -> None:
        self.theorem: Theorem = theorem

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "1 つ以上の角度 Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        n = nouns[0]
        name = type(n).__name__
        symbols = n.get_symbols()

        if self.theorem == "parallel_alternate" and name == "LineAngleAtom":
            expr = symbols.get("target_angle_expr") or symbols.get("known_angle", sympy.Integer(60))
        elif self.theorem == "inscribed_angle" and name == "CircleAngleAtom":
            expr = symbols.get("inscribed_angle_expr", sympy.Integer(30))
        elif self.theorem == "interior_angle_sum" and name == "PolygonAtom":
            # 内角和 = 180(n-2) [°]
            vertices = symbols.get("vertices")
            num_sides = 3 if vertices is None else len(vertices)
            expr = sympy.Integer(180 * (num_sides - 2))
        else:
            expr = sympy.Integer(90)
        return LogicStep(
            operation_name=f"find_angle_{self.theorem}",
            operands=[name],
            sympy_expr=sympy.simplify(expr),
            narration_hint=f"{self.theorem} により角度を求める",
        )
