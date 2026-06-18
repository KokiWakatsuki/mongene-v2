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
            symbols = nouns[0].get_symbols()
            atom_name = type(nouns[0]).__name__
            # Atom 型に応じて適切な metric を自動選択
            preferred_keys = {
                "PrismAtom": ["volume_expr", "surface_area_expr"],
                "PyramidAtom": ["volume_expr", "surface_area_expr"],
                "SphereAtom": ["volume_expr", "surface_area_expr"],
                "CircleAtom": ["area_expr", "circumference_expr"],
                "PolygonAtom": ["area_expr", "perimeter_expr"],
            }
            # measure_type が "area" だが Atom が立体の場合は volume を優先
            if self.measure_type == "area" and atom_name in preferred_keys:
                candidates = preferred_keys[atom_name]
            else:
                key = self._KEY_MAP[self.measure_type]
                candidates = [key] + preferred_keys.get(atom_name, [])

            expr = sympy.Integer(0)
            chosen_key = candidates[0]
            for k in candidates:
                v = symbols.get(k)
                if v is None:
                    continue
                try:
                    if hasattr(v, "is_zero") and v.is_zero:
                        continue
                except Exception:
                    pass
                expr = v
                chosen_key = k
                break

            # narration を選んだ metric に合わせる
            metric_jp = {
                "volume_expr": "体積",
                "surface_area_expr": "表面積",
                "area_expr": "面積",
                "perimeter_expr": "周の長さ",
                "circumference_expr": "円周の長さ",
            }.get(chosen_key, self.measure_type)
            narration = f"{atom_name} の{metric_jp}"
        return LogicStep(
            operation_name=f"measure_{self.measure_type}",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=sympy.simplify(expr),
            narration_hint=narration,
        )
