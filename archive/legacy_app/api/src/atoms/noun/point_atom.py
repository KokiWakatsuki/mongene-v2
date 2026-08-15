"""PointAtom（§18.1）

座標平面上の点 $(x, y)$ を表す Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class PointAtom(NounAtom):
    tags: ClassVar[List[str]] = ["coordinate"]

    def __init__(
        self,
        x: sympy.Expr | None = None,
        y: sympy.Expr | None = None,
        label: str = "A",
    ) -> None:
        self.x: sympy.Expr = sympy.Integer(0) if x is None else x
        self.y: sympy.Expr = sympy.Integer(0) if y is None else y
        self.label: str = label

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "PointAtom":
        custom = constraints.custom or {}
        range_x: Tuple[int, int] = tuple(custom.get("range_x", (-10, 10)))
        range_y: Tuple[int, int] = tuple(custom.get("range_y", (-10, 10)))
        integer_only: bool = bool(custom.get("integer_only", True))
        label: str = str(custom.get("label", "A"))

        if integer_only:
            x_val = sympy.Integer(rng.randint(range_x[0], range_x[1]))
            y_val = sympy.Integer(rng.randint(range_y[0], range_y[1]))
        else:
            # 半整数刻みの簡易対応
            x_val = sympy.Rational(rng.randint(range_x[0] * 2, range_x[1] * 2), 2)
            y_val = sympy.Rational(rng.randint(range_y[0] * 2, range_y[1] * 2), 2)

        return PointAtom(x=x_val, y=y_val, label=label)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "x": self.x,
            "y": self.y,
            "label": sympy.Symbol(self.label),
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        range_x = custom.get("range_x", (-10, 10))
        range_y = custom.get("range_y", (-10, 10))
        nx = max(1, range_x[1] - range_x[0] + 1)
        ny = max(1, range_y[1] - range_y[0] + 1)
        return nx * ny
