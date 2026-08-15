"""FactorizeVerb

2 つの 1 次式 PolynomialAtom の積を展開した式を問題文に、
因数分解形を答えにする Verb。

問題: $(x+a)(x+b)$ を展開すると $x^2 + (a+b)x + ab$
答え: 因数分解して $(x+a)(x+b)$ に戻す
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class FactorizeVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = ["PolynomialAtom"]
    tags: ClassVar[List[str]] = ["factorize"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 2:
            return False, "PolynomialAtom 2 つが必要"
        for n in nouns:
            if type(n).__name__ != "PolynomialAtom":
                return False, f"{type(n).__name__} は FactorizeVerb に渡せない"
        syms0 = nouns[0].get_symbols()
        syms1 = nouns[1].get_symbols()
        e0 = syms0.get("expression")
        e1 = syms1.get("expression")
        if e0 is None or e1 is None:
            return False, "expression が取得できない"
        # 定数（次数 0）同士だと展開形が2次にならない → 問題として不適
        deg0 = int(sympy.degree(e0)) if e0.free_symbols else 0
        deg1 = int(sympy.degree(e1)) if e1.free_symbols else 0
        if deg0 == 0 and deg1 == 0:
            return False, "両方定数式（展開問題にならない）"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        syms0 = nouns[0].get_symbols()
        syms1 = nouns[1].get_symbols()
        e0 = syms0.get("expression", sympy.Integer(1))
        e1 = syms1.get("expression", sympy.Integer(1))
        expanded = sympy.expand(e0 * e1)     # 問題文に使う展開形
        factored = sympy.factor(expanded)    # 答えとなる因数分解形
        return LogicStep(
            operation_name="factorize",
            operands=[str(expanded)],        # operands[0] = 展開形（問題文用）
            sympy_expr=factored,             # 答え = 因数分解形
            narration_hint="因数分解する",
        )
