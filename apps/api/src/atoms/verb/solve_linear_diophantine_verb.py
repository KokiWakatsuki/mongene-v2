"""SolveLinearDiophantineVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class SolveLinearDiophantineVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["EquationAtom"]
    tags: ClassVar[List[str]] = ["diophantine", "integer_solutions"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "1 つの不定方程式が必要"
        eq = nouns[0]
        if type(eq).__name__ != "EquationAtom":
            return False, "EquationAtom のみ受理"
        a, b, c = self._extract_coeffs(eq)
        if a is None or b is None:
            return False, "ax+by=c の形が検出できない"
        if a == 0 and b == 0:
            return False, "係数が両方 0"
        g = sympy.gcd(a, b)
        if c % g != 0:
            return False, f"gcd({a},{b})={g} が c={c} を割らない"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        eq = nouns[0]
        a, b, c = self._extract_coeffs(eq)
        t = sympy.Symbol("t", integer=True)
        x0, y0 = self._particular_solution(int(a), int(b), int(c))
        x_expr = sympy.Integer(x0) + sympy.Integer(b) * t
        y_expr = sympy.Integer(y0) - sympy.Integer(a) * t
        return LogicStep(
            operation_name="diophantine_general_solution",
            operands=[str(a), str(b), str(c)],
            sympy_expr=sympy.Tuple(x_expr, y_expr),
            narration_hint=f"{a}x+{b}y={c} の整数解一般形を求める",
        )

    def _extract_coeffs(self, eq: NounAtom):
        symbols = eq.get_symbols()
        lhs = symbols.get("lhs")
        rhs = symbols.get("rhs")
        if lhs is None or rhs is None:
            return None, None, None
        expr = sympy.expand(lhs - rhs)
        x = sympy.Symbol("x")
        y = sympy.Symbol("y")
        try:
            poly = sympy.Poly(expr, x, y)
            a = poly.coeff_monomial(x)
            b = poly.coeff_monomial(y)
            c = -poly.coeff_monomial(1)
            return int(a), int(b), int(c)
        except Exception:
            return None, None, None

    def _particular_solution(self, a: int, b: int, c: int):
        g, x1, y1 = self._extended_gcd(a, b)
        k = c // g
        return x1 * k, y1 * k

    def _extended_gcd(self, a: int, b: int):
        if b == 0:
            return a, 1, 0
        g, x1, y1 = self._extended_gcd(b, a % b)
        return g, y1, x1 - (a // b) * y1
