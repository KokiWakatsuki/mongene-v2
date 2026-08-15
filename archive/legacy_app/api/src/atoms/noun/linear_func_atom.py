"""LinearFuncAtom（§18.1）

一次関数 $y = ax + b$（force_proportion=True で $y=ax$）を表す Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class LinearFuncAtom(NounAtom):
    tags: ClassVar[List[str]] = ["linear_function", "proportion"]

    def __init__(
        self,
        slope: sympy.Expr | None = None,
        intercept: sympy.Expr | None = None,
    ) -> None:
        self.slope: sympy.Expr = sympy.Integer(1) if slope is None else slope
        self.intercept: sympy.Expr = sympy.Integer(0) if intercept is None else intercept

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "LinearFuncAtom":
        custom = constraints.custom or {}
        force_proportion: bool = bool(custom.get("force_proportion", False))
        max_slope: int = int(custom.get("max_slope", 5))
        force_integer_slope: bool = bool(custom.get("force_integer_slope", True))
        allow_negative: bool = bool(custom.get("allow_negative", True))
        max_intercept: int = int(custom.get("max_intercept", max_slope))

        lo = -max_slope if allow_negative else 1
        hi = max_slope
        if force_integer_slope:
            a = rng.randint(lo, hi)
            while a == 0:
                a = rng.randint(lo, hi)
            slope = sympy.Integer(a)
        else:
            num = rng.randint(lo, hi)
            while num == 0:
                num = rng.randint(lo, hi)
            den = rng.randint(1, max(1, max_slope))
            slope = sympy.Rational(num, den)

        if force_proportion:
            intercept = sympy.Integer(0)
        else:
            b_lo = -max_intercept if allow_negative else 0
            intercept = sympy.Integer(rng.randint(b_lo, max_intercept))

        return LinearFuncAtom(slope=slope, intercept=intercept)

    @property
    def expression(self) -> sympy.Expr:
        x = sympy.Symbol("x")
        return self.slope * x + self.intercept

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "slope": self.slope,
            "intercept": self.intercept,
            "expression": self.expression,
        }

    def y_intercept(self) -> sympy.Expr:
        return self.intercept

    def x_intercept(self) -> sympy.Expr | None:
        if sympy.simplify(self.slope) == 0:
            return None
        return sympy.Rational(-self.intercept, self.slope)

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_slope = int(custom.get("max_slope", 5))
        max_intercept = int(custom.get("max_intercept", max_slope))
        sign = 2 if custom.get("allow_negative", True) else 1
        slope_n = max_slope * sign
        intercept_n = 1 if custom.get("force_proportion", False) else (max_intercept * sign + 1)
        return max(1, slope_n) * max(1, intercept_n)
