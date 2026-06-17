"""CalculateArithmeticVerb（§17.2, §18.2）

数値・文字式の四則演算を SymPy で実行する Verb。
Phase 1 の垂直スライスでは「2 つの NumberAtom を足し合わせて答えを出す」用途。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Operation = Literal["+", "-", "*", "/"]


@register_verb
class CalculateArithmeticVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "NumberAtom",
        "PolynomialAtom",
        "SquareRootAtom",
    ]
    tags: ClassVar[List[str]] = ["arithmetic"]

    def __init__(self, operation: Optional[Operation] = None) -> None:
        self.operation: Optional[Operation] = operation

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) < 2:
            return False, "CalculateArithmeticVerb は 2 つ以上の Noun を必要とする"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は CalculateArithmeticVerb に渡せない"
        if self.operation == "/":
            for n in nouns[1:]:
                v = n.get_symbols().get("value")
                if v is not None and sympy.simplify(v) == 0:
                    return False, "ゼロ除算"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        op: Operation = self.operation or rng.choice(["+", "-", "*"])

        values = [n.get_symbols()["value"] for n in nouns]
        result: sympy.Expr = values[0]
        for v in values[1:]:
            if op == "+":
                result = result + v
            elif op == "-":
                result = result - v
            elif op == "*":
                result = result * v
            elif op == "/":
                result = result / v

        simplified = sympy.simplify(result)

        narration = {
            "+": "和を計算する",
            "-": "差を計算する",
            "*": "積を計算する",
            "/": "商を計算する",
        }[op]

        return LogicStep(
            operation_name=f"arithmetic_{op}",
            operands=[str(v) for v in values],
            sympy_expr=simplified,
            narration_hint=narration,
        )
