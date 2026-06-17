"""CircleAtom（§17.1, §18.1）

円・おうぎ形を表す Noun Atom。半径と中心角から面積・周長・弧長を導出する。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_DEFAULT_CENTRAL_ANGLE_CHOICES: List[int] = [30, 45, 60, 90, 120, 180, 270, 360]


@register_noun
class CircleAtom(NounAtom):
    tags: ClassVar[List[str]] = ["plane_geometry", "circle", "pi"]

    def __init__(
        self,
        radius: sympy.Expr | None = None,
        central_angle: sympy.Expr | None = None,
        is_sector: bool = False,
    ) -> None:
        self.radius: sympy.Expr = sympy.Integer(1) if radius is None else radius
        self.central_angle: sympy.Expr = (
            sympy.Integer(360) if central_angle is None else central_angle
        )
        self.is_sector: bool = is_sector

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "CircleAtom":
        custom = constraints.custom or {}
        is_sector: bool = bool(custom.get("is_sector", False))
        max_radius: int = int(custom.get("max_radius", 10))
        if max_radius < 1:
            max_radius = 1
        choices_raw = custom.get("central_angle_choices", _DEFAULT_CENTRAL_ANGLE_CHOICES)
        choices: List[int] = [int(c) for c in choices_raw] or _DEFAULT_CENTRAL_ANGLE_CHOICES

        radius = sympy.Integer(rng.randint(1, max_radius))
        if is_sector:
            # おうぎ形：360 度未満を優先
            sector_choices = [c for c in choices if 0 < c < 360]
            if not sector_choices:
                sector_choices = choices
            angle = sympy.Integer(rng.choice(sector_choices))
        else:
            angle = sympy.Integer(360)

        return CircleAtom(radius=radius, central_angle=angle, is_sector=is_sector)

    @property
    def area_expr(self) -> sympy.Expr:
        full_area = sympy.pi * self.radius ** 2
        if self.is_sector:
            return sympy.simplify(full_area * self.central_angle / 360)
        return sympy.simplify(full_area)

    @property
    def circumference_expr(self) -> sympy.Expr:
        return sympy.simplify(2 * sympy.pi * self.radius)

    @property
    def arc_length_expr(self) -> sympy.Expr:
        return sympy.simplify(self.circumference_expr * self.central_angle / 360)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "radius": self.radius,
            "central_angle": self.central_angle,
            "area": self.area_expr,
            "circumference": self.circumference_expr,
            "arc_length": self.arc_length_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_radius = int(custom.get("max_radius", 10))
        choices = custom.get("central_angle_choices", _DEFAULT_CENTRAL_ANGLE_CHOICES)
        if bool(custom.get("is_sector", False)):
            return max_radius * max(1, len([c for c in choices if 0 < int(c) < 360]))
        return max_radius
