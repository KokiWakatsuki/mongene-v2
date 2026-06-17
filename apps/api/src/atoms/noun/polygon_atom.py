"""PolygonAtom（§17.1, §18.1）

多角形（三角形、四角形、正多角形）を表す Noun Atom。
頂点座標から辺長・面積・周長を導出する。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_VALID_POLYGON_TYPES = {
    "triangle",
    "right_triangle",
    "isoceles_triangle",
    "equilateral_triangle",
    "square",
    "rectangle",
    "parallelogram",
    "rhombus",
    "trapezoid",
    "regular_polygon",
}


@register_noun
class PolygonAtom(NounAtom):
    tags: ClassVar[List[str]] = ["plane_geometry", "triangle", "rectangle"]

    def __init__(
        self,
        polygon_type: str = "triangle",
        vertices: List[Tuple[sympy.Expr, sympy.Expr]] | None = None,
        n_sides: int = 3,
    ) -> None:
        self.polygon_type: str = polygon_type
        self.n_sides: int = n_sides
        if vertices is None:
            # デフォルト：単位直角三角形
            self.vertices: List[Tuple[sympy.Expr, sympy.Expr]] = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(1), sympy.Integer(0)),
                (sympy.Integer(0), sympy.Integer(1)),
            ]
        else:
            self.vertices = vertices

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "PolygonAtom":
        custom = constraints.custom or {}
        polygon_type: str = str(custom.get("polygon_type", "triangle"))
        if polygon_type not in _VALID_POLYGON_TYPES:
            polygon_type = "triangle"
        max_side: int = int(custom.get("max_side_length", 10))
        if max_side < 2:
            max_side = 2
        force_integer_coords: bool = bool(custom.get("force_integer_coords", True))
        n_sides_in: int = int(custom.get("n_sides", 5))

        vertices: List[Tuple[sympy.Expr, sympy.Expr]] = []
        n_sides = 3

        if polygon_type == "triangle":
            # 一般三角形：3 点ランダム（退化を避ける）
            for _ in range(20):
                pts = [
                    (rng.randint(0, max_side), rng.randint(0, max_side))
                    for _ in range(3)
                ]
                # 面積 != 0 をチェック
                (x1, y1), (x2, y2), (x3, y3) = pts
                area2 = (x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)
                if area2 != 0:
                    vertices = [(sympy.Integer(x), sympy.Integer(y)) for x, y in pts]
                    break
            if not vertices:
                vertices = [
                    (sympy.Integer(0), sympy.Integer(0)),
                    (sympy.Integer(max_side), sympy.Integer(0)),
                    (sympy.Integer(0), sympy.Integer(max_side)),
                ]
            n_sides = 3
        elif polygon_type == "right_triangle":
            a = rng.randint(1, max_side)
            b = rng.randint(1, max_side)
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(a), sympy.Integer(0)),
                (sympy.Integer(0), sympy.Integer(b)),
            ]
            n_sides = 3
        elif polygon_type == "isoceles_triangle":
            base = rng.randint(2, max_side)
            h = rng.randint(1, max_side)
            base_half = sympy.Rational(base, 2)
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(base), sympy.Integer(0)),
                (base_half, sympy.Integer(h)),
            ]
            n_sides = 3
        elif polygon_type == "equilateral_triangle":
            a = rng.randint(1, max_side)
            # 正三角形：(0,0),(a,0),(a/2, a*sqrt(3)/2)
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(a), sympy.Integer(0)),
                (sympy.Rational(a, 2), sympy.Rational(a, 2) * sympy.sqrt(3)),
            ]
            n_sides = 3
        elif polygon_type == "square":
            a = rng.randint(1, max_side)
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(a), sympy.Integer(0)),
                (sympy.Integer(a), sympy.Integer(a)),
                (sympy.Integer(0), sympy.Integer(a)),
            ]
            n_sides = 4
        elif polygon_type == "rectangle":
            w = rng.randint(1, max_side)
            h = rng.randint(1, max_side)
            while h == w:
                h = rng.randint(1, max_side)
                if max_side == 1:
                    break
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(w), sympy.Integer(0)),
                (sympy.Integer(w), sympy.Integer(h)),
                (sympy.Integer(0), sympy.Integer(h)),
            ]
            n_sides = 4
        elif polygon_type == "parallelogram":
            w = rng.randint(2, max_side)
            h = rng.randint(1, max_side)
            shift = rng.randint(1, max(1, max_side // 2))
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(w), sympy.Integer(0)),
                (sympy.Integer(w + shift), sympy.Integer(h)),
                (sympy.Integer(shift), sympy.Integer(h)),
            ]
            n_sides = 4
        elif polygon_type == "rhombus":
            # 対角線が直交する菱形：対角線長 2p, 2q
            p = rng.randint(1, max(1, max_side // 2))
            q = rng.randint(1, max(1, max_side // 2))
            vertices = [
                (sympy.Integer(0), sympy.Integer(-q)),
                (sympy.Integer(p), sympy.Integer(0)),
                (sympy.Integer(0), sympy.Integer(q)),
                (sympy.Integer(-p), sympy.Integer(0)),
            ]
            n_sides = 4
        elif polygon_type == "trapezoid":
            top = rng.randint(1, max(1, max_side - 1))
            bottom = top + rng.randint(1, max(1, max_side - top))
            h = rng.randint(1, max_side)
            offset = rng.randint(0, max(0, bottom - top))
            vertices = [
                (sympy.Integer(0), sympy.Integer(0)),
                (sympy.Integer(bottom), sympy.Integer(0)),
                (sympy.Integer(offset + top), sympy.Integer(h)),
                (sympy.Integer(offset), sympy.Integer(h)),
            ]
            n_sides = 4
        elif polygon_type == "regular_polygon":
            n_sides = max(3, n_sides_in)
            r = rng.randint(1, max_side)
            vertices = []
            for k in range(n_sides):
                theta = 2 * sympy.pi * k / n_sides
                x = sympy.Integer(r) * sympy.cos(theta)
                y = sympy.Integer(r) * sympy.sin(theta)
                if force_integer_coords:
                    # 正多角形では一般に整数座標にならないので、シンボリックに残す
                    pass
                vertices.append((sympy.simplify(x), sympy.simplify(y)))

        return PolygonAtom(polygon_type=polygon_type, vertices=vertices, n_sides=n_sides)

    @property
    def side_lengths(self) -> List[sympy.Expr]:
        n = len(self.vertices)
        result: List[sympy.Expr] = []
        for i in range(n):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % n]
            d = sympy.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
            result.append(sympy.simplify(d))
        return result

    @property
    def perimeter_expr(self) -> sympy.Expr:
        return sympy.simplify(sum(self.side_lengths))

    @property
    def area_expr(self) -> sympy.Expr:
        # Shoelace 公式
        n = len(self.vertices)
        if n < 3:
            return sympy.Integer(0)
        s = sympy.Integer(0)
        for i in range(n):
            x1, y1 = self.vertices[i]
            x2, y2 = self.vertices[(i + 1) % n]
            s += x1 * y2 - x2 * y1
        return sympy.simplify(sympy.Abs(s) / 2)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "area": self.area_expr,
            "perimeter": self.perimeter_expr,
            "n_sides": sympy.Integer(len(self.vertices)),
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_side = int(custom.get("max_side_length", 10))
        polygon_type = str(custom.get("polygon_type", "triangle"))
        if polygon_type in {"square", "equilateral_triangle"}:
            return max_side
        if polygon_type in {"rectangle", "right_triangle", "isoceles_triangle"}:
            return max_side * max_side
        if polygon_type in {"parallelogram", "rhombus", "trapezoid"}:
            return max_side ** 3
        if polygon_type == "regular_polygon":
            return max_side * 5
        # triangle 一般
        return (max_side + 1) ** 6
