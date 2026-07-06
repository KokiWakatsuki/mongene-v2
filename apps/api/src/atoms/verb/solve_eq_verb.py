"""SolveEqVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class SolveEqVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["EquationAtom", "ProportionAtom"]
    tags: ClassVar[List[str]] = ["solve_equation"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "SolveEqVerb は単一の方程式を要求"
        eq = nouns[0]
        if type(eq).__name__ not in self.accepted_noun_types:
            return False, f"{type(eq).__name__} は SolveEqVerb に渡せない"

        symbols = eq.get_symbols()
        if type(eq).__name__ == "ProportionAtom":
            return True, None

        lhs = symbols.get("lhs")
        rhs = symbols.get("rhs")
        var = symbols.get("variable") or getattr(eq, "variable", None)
        if lhs is None or rhs is None or var is None:
            return False, "EquationAtom に lhs/rhs/variable が無い"
        try:
            sols = sympy.solve(lhs - rhs, var)
        except Exception as e:
            return False, f"解探索失敗: {e}"
        if not sols:
            return False, "解が存在しない"
        for s in sols:
            if s.free_symbols:
                # パラメータを含む解（ディオファントス形 ax+by=c → x=(c-by)/a）は許容
                continue
            if not s.is_real:
                return False, "解が実数でない"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        eq = nouns[0]
        symbols = eq.get_symbols()
        if type(eq).__name__ == "ProportionAtom":
            # a:b = c:x → x = b*c/a（ProportionAtom は lhs_a, lhs_b, rhs_c を公開）
            a = symbols.get("lhs_a", sympy.Integer(1))
            b = symbols.get("lhs_b", sympy.Integer(1))
            c = symbols.get("rhs_c", sympy.Integer(1))
            x_val = sympy.Rational(b * c, a) if a != 0 else sympy.Integer(0)
            return LogicStep(
                operation_name="solve_proportion",
                operands=[str(a), str(b), str(c)],
                sympy_expr=sympy.simplify(x_val),
                narration_hint="比例式を解く",
            )

        lhs = symbols["lhs"]
        rhs = symbols["rhs"]
        var = symbols.get("variable") or getattr(eq, "variable", None) or sympy.Symbol("x")
        sols = sympy.solve(lhs - rhs, var)
        result = sols[0] if len(sols) == 1 else sympy.FiniteSet(*sols)
        return LogicStep(
            operation_name="solve_equation",
            operands=[str(lhs), str(rhs)],
            sympy_expr=sympy.sympify(result),
            narration_hint="方程式を解く",
        )
