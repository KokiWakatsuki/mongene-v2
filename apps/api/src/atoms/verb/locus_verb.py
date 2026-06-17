"""LocusVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class LocusVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["PointAtom", "PolygonAtom", "CircleAtom"]
    tags: ClassVar[List[str]] = ["locus"]

    def __init__(self, condition_type: str = "equidistant") -> None:
        self.condition_type = condition_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "1 つ以上の条件 Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        x, y = sympy.symbols("x y")
        if self.condition_type == "equidistant" and len(nouns) >= 2:
            # 2 点から等距離 → 垂直二等分線
            p1 = nouns[0].get_symbols()
            p2 = nouns[1].get_symbols()
            x1, y1 = p1.get("x", sympy.Integer(0)), p1.get("y", sympy.Integer(0))
            x2, y2 = p2.get("x", sympy.Integer(1)), p2.get("y", sympy.Integer(0))
            expr = sympy.simplify((x - x1) ** 2 + (y - y1) ** 2 - ((x - x2) ** 2 + (y - y2) ** 2))
            narration = "2 点から等距離 → 垂直二等分線"
        else:
            expr = sympy.Eq(x ** 2 + y ** 2, sympy.Integer(1))
            narration = f"条件 {self.condition_type} を満たす点の軌跡"
        return LogicStep(
            operation_name="locus",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=expr,
            narration_hint=narration,
        )
