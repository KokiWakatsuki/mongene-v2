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
    "exterior_angle_sum",     # 多角形の外角の和（= 360）
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
            # inscribed_angle_expr が優先（circle_angle_atom.py の get_symbols() が公開するキー）
            expr = symbols.get("inscribed_angle_expr") or symbols.get("inscribed_angle", sympy.Integer(30))
        elif self.theorem == "interior_angle_sum" and name == "PolygonAtom":
            # n_sides キーを使う（vertices は get_symbols() から公開されない）
            n_sides_sym = symbols.get("n_sides")
            num_sides = int(n_sides_sym) if n_sides_sym is not None else 3
            expr = sympy.Integer(180 * (num_sides - 2))
        elif self.theorem == "exterior_angle" and name == "PolygonAtom":
            # 正n角形の1つの外角 = 360/n [°]
            n_sides_sym = symbols.get("n_sides")
            num_sides = int(n_sides_sym) if n_sides_sym is not None else 3
            expr = sympy.Rational(360, num_sides)
        elif self.theorem == "exterior_angle_sum":
            # 凸多角形の外角の和は常に 360°（多角形の種類によらない）
            expr = sympy.Integer(360)
        else:
            expr = sympy.Integer(90)
        return LogicStep(
            operation_name=f"find_angle_{self.theorem}",
            operands=[name],
            sympy_expr=sympy.simplify(expr),
            narration_hint=f"{self.theorem} により角度を求める",
        )
