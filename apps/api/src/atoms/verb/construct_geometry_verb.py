"""ConstructGeometryVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

ConstructionType = Literal[
    "perp_bisector", "angle_bisector", "perpendicular", "tangent", "copy_length"
]


@register_verb
class ConstructGeometryVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "PointAtom",
        "PolygonAtom",
        "CircleAtom",
        "LineAngleAtom",
    ]
    tags: ClassVar[List[str]] = ["construction"]

    def __init__(self, construction_type: ConstructionType = "perp_bisector") -> None:
        self.construction_type: ConstructionType = construction_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "少なくとも 1 つの Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        steps_data = {
            "perp_bisector": [
                {"step": 1, "action": "draw_circle", "params": {"center": "A", "radius": "AB"}},
                {"step": 2, "action": "draw_circle", "params": {"center": "B", "radius": "AB"}},
                {"step": 3, "action": "connect_intersections"},
            ],
            "angle_bisector": [
                {"step": 1, "action": "draw_arc", "params": {"center": "vertex"}},
                {"step": 2, "action": "draw_circles_from_arc_points"},
                {"step": 3, "action": "connect_vertex_to_intersection"},
            ],
            "perpendicular": [
                {"step": 1, "action": "draw_circle_around_point"},
                {"step": 2, "action": "construct_perp_bisector_of_segment"},
            ],
            "tangent": [
                {"step": 1, "action": "draw_circle_through_center_and_external_point"},
                {"step": 2, "action": "intersect_with_target_circle"},
                {"step": 3, "action": "connect_external_point_to_intersection"},
            ],
            "copy_length": [
                {"step": 1, "action": "open_compass_to_length"},
                {"step": 2, "action": "mark_arc_from_new_point"},
            ],
        }
        steps = steps_data[self.construction_type]
        return LogicStep(
            operation_name=f"construct_{self.construction_type}",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=sympy.Integer(len(steps)),
            narration_hint=f"{self.construction_type} の作図（{len(steps)} ステップ）",
        )
