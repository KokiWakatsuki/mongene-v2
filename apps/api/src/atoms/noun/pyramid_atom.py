"""PyramidAtom（§18.1）

角錐（三角錐・四角錐・正 n 角錐）の体積・表面積を保持する Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class PyramidAtom(NounAtom):
    tags: ClassVar[List[str]] = ["space_geometry", "pyramid", "geometry"]

    def __init__(
        self,
        base_side: sympy.Expr | None = None,
        height: sympy.Expr | None = None,
        base_shape: str = "square",
        num_sides: int = 4,
        is_regular_pyramid: bool = True,
        hide_height: bool = False,
    ) -> None:
        self.base_side: sympy.Expr = sympy.Integer(1) if base_side is None else base_side
        self.height: sympy.Expr = sympy.Integer(1) if height is None else height
        self.base_shape: str = base_shape
        self.num_sides: int = num_sides
        self.is_regular_pyramid: bool = is_regular_pyramid
        self.hide_height: bool = hide_height

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "PyramidAtom":
        custom = constraints.custom or {}
        base_shape: str = str(custom.get("base_shape", "square"))
        if base_shape not in ("triangle", "square", "regular_polygon"):
            base_shape = "square"
        is_regular_pyramid: bool = bool(custom.get("is_regular_pyramid", True))
        hide_height: bool = bool(custom.get("hide_height", False))
        max_base_side: int = int(custom.get("max_base_side", 10))
        max_height: int = int(custom.get("max_height", 12))
        if base_shape == "regular_polygon":
            num_sides: int = int(custom.get("num_sides", 6))
        elif base_shape == "triangle":
            num_sides = 3
        else:
            num_sides = 4

        base_side = sympy.Integer(rng.randint(2, max(2, max_base_side)))
        height = sympy.Integer(rng.randint(2, max(2, max_height)))

        return PyramidAtom(
            base_side=base_side,
            height=height,
            base_shape=base_shape,
            num_sides=num_sides,
            is_regular_pyramid=is_regular_pyramid,
            hide_height=hide_height,
        )

    @property
    def base_area_expr(self) -> sympy.Expr:
        s = self.base_side
        if self.base_shape == "triangle":
            # 正三角形を仮定
            return sympy.sqrt(3) / 4 * s ** 2
        if self.base_shape == "regular_polygon":
            n = sympy.Integer(self.num_sides)
            return n * s ** 2 / (4 * sympy.tan(sympy.pi / n))
        # square
        return s ** 2

    @property
    def slant_edge(self) -> sympy.Expr:
        # 正四角錐などで中心から底辺中点までの距離 d を仮定し
        # slant_edge = sqrt(h^2 + (s/2)^2 + ...) を簡易計算（正四角錐：底面中心から頂点までの距離）
        s = self.base_side
        h = self.height
        if self.base_shape == "square":
            # 底面中心から頂点までの距離 = s*sqrt(2)/2
            return sympy.sqrt(h ** 2 + (s * sympy.sqrt(2) / 2) ** 2)
        if self.base_shape == "triangle":
            # 正三角形底面：外接円半径 = s/sqrt(3)
            return sympy.sqrt(h ** 2 + (s / sympy.sqrt(3)) ** 2)
        # regular_polygon: 外接円半径 = s / (2 sin(pi/n))
        n = sympy.Integer(self.num_sides)
        R = s / (2 * sympy.sin(sympy.pi / n))
        return sympy.sqrt(h ** 2 + R ** 2)

    @property
    def slant_height(self) -> sympy.Expr:
        """側面三角形の斜辺の高さ（apothem を使った母線）"""
        s = self.base_side
        h = self.height
        if self.base_shape == "square":
            apothem = s / 2
        elif self.base_shape == "triangle":
            apothem = s / (2 * sympy.sqrt(3))
        else:
            n = sympy.Integer(self.num_sides)
            apothem = s / (2 * sympy.tan(sympy.pi / n))
        return sympy.sqrt(h ** 2 + apothem ** 2)

    @property
    def lateral_area_expr(self) -> sympy.Expr:
        # 正多角錐：底面周 × 母線斜辺の高さ / 2
        if self.base_shape == "triangle":
            perimeter = 3 * self.base_side
        elif self.base_shape == "square":
            perimeter = 4 * self.base_side
        else:
            perimeter = sympy.Integer(self.num_sides) * self.base_side
        return sympy.Rational(1, 2) * perimeter * self.slant_height

    @property
    def surface_area_expr(self) -> sympy.Expr:
        return sympy.simplify(self.base_area_expr + self.lateral_area_expr)

    @property
    def volume_expr(self) -> sympy.Expr:
        return sympy.simplify(sympy.Rational(1, 3) * self.base_area_expr * self.height)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "base_side": self.base_side,
            "height": self.height,
            "slant_edge": self.slant_edge,
            "volume_expr": self.volume_expr,
            "surface_area_expr": self.surface_area_expr,
            "base_area_expr": self.base_area_expr,
            "lateral_area_expr": self.lateral_area_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_base_side = int(custom.get("max_base_side", 10))
        max_height = int(custom.get("max_height", 12))
        return max(1, max_base_side - 1) * max(1, max_height - 1)
