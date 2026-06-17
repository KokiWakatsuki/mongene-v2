"""FormShapeVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class FormShapeVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["PointAtom", "MovingPointAtom"]
    tags: ClassVar[List[str]] = ["form_shape"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) < 3:
            return False, "多角形には 3 点以上必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        # 退化チェック（簡易: 全頂点が同一でない）
        coords = []
        for n in nouns:
            s = n.get_symbols()
            x = s.get("x")
            y = s.get("y")
            if x is None or y is None:
                continue
            coords.append((str(x), str(y)))
        if len(set(coords)) < 3:
            return False, "頂点が退化している"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        vertices = []
        for n in nouns:
            s = n.get_symbols()
            vertices.append((s.get("x", sympy.Integer(0)), s.get("y", sympy.Integer(0))))
        # Shoelace formula
        n_v = len(vertices)
        area_sum = sympy.Integer(0)
        for i in range(n_v):
            x1, y1 = vertices[i]
            x2, y2 = vertices[(i + 1) % n_v]
            area_sum += x1 * y2 - x2 * y1
        area = sympy.Rational(1, 2) * sympy.Abs(area_sum)
        return LogicStep(
            operation_name="form_shape",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=sympy.simplify(area),
            narration_hint=f"{n_v} 点を結ぶ多角形の面積",
        )
