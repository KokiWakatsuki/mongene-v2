"""PythagoreanLengthVerb（三平方の定理で辺を求める）

a² + b² = c² を SymPy で厳密計算する。
accepted: PolygonAtom(right_triangle) または NumberAtom × 2（脚の長さ）
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Mode = Literal["hypotenuse", "leg_from_hypotenuse_and_leg"]


@register_verb
class PythagoreanLengthVerb(VerbAtom):
    """三平方の定理 a² + b² = c² で辺の長さを求める。

    mode="hypotenuse": 2 脚 a, b → 斜辺 c = sqrt(a² + b²)
    mode="leg_from_hypotenuse_and_leg": 斜辺 c と 1 脚 a → 他の脚 b = sqrt(c² - a²)
    """

    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "PolygonAtom",  # right_triangle の 2 脚
        "NumberAtom",   # 長さを数値で直接渡す場合
        "PrismAtom",    # 直方体の対角線
        "PyramidAtom",  # 角錐の母線
        "PointAtom",    # 座標平面上の 2 点間の距離
    ]
    tags: ClassVar[List[str]] = ["pythagorean", "plane_geometry", "coordinate"]

    def __init__(self, mode: Mode = "hypotenuse") -> None:
        self.mode: Mode = mode

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) < 1:
            return False, "少なくとも 1 つの Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は PythagoreanLengthVerb に渡せない"

        # PolygonAtom の場合は right_triangle であること
        for n in nouns:
            if type(n).__name__ == "PolygonAtom":
                if getattr(n, "polygon_type", "") not in (
                    "right_triangle", "isoceles_right_triangle", "triangle"
                ):
                    return False, "PolygonAtom は直角三角形である必要がある"

        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        # PointAtom が 2 つある → 座標平面上の 2 点間の距離
        if len(nouns) >= 2 and all(type(n).__name__ == "PointAtom" for n in nouns[:2]):
            return self._from_two_points(nouns[0], nouns[1])

        # PolygonAtom から 2 辺を取得
        if type(nouns[0]).__name__ == "PolygonAtom":
            return self._from_polygon(nouns[0], rng)

        # PrismAtom: 底面対角線または空間対角線
        if type(nouns[0]).__name__ == "PrismAtom":
            return self._from_prism(nouns[0])

        # PyramidAtom: 斜辺（母線）の計算
        if type(nouns[0]).__name__ == "PyramidAtom":
            return self._from_pyramid(nouns[0])

        # NumberAtom × 2
        syms0 = nouns[0].get_symbols()
        syms1 = nouns[1].get_symbols() if len(nouns) > 1 else syms0
        a = syms0.get("value", sympy.Integer(3))
        b = syms1.get("value", sympy.Integer(4))
        return self._compute(a, b)

    def _from_polygon(self, poly: NounAtom, rng: random.Random) -> LogicStep:
        sides = getattr(poly, "side_lengths", [])
        if len(sides) >= 3:
            sides_sorted = sorted([sympy.nsimplify(s) for s in sides if s])
            a, b, c = sides_sorted[0], sides_sorted[1], sides_sorted[2]
            # c が斜辺か確認（最長辺）
            if self.mode == "hypotenuse":
                result = c  # 三角形の最長辺が斜辺
                narration = f"三平方の定理 $c = \\sqrt{{a^2 + b^2}}$ を使って斜辺を求める"
                return LogicStep(
                    operation_name="pythagorean_hypotenuse",
                    operands=[str(a), str(b)],
                    sympy_expr=sympy.simplify(c),
                    narration_hint=narration,
                )
        # 2 辺から斜辺を計算
        verts = getattr(poly, "vertices", [])
        if len(verts) >= 3:
            v = [sympy.nsimplify(x) for pt in verts for x in pt]
            # 直角三角形の脚を SymPy で推定（座標から計算）
            try:
                pts = list(poly.vertices)
                dists = [
                    sympy.sqrt((pts[i][0] - pts[j][0])**2 + (pts[i][1] - pts[j][1])**2)
                    for i, j in [(0,1),(1,2),(0,2)]
                ]
                dists_sorted = sorted([sympy.simplify(d) for d in dists])
                a, b = dists_sorted[0], dists_sorted[1]
                return self._compute(a, b)
            except Exception:
                pass
        return self._compute(sympy.Integer(3), sympy.Integer(4))

    def _from_prism(self, prism: NounAtom) -> LogicStep:
        sym = prism.get_symbols()
        w = sym.get("width", sympy.Integer(3))
        d = sym.get("depth", sympy.Integer(4))
        h = sym.get("height", sympy.Integer(5))
        # 空間対角線 = sqrt(w² + d² + h²)
        diagonal = sympy.sqrt(w**2 + d**2 + h**2)
        return LogicStep(
            operation_name="pythagorean_space_diagonal",
            operands=[str(w), str(d), str(h)],
            sympy_expr=sympy.simplify(diagonal),
            narration_hint=f"直方体の空間対角線 = $\\sqrt{{w^2 + d^2 + h^2}}$",
        )

    def _from_pyramid(self, pyramid: NounAtom) -> LogicStep:
        sym = pyramid.get_symbols()
        base_side = sym.get("base_side", sympy.Integer(6))
        height = sym.get("height", sympy.Integer(4))
        # 正四角錐の斜高 l = sqrt((base_side/2)² + height²)
        half = base_side / 2
        slant_height = sympy.sqrt(half**2 + height**2)
        # 母線 e = sqrt((base_side*sqrt(2)/2)² + height²)
        slant_edge = sympy.sqrt((base_side * sympy.sqrt(2) / 2)**2 + height**2)
        return LogicStep(
            operation_name="pythagorean_slant_edge",
            operands=[str(base_side), str(height)],
            sympy_expr=sympy.simplify(slant_edge),
            narration_hint=f"正四角錐の母線 = $\\sqrt{{(\\frac{{base}}{{\\sqrt{{2}}}})^2 + h^2}}$",
        )

    def _from_two_points(self, p1: NounAtom, p2: NounAtom) -> LogicStep:
        """座標平面上の 2 点 A(x1,y1), B(x2,y2) の距離 = sqrt((x2-x1)^2 + (y2-y1)^2)"""
        s1 = p1.get_symbols()
        s2 = p2.get_symbols()
        x1, y1 = s1.get("x", sympy.Integer(0)), s1.get("y", sympy.Integer(0))
        x2, y2 = s2.get("x", sympy.Integer(0)), s2.get("y", sympy.Integer(0))
        dx = x2 - x1
        dy = y2 - y1
        dist = sympy.sqrt(dx**2 + dy**2)
        return LogicStep(
            operation_name="pythagorean_distance",
            operands=[f"({x1},{y1})", f"({x2},{y2})"],
            sympy_expr=sympy.simplify(dist),
            narration_hint=f"2点間の距離 = $\\sqrt{{({dx})^2+({dy})^2}}$",
        )

    def _compute(self, a: sympy.Expr, b: sympy.Expr) -> LogicStep:
        if self.mode == "hypotenuse":
            result = sympy.sqrt(a**2 + b**2)
            narration = f"三平方の定理: $c = \\sqrt{{a^2 + b^2}} = \\sqrt{{{a}^2 + {b}^2}}$"
        else:
            # leg: b = sqrt(c² - a²) ← a が脚, b が斜辺の役割を入れ替える
            result = sympy.sqrt(b**2 - a**2)
            narration = f"三平方の定理: $a = \\sqrt{{c^2 - b^2}} = \\sqrt{{{b}^2 - {a}^2}}$"
        return LogicStep(
            operation_name=f"pythagorean_{self.mode}",
            operands=[str(a), str(b)],
            sympy_expr=sympy.simplify(result),
            narration_hint=narration,
        )
