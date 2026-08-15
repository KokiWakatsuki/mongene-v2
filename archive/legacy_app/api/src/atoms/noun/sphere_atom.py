"""SphereAtom（§18.1）

球（体積 $\\frac{4}{3}\\pi r^3$、表面積 $4\\pi r^2$）を表す Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class SphereAtom(NounAtom):
    tags: ClassVar[List[str]] = ["space_geometry", "sphere", "pi", "geometry"]

    def __init__(self, radius: sympy.Expr | None = None) -> None:
        self.radius: sympy.Expr = sympy.Integer(1) if radius is None else radius

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "SphereAtom":
        custom = constraints.custom or {}
        max_radius: int = int(custom.get("max_radius", 10))
        integer_radius: bool = bool(custom.get("integer_radius", True))

        if integer_radius:
            r = sympy.Integer(rng.randint(1, max(1, max_radius)))
        else:
            # 半整数刻みを許容
            r = sympy.Rational(rng.randint(1, max(1, max_radius * 2)), 2)

        return SphereAtom(radius=r)

    @property
    def volume_expr(self) -> sympy.Expr:
        return sympy.Rational(4, 3) * sympy.pi * self.radius ** 3

    @property
    def surface_area_expr(self) -> sympy.Expr:
        return 4 * sympy.pi * self.radius ** 2

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "radius": self.radius,
            "volume_expr": self.volume_expr,
            "surface_area_expr": self.surface_area_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_radius = int(custom.get("max_radius", 10))
        if not custom.get("integer_radius", True):
            return max(1, max_radius * 2)
        return max(1, max_radius)
