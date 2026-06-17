"""IntersectVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class IntersectVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = [
        "LinearFuncAtom",
        "QuadraticFuncAtom",
        "PolygonAtom",
        "CircleAtom",
    ]
    tags: ClassVar[List[str]] = ["intersect"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 2:
            return False, "2 つの関数/図形が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        # 簡易：両方 LinearFuncAtom で slope が同じなら平行（解なし）
        if all(type(n).__name__ == "LinearFuncAtom" for n in nouns):
            s1 = nouns[0].get_symbols().get("slope")
            s2 = nouns[1].get_symbols().get("slope")
            if s1 is not None and s2 is not None and sympy.simplify(s1 - s2) == 0:
                return False, "平行直線（交点なし）"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        x = sympy.Symbol("x")
        e1 = nouns[0].get_symbols().get("expression")
        e2 = nouns[1].get_symbols().get("expression")
        if e1 is None or e2 is None:
            sols = []
        else:
            try:
                sols = sympy.solve(e1 - e2, x)
            except Exception:
                sols = []
        if sols:
            points = [sympy.Tuple(s, e1.subs(x, s)) for s in sols]
            expr = sympy.FiniteSet(*points) if len(points) > 1 else points[0]
        else:
            expr = sympy.Integer(0)
        return LogicStep(
            operation_name="intersect",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=expr,
            narration_hint="2 関数/図形の交点を求める",
        )
