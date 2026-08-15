"""PrismAtom（§18.1）

柱体（直方体・立方体・三角柱・n 角柱）の体積・表面積を保持する Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class PrismAtom(NounAtom):
    tags: ClassVar[List[str]] = ["space_geometry", "prism", "geometry"]

    def __init__(
        self,
        width: sympy.Expr | None = None,
        depth: sympy.Expr | None = None,
        height: sympy.Expr | None = None,
        base_shape_type: str = "square",
        num_sides: int = 4,
    ) -> None:
        self.width: sympy.Expr = sympy.Integer(1) if width is None else width
        self.depth: sympy.Expr = sympy.Integer(1) if depth is None else depth
        self.height: sympy.Expr = sympy.Integer(1) if height is None else height
        self.base_shape_type: str = base_shape_type
        self.num_sides: int = num_sides

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "PrismAtom":
        custom = constraints.custom or {}
        is_cube: bool = bool(custom.get("is_cube", False))
        base_shape_type: str = str(custom.get("base_shape_type", "square"))
        max_dim: int = int(custom.get("max_dim", 10))
        min_dim: int = max(2, int(custom.get("min_dim", 2)))
        max_height: int = int(custom.get("max_height", max_dim))
        num_sides: int = int(custom.get("num_sides", 6 if base_shape_type == "regular_polygon" else 4))

        if base_shape_type not in ("triangle", "square", "regular_polygon"):
            base_shape_type = "square"

        if is_cube:
            s = sympy.Integer(rng.randint(2, max(2, max_dim)))
            return PrismAtom(
                width=s, depth=s, height=s,
                base_shape_type="square", num_sides=4,
            )

        if base_shape_type == "triangle":
            width = sympy.Integer(rng.randint(min_dim, max_dim))
            depth = sympy.Integer(rng.randint(min_dim, max_dim))
            height = sympy.Integer(rng.randint(min_dim, max_height))
            return PrismAtom(width=width, depth=depth, height=height, base_shape_type="triangle", num_sides=3)

        if base_shape_type == "regular_polygon":
            side = sympy.Integer(rng.randint(min_dim, max_dim))
            height = sympy.Integer(rng.randint(min_dim, max_height))
            return PrismAtom(width=side, depth=side, height=height, base_shape_type="regular_polygon", num_sides=num_sides)

        # 直方体（min_dim でフロア保証）
        width = sympy.Integer(rng.randint(min_dim, max_dim))
        depth = sympy.Integer(rng.randint(min_dim, max_dim))
        height = sympy.Integer(rng.randint(min_dim, max_height))
        return PrismAtom(width=width, depth=depth, height=height, base_shape_type="square", num_sides=4)

    @property
    def is_cube(self) -> bool:
        return (
            self.base_shape_type == "square"
            and self.width == self.depth == self.height
        )

    @property
    def base_area_expr(self) -> sympy.Expr:
        if self.base_shape_type == "triangle":
            return sympy.Rational(1, 2) * self.width * self.depth
        if self.base_shape_type == "regular_polygon":
            n = sympy.Integer(self.num_sides)
            s = self.width
            return n * s ** 2 / (4 * sympy.tan(sympy.pi / n))
        # square / rectangle
        return self.width * self.depth

    @property
    def base_perimeter_expr(self) -> sympy.Expr:
        if self.base_shape_type == "triangle":
            # 直角三角形を仮定（width, depth が直角辺）
            return self.width + self.depth + sympy.sqrt(self.width ** 2 + self.depth ** 2)
        if self.base_shape_type == "regular_polygon":
            return sympy.Integer(self.num_sides) * self.width
        return 2 * (self.width + self.depth)

    @property
    def volume_expr(self) -> sympy.Expr:
        return sympy.simplify(self.base_area_expr * self.height)

    @property
    def surface_area_expr(self) -> sympy.Expr:
        return sympy.simplify(2 * self.base_area_expr + self.base_perimeter_expr * self.height)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "volume_expr": self.volume_expr,
            "surface_area_expr": self.surface_area_expr,
            "base_area_expr": self.base_area_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_dim = int(custom.get("max_dim", 10))
        if custom.get("is_cube", False):
            return max(1, max_dim - 1)
        n = max(1, max_dim - 1)
        return n ** 3
