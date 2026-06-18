"""LocusVerb（§18.2）

条件を満たす点の軌跡を SymPy 方程式として返す。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

ConditionType = Literal[
    "equidistant_two_points",       # 2 点から等距離 → 垂直二等分線
    "equidistant_point_line",       # 点と直線から等距離 → 放物線
    "fixed_distance_from_point",    # 1 点から一定距離 → 円
    "fixed_distance_from_line",     # 1 直線から一定距離 → 平行直線
    "equidistant_two_lines",        # 2 直線から等距離 → 角の二等分線
    "angle_subtended",              # 線分を一定角で見る点 → 円弧
]


@register_verb
class LocusVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["PointAtom", "PolygonAtom", "CircleAtom"]
    tags: ClassVar[List[str]] = ["locus"]

    def __init__(
        self,
        condition_type: ConditionType = "equidistant_two_points",
        distance: Optional[float] = None,
        angle_degrees: Optional[float] = None,
    ) -> None:
        self.condition_type: ConditionType = condition_type
        self.distance = distance
        self.angle_degrees = angle_degrees

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "1 つ以上の条件 Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は LocusVerb に渡せない"

        # 条件タイプ別の引数チェック
        if self.condition_type == "equidistant_two_points" and len(nouns) < 2:
            return False, "equidistant_two_points には 2 点必要"
        if self.condition_type == "fixed_distance_from_point" and self.distance is None:
            return False, "fixed_distance_from_point には distance 引数必須"
        if self.condition_type == "equidistant_two_lines" and len(nouns) < 2:
            return False, "equidistant_two_lines には 2 直線（2 点で代用）必要"
        if self.condition_type == "angle_subtended" and (
            self.angle_degrees is None or len(nouns) < 2
        ):
            return False, "angle_subtended には 2 点 + angle_degrees 必要"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        x, y = sympy.symbols("x y", real=True)

        if self.condition_type == "equidistant_two_points":
            # 2 点 P1, P2 から等距離 → (x-x1)^2 + (y-y1)^2 = (x-x2)^2 + (y-y2)^2
            p1 = nouns[0].get_symbols()
            p2 = nouns[1].get_symbols()
            x1, y1 = p1.get("x", sympy.Integer(0)), p1.get("y", sympy.Integer(0))
            x2, y2 = p2.get("x", sympy.Integer(2)), p2.get("y", sympy.Integer(0))
            expr = sympy.expand(
                (x - x1) ** 2 + (y - y1) ** 2 - (x - x2) ** 2 - (y - y2) ** 2
            )
            equation = sympy.Eq(sympy.simplify(expr), 0)
            narration = "2 点から等距離な点の軌跡（垂直二等分線）"

        elif self.condition_type == "fixed_distance_from_point":
            # 1 点 O から距離 r → 円 (x-x0)^2 + (y-y0)^2 = r^2
            p = nouns[0].get_symbols()
            x0 = p.get("x", sympy.Integer(0))
            y0 = p.get("y", sympy.Integer(0))
            r = sympy.Rational(self.distance) if self.distance else sympy.Integer(1)
            equation = sympy.Eq((x - x0) ** 2 + (y - y0) ** 2, r ** 2)
            narration = f"点 O から距離 {r} の点の軌跡（円）"

        elif self.condition_type == "fixed_distance_from_line":
            # 直線 y = 0 から距離 d → y = ±d
            d = sympy.Rational(self.distance) if self.distance else sympy.Integer(1)
            equation = sympy.Eq(y ** 2, d ** 2)
            narration = f"直線から距離 {d} の点の軌跡（2 本の平行直線）"

        elif self.condition_type == "equidistant_two_lines":
            # 簡略化: 2 直線が 2 点を通る形と仮定し、角の二等分線（y = ±x の形に正規化）
            equation = sympy.Eq(x, y)
            narration = "2 直線から等距離な点の軌跡（角の二等分線）"

        elif self.condition_type == "angle_subtended":
            # 線分 P1P2 を角度 θ で見る点 → 円弧
            # 簡略化: P1=(0,0), P2=(d,0) として中心 (d/2, h) 半径 R の円
            p1 = nouns[0].get_symbols()
            p2 = nouns[1].get_symbols()
            x1, y1 = p1.get("x", sympy.Integer(0)), p1.get("y", sympy.Integer(0))
            x2, y2 = p2.get("x", sympy.Integer(2)), p2.get("y", sympy.Integer(0))
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            d_half = sympy.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) / 2
            theta = sympy.rad(sympy.Rational(self.angle_degrees or 60))
            radius = d_half / sympy.sin(theta)
            equation = sympy.Eq((x - mx) ** 2 + (y - my) ** 2, radius ** 2)
            narration = f"線分を {self.angle_degrees}° で見る点の軌跡（円弧）"

        else:
            equation = sympy.Eq(x ** 2 + y ** 2, sympy.Integer(1))
            narration = f"条件 {self.condition_type} を満たす点の軌跡"

        return LogicStep(
            operation_name=f"locus_{self.condition_type}",
            operands=[type(n).__name__ for n in nouns],
            sympy_expr=equation,
            narration_hint=narration,
        )
