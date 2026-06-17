"""ProportionAtom（§18.1）

比例式 a:b = c:d を表す Atom。整数解条件に対応する。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class ProportionAtom(NounAtom):
    tags: ClassVar[List[str]] = ["proportion_equation"]

    def __init__(
        self,
        lhs_ratio: Tuple[sympy.Expr, sympy.Expr] | None = None,
        rhs_ratio: Tuple[sympy.Expr, sympy.Expr] | None = None,
    ) -> None:
        self.lhs_ratio: Tuple[sympy.Expr, sympy.Expr] = (
            (sympy.Integer(1), sympy.Integer(1)) if lhs_ratio is None else lhs_ratio
        )
        self.rhs_ratio: Tuple[sympy.Expr, sympy.Expr] = (
            (sympy.Integer(1), sympy.Integer(1)) if rhs_ratio is None else rhs_ratio
        )

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "ProportionAtom":
        custom = constraints.custom or {}
        is_integer_solution: bool = bool(custom.get("is_integer_solution", True))
        max_ratio_value: int = int(custom.get("max_ratio_value", 10))

        a = rng.randint(1, max_ratio_value)
        b = rng.randint(1, max_ratio_value)

        if is_integer_solution:
            k = rng.randint(2, max(2, max_ratio_value))
            c = a * k
            d = b * k
        else:
            c = rng.randint(1, max_ratio_value)
            d = rng.randint(1, max_ratio_value)

        return ProportionAtom(
            lhs_ratio=(sympy.Integer(a), sympy.Integer(b)),
            rhs_ratio=(sympy.Integer(c), sympy.Integer(d)),
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        a, b = self.lhs_ratio
        c, d = self.rhs_ratio
        return {
            "lhs_a": a,
            "lhs_b": b,
            "rhs_c": c,
            "rhs_d": d,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_ratio_value = int(custom.get("max_ratio_value", 10))
        return max_ratio_value ** 4
