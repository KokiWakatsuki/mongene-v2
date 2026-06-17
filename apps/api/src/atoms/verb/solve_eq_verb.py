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
            if not s.is_real:
                return False, "解が実数でない"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        eq = nouns[0]
        symbols = eq.get_symbols()
        if type(eq).__name__ == "ProportionAtom":
            lhs_ratio = symbols.get("lhs_ratio_a"), symbols.get("lhs_ratio_b")
            rhs_ratio = symbols.get("rhs_ratio_a"), symbols.get("rhs_ratio_b")
            if all(v is not None for v in lhs_ratio + rhs_ratio):
                # a:b = c:d → a*d = b*c
                expr = sympy.simplify(lhs_ratio[0] * rhs_ratio[1] - lhs_ratio[1] * rhs_ratio[0])
            else:
                expr = sympy.Integer(0)
            return LogicStep(
                operation_name="solve_proportion",
                operands=[],
                sympy_expr=expr,
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
