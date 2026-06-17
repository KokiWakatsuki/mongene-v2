"""QuadraticFuncAtom（§18.1）

2 乗に比例 $y = ax^2$ を表す Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class QuadraticFuncAtom(NounAtom):
    tags: ClassVar[List[str]] = ["quadratic_function"]

    def __init__(self, coefficient_a: sympy.Expr | None = None) -> None:
        self.coefficient_a: sympy.Expr = (
            sympy.Integer(1) if coefficient_a is None else coefficient_a
        )

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "QuadraticFuncAtom":
        custom = constraints.custom or {}
        max_a_value: int = int(custom.get("max_a_value", 4))
        allow_negative_a: bool = bool(custom.get("allow_negative_a", True))
        is_pure_form: bool = bool(custom.get("is_pure_form", True))
        force_integer: bool = bool(custom.get("force_integer", False))

        # is_pure_form 仕様: y=ax^2 限定（本実装は常に純粋形）
        _ = is_pure_form

        lo = -max_a_value if allow_negative_a else 1
        hi = max_a_value
        if force_integer:
            a = rng.randint(lo, hi)
            while a == 0:
                a = rng.randint(lo, hi)
            coefficient_a = sympy.Integer(a)
        else:
            # 分数係数（1/2, 1/3 等）も許す
            num = rng.randint(lo, hi)
            while num == 0:
                num = rng.randint(lo, hi)
            den = rng.randint(1, max(1, max_a_value))
            coefficient_a = sympy.Rational(num, den)

        return QuadraticFuncAtom(coefficient_a=coefficient_a)

    @property
    def expression(self) -> sympy.Expr:
        x = sympy.Symbol("x")
        return self.coefficient_a * x**2

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "coefficient_a": self.coefficient_a,
            "expression": self.expression,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_a = int(custom.get("max_a_value", 4))
        sign = 2 if custom.get("allow_negative_a", True) else 1
        return max(1, max_a * sign)
