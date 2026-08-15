"""SimultaneousEqVerb

2 つの EquationAtom（diophantine_form: ax + by = c）を連立して解く Verb。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class SimultaneousEqVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = ["EquationAtom"]
    tags: ClassVar[List[str]] = ["simultaneous_equation", "linear_equation"]

    def __init__(self, allow_fraction: bool = False) -> None:
        self.allow_fraction = allow_fraction

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 2:
            return False, "EquationAtom 2 つを要求"
        for n in nouns:
            if type(n).__name__ != "EquationAtom":
                return False, f"{type(n).__name__} は SimultaneousEqVerb に渡せない"

        x, y = sympy.Symbol("x"), sympy.Symbol("y")
        s1 = nouns[0].get_symbols()
        s2 = nouns[1].get_symbols()
        e1 = s1["lhs"] - s1["rhs"]
        e2 = s2["lhs"] - s2["rhs"]

        if y not in e1.free_symbols or y not in e2.free_symbols:
            return False, "2 変数方程式でない（diophantine_form が必要）"

        try:
            sol = sympy.solve([e1, e2], [x, y])
        except Exception as exc:
            return False, f"解探索失敗: {exc}"

        if not sol or not isinstance(sol, dict):
            return False, "連立方程式に一意解がない"

        x_val = sol.get(x)
        y_val = sol.get(y)
        if x_val is None or y_val is None:
            return False, "解が求まらない"
        x_is_int = sympy.sympify(x_val).is_Integer
        y_is_int = sympy.sympify(y_val).is_Integer
        if not self.allow_fraction:
            if not x_is_int or not y_is_int:
                return False, "整数解でない"
            if abs(int(x_val)) > 20 or abs(int(y_val)) > 20:
                return False, f"解が大きすぎる（中学範囲外）: x={x_val}, y={y_val}"
        else:
            # 分数解許可：係数が極端に大きい場合のみ除外
            def _magnitude(v) -> float:
                return float(abs(v))
            if _magnitude(x_val) > 50 or _magnitude(y_val) > 50:
                return False, f"解が大きすぎる: x={x_val}, y={y_val}"

        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        x, y = sympy.Symbol("x"), sympy.Symbol("y")
        s1 = nouns[0].get_symbols()
        s2 = nouns[1].get_symbols()
        e1 = s1["lhs"] - s1["rhs"]
        e2 = s2["lhs"] - s2["rhs"]

        sol = sympy.solve([e1, e2], [x, y])
        x_val = sol[x]
        y_val = sol[y]

        return LogicStep(
            operation_name="solve_simultaneous",
            operands=[str(s1["lhs"] - s1["rhs"]), str(s2["lhs"] - s2["rhs"])],
            sympy_expr=sympy.Tuple(x_val, y_val),
            narration_hint=f"連立方程式を解く: x={x_val}, y={y_val}",
        )
