"""FindDivisorsVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Mode = Literal["divisors", "sigma", "gcd", "lcm"]


@register_verb
class FindDivisorsVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["NumberAtom"]
    tags: ClassVar[List[str]] = ["divisors", "number_theory"]

    def __init__(self, mode: Mode = "divisors") -> None:
        self.mode: Mode = mode

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "1 つ以上の NumberAtom が必要"
        for n in nouns:
            if type(n).__name__ != "NumberAtom":
                return False, f"{type(n).__name__} は不可"
            v = n.get_symbols()["value"]
            if not v.is_Integer or int(v) <= 0:
                return False, "正の自然数のみ受理"
        if self.mode in ("gcd", "lcm") and len(nouns) < 2:
            return False, f"{self.mode} には 2 つ以上必要"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        vals = [int(n.get_symbols()["value"]) for n in nouns]
        if self.mode == "divisors":
            divs = sympy.divisors(vals[0])
            result = sympy.FiniteSet(*divs)
            narration = f"{vals[0]} の約数を列挙"
        elif self.mode == "sigma":
            result = sympy.Integer(sympy.divisor_sigma(vals[0], 1))
            narration = f"{vals[0]} の約数の総和"
        elif self.mode == "gcd":
            result = sympy.Integer(sympy.gcd(*vals))
            narration = "最大公約数 (GCD) を求める"
        else:  # lcm
            result = sympy.Integer(sympy.lcm(*vals))
            narration = "最小公倍数 (LCM) を求める"
        return LogicStep(
            operation_name=f"find_{self.mode}",
            operands=[str(v) for v in vals],
            sympy_expr=result,
            narration_hint=narration,
        )
