"""SquareRootAtom（§18.1）

根号を含む数 (sqrt(a)) を表す Atom。係数と被開平数を持つ。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class SquareRootAtom(NounAtom):
    tags: ClassVar[List[str]] = ["square_root"]

    def __init__(
        self,
        coefficient: sympy.Expr | None = None,
        base: sympy.Expr | None = None,
        expression: sympy.Expr | None = None,
    ) -> None:
        self.coefficient: sympy.Expr = sympy.Integer(1) if coefficient is None else coefficient
        self.base: sympy.Expr = sympy.Integer(1) if base is None else base
        if expression is None:
            self.expression: sympy.Expr = self.coefficient * sympy.sqrt(self.base)
        else:
            self.expression = expression

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "SquareRootAtom":
        custom = constraints.custom or {}
        allow_simplification: bool = bool(custom.get("allow_simplification", True))
        force_denominator_root: bool = bool(custom.get("force_denominator_root", False))
        max_base: int = int(custom.get("max_base", 30))
        max_coefficient: int = int(custom.get("max_coefficient", 5))

        base = rng.randint(2, max(2, max_base))
        coefficient = rng.randint(1, max(1, max_coefficient))

        if allow_simplification:
            expr = sympy.sqrt(sympy.Integer(base)) * sympy.Integer(coefficient)
            expr = sympy.sqrtdenest(sympy.simplify(expr))
        else:
            expr = sympy.Mul(sympy.Integer(coefficient), sympy.sqrt(sympy.Integer(base)), evaluate=False)

        if force_denominator_root:
            expr = sympy.Integer(1) / sympy.sqrt(sympy.Integer(base))

        return SquareRootAtom(
            coefficient=sympy.Integer(coefficient),
            base=sympy.Integer(base),
            expression=expr,
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "expression": self.expression,
            "coefficient": self.coefficient,
            "base": self.base,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_base = int(custom.get("max_base", 30))
        max_coefficient = int(custom.get("max_coefficient", 5))
        return max_base * max_coefficient
