"""EquationAtom（§18.1）

等式 lhs = rhs を表す Atom。次数や diophantine 形によりタグを動的に変える。
"""
from __future__ import annotations

import random
from typing import ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class EquationAtom(NounAtom):
    tags: ClassVar[List[str]] = ["linear_equation", "quadratic_equation"]

    def __init__(
        self,
        lhs: sympy.Expr | None = None,
        rhs: sympy.Expr | None = None,
        variable: sympy.Symbol | None = None,
        degree: int = 1,
        extra_tags: List[str] | None = None,
    ) -> None:
        self.lhs: sympy.Expr = sympy.Integer(0) if lhs is None else lhs
        self.rhs: sympy.Expr = sympy.Integer(0) if rhs is None else rhs
        self.variable: sympy.Symbol = sympy.Symbol("x") if variable is None else variable
        self._degree: int = degree
        # degree に応じてインスタンスの tags を動的に決定
        # （ClassVar の tags は最大集合、インスタンスでは現在の degree に絞る）
        if degree >= 2:
            base_tags = ["linear_equation", "quadratic_equation"]
        else:
            base_tags = ["linear_equation"]
        merged = list(base_tags)
        if extra_tags:
            for t in extra_tags:
                if t not in merged:
                    merged.append(t)
        self.tags = merged

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "EquationAtom":
        custom = constraints.custom or {}
        is_integer_solution: bool = bool(custom.get("is_integer_solution", True))
        diophantine_form: bool = bool(custom.get("diophantine_form", False))
        max_coefficient: int = int(custom.get("max_coefficient", 10))
        degree: int = int(custom.get("degree", 1))

        degree = max(1, min(2, degree))
        x = sympy.Symbol("x")
        extra_tags: List[str] = []

        if diophantine_form:
            y = sympy.Symbol("y")
            a = rng.randint(1, max_coefficient)
            b = rng.randint(1, max_coefficient)
            x0 = rng.randint(-max_coefficient, max_coefficient)
            y0 = rng.randint(-max_coefficient, max_coefficient)
            c = a * x0 + b * y0
            lhs = sympy.Add(sympy.Mul(sympy.Integer(a), x), sympy.Mul(sympy.Integer(b), y))
            rhs = sympy.Integer(c)
            extra_tags.append("diophantine")
            variable = x
            eq_degree = 1
        elif degree == 2:
            root1 = rng.randint(-max_coefficient, max_coefficient)
            root2 = rng.randint(-max_coefficient, max_coefficient)
            if is_integer_solution:
                lhs = sympy.expand((x - root1) * (x - root2))
            else:
                a = rng.randint(1, max_coefficient)
                b = rng.randint(-max_coefficient, max_coefficient)
                c = rng.randint(-max_coefficient, max_coefficient)
                lhs = sympy.Add(sympy.Mul(sympy.Integer(a), x**2), sympy.Mul(sympy.Integer(b), x), sympy.Integer(c))
            rhs = sympy.Integer(0)
            variable = x
            eq_degree = 2
        else:
            a = rng.randint(1, max_coefficient)
            sol = rng.randint(-max_coefficient, max_coefficient)
            b = rng.randint(-max_coefficient, max_coefficient)
            lhs = sympy.Add(sympy.Mul(sympy.Integer(a), x), sympy.Integer(b))
            rhs = sympy.Integer(a * sol + b)
            variable = x
            eq_degree = 1

        return EquationAtom(
            lhs=lhs,
            rhs=rhs,
            variable=variable,
            degree=eq_degree,
            extra_tags=extra_tags,
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "lhs": self.lhs,
            "rhs": self.rhs,
            "degree": sympy.Integer(self._degree),
        }

    @property
    def degree(self) -> int:
        return self._degree

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        max_coefficient = int(custom.get("max_coefficient", 10))
        degree = int(custom.get("degree", 1))
        if custom.get("diophantine_form", False):
            return max_coefficient ** 4
        if degree == 2:
            return (2 * max_coefficient + 1) ** 2
        return (2 * max_coefficient + 1) * max_coefficient
