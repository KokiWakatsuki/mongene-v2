"""PolynomialAtom（§18.1）

多項式を表す Atom。係数・次数・変数数を制約として受け取る。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class PolynomialAtom(NounAtom):
    tags: ClassVar[List[str]] = ["polynomial", "factorization"]

    def __init__(
        self,
        expression: sympy.Expr | None = None,
        variables: List[sympy.Symbol] | None = None,
    ) -> None:
        self.expression: sympy.Expr = sympy.Integer(0) if expression is None else expression
        self.variables: List[sympy.Symbol] = variables or []

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "PolynomialAtom":
        custom = constraints.custom or {}
        max_degree: int = int(custom.get("max_degree", 2))
        num_variables: int = int(custom.get("num_variables", 1))
        max_coefficient: int = int(custom.get("max_coefficient", 10))

        num_variables = max(1, min(2, num_variables))
        max_degree = max(1, max_degree)

        symbol_names = ["x", "y"][:num_variables]
        variables = [sympy.Symbol(name) for name in symbol_names]

        expr: sympy.Expr = sympy.Integer(0)
        for var in variables:
            for deg in range(max_degree, -1, -1):
                coef = rng.randint(-max_coefficient, max_coefficient)
                if deg == max_degree and coef == 0:
                    coef = rng.choice([c for c in range(-max_coefficient, max_coefficient + 1) if c != 0])
                if coef == 0:
                    continue
                expr = sympy.Add(expr, sympy.Mul(sympy.Integer(coef), var**deg))

        return PolynomialAtom(expression=sympy.expand(expr), variables=variables)

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "expression": self.expression,
            "degree": sympy.Integer(self.degree),
        }

    @property
    def degree(self) -> int:
        if self.expression == 0 or not self.variables:
            return 0
        try:
            return int(sympy.Poly(self.expression, *self.variables).total_degree())
        except sympy.PolynomialError:
            return 0

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_degree = int(custom.get("max_degree", 2))
        num_variables = int(custom.get("num_variables", 1))
        max_coefficient = int(custom.get("max_coefficient", 10))
        return (2 * max_coefficient + 1) ** (max_degree + 1) * num_variables
