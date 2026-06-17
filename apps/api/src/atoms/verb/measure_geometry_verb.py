"""MeasureGeometryVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

MeasureType = Literal["distance", "arc_length", "perimeter", "area", "volume", "surface_area"]


@register_verb
class MeasureGeometryVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "PointAtom",
        "PolygonAtom",
        "CircleAtom",
        "PrismAtom",
        "PyramidAtom",
        "SphereAtom",
    ]
    tags: ClassVar[List[str]] = ["measure_geometry"]

    _KEY_MAP = {
        "area": "area_expr",
        "perimeter": "perimeter_expr",
        "arc_length": "arc_length_expr",
        "volume": "volume_expr",
        "surface_area": "surface_area_expr",
    }

    def __init__(self, measure_type: MeasureType = "area") -> None:
        self.measure_type: MeasureType = measure_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "1 つ以上の Atom を要求"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        if self.measure_type == "distance" and len(nouns) < 2:
            return False, "distance には 2 点必要"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        if self.measure_type == "distance":
            s1 = nouns[0].get_symbols()
            s2 = nouns[1].get_symbols()
            x1, y1 = s1.get("x", sympy.Integer(0)), s1.get("y", sympy.Integer(0))
            x2, y2 = s2.get("x", sympy.Integer(0)), s2.get("y", sympy.Integer(0))
            expr = sympy.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            narration = "2 点間の距離（三平方の定理）"
        else:
            key = self._KEY_MAP[self.measure_type]
            symbols = nouns[0].get_symbols()
            expr = symbols.get(key, sympy.Integer(0))
            narration = f"{type(nouns[0]).__name__} の {self.measure_type}"
        return LogicStep(
            operation_name=f"measure_{self.measure_type}",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=sympy.simplify(expr),
            narration_hint=narration,
        )
