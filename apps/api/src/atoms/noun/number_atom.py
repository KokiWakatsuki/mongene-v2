"""NumberAtom（§18.1）

中1 の四則計算で使う整数・分数・小数の Atom。Phase 1 ではこの 1 個だけで Hello World を回す。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class NumberAtom(NounAtom):
    tags: ClassVar[List[str]] = ["number", "fraction", "integer"]

    def __init__(self, value: sympy.Expr | None = None) -> None:
        self.value: sympy.Expr = sympy.Integer(0) if value is None else value

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "NumberAtom":
        custom = constraints.custom or {}
        allow_negative: bool = bool(custom.get("allow_negative", True))
        force_fraction: bool = bool(custom.get("force_fraction", False))
        max_value: int = int(custom.get("max_value", 30))
        rng_lo, rng_hi = custom.get("range_constraint", (None, None))

        if rng_lo is None:
            rng_lo = -max_value if allow_negative else 0
        if rng_hi is None:
            rng_hi = max_value

        if force_fraction:
            denominator = rng.randint(2, max(2, min(10, max_value)))
            numerator = rng.randint(rng_lo, rng_hi)
            if numerator == 0:
                numerator = 1
            value = sympy.Rational(numerator, denominator)
        else:
            value = sympy.Integer(rng.randint(rng_lo, rng_hi))

        return NumberAtom(value=value)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "value": self.value,
            "prime_factors": sympy.Integer(0),
        }

    @property
    def prime_factors(self) -> List[int]:
        if not self.value.is_Integer:
            return []
        n = abs(int(self.value))
        if n <= 1:
            return []
        return list(sympy.factorint(n).keys())

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_value = int(custom.get("max_value", 30))
        sign = 2 if custom.get("allow_negative", True) else 1
        if custom.get("force_fraction", False):
            return max_value * sign * 9  # denominator 候補
        return max_value * sign + 1
