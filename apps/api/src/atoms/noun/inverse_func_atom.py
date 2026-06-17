"""InverseFuncAtom（§18.1）

反比例 $y = a/x$ を表す Noun Atom。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class InverseFuncAtom(NounAtom):
    tags: ClassVar[List[str]] = ["inverse_proportion"]

    def __init__(self, constant: sympy.Expr | None = None) -> None:
        self.constant: sympy.Expr = sympy.Integer(1) if constant is None else constant

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "InverseFuncAtom":
        custom = constraints.custom or {}
        max_constant: int = int(custom.get("max_constant", 12))
        integer_only: bool = bool(custom.get("integer_only", True))
        allow_negative: bool = bool(custom.get("allow_negative", True))

        lo = -max_constant if allow_negative else 1
        hi = max_constant
        if integer_only:
            a = rng.randint(lo, hi)
            while a == 0:
                a = rng.randint(lo, hi)
            constant = sympy.Integer(a)
        else:
            num = rng.randint(lo, hi)
            while num == 0:
                num = rng.randint(lo, hi)
            den = rng.randint(1, max(1, max_constant))
            constant = sympy.Rational(num, den)

        return InverseFuncAtom(constant=constant)

    @property
    def expression(self) -> sympy.Expr:
        x = sympy.Symbol("x")
        return self.constant / x

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "constant": self.constant,
            "expression": self.expression,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_constant = int(custom.get("max_constant", 12))
        sign = 2 if custom.get("allow_negative", True) else 1
        return max(1, max_constant * sign)
