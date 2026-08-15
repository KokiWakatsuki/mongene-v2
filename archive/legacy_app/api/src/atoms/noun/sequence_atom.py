"""SequenceAtom（§18.1）

数列（等差・等比・図形数列・分数列・表格子）を表す Atom。
GeneralizeFormulaVerb の入力となり、n 番目の式・初項・step_rule を保持する。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_PATTERN_TYPES = ("arithmetic", "geometric", "figurate", "fraction_seq", "table_grid")


@register_noun
class SequenceAtom(NounAtom):
    tags: ClassVar[List[str]] = ["sequence", "pattern", "generalization"]

    def __init__(
        self,
        pattern_type: str = "arithmetic",
        nth_term_expr: sympy.Expr | None = None,
        first_term: sympy.Expr | None = None,
        step_rule: Dict[str, Any] | None = None,
        min_terms_required: int = 3,
    ) -> None:
        self.pattern_type: str = pattern_type
        n = sympy.Symbol("n", positive=True, integer=True)
        self._n_symbol = n
        self.nth_term_expr: sympy.Expr = (
            sympy.Integer(0) if nth_term_expr is None else nth_term_expr
        )
        self.first_term: sympy.Expr = (
            sympy.Integer(0) if first_term is None else first_term
        )
        self.step_rule: Dict[str, Any] = step_rule or {}
        self.min_terms_required: int = min_terms_required

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "SequenceAtom":
        custom = constraints.custom or {}
        pattern_type: str = str(custom.get("pattern_type", rng.choice(_PATTERN_TYPES)))
        if pattern_type not in _PATTERN_TYPES:
            pattern_type = "arithmetic"
        min_terms_required: int = max(3, int(custom.get("min_terms_required", 3)))

        n = sympy.Symbol("n", positive=True, integer=True)

        if pattern_type == "arithmetic":
            a = rng.randint(1, 10)
            d = rng.randint(1, 5) * rng.choice([-1, 1])
            first_term = sympy.Integer(a)
            nth = sympy.Integer(a) + sympy.Integer(d) * (n - 1)
            step_rule = {"type": "arithmetic", "common_difference": d}
        elif pattern_type == "geometric":
            a = rng.randint(1, 5)
            r = rng.randint(2, 4)
            first_term = sympy.Integer(a)
            nth = sympy.Integer(a) * sympy.Integer(r) ** (n - 1)
            step_rule = {"type": "geometric", "common_ratio": r}
        elif pattern_type == "figurate":
            # マッチ棒で正方形 n 個 → 3n+1 のような形
            base = rng.randint(2, 4)
            inc = rng.randint(2, 4)
            first_term = sympy.Integer(base + inc * 0 + inc)  # n=1 時の値
            # f(n) = inc * n + (base)
            nth = sympy.Integer(inc) * n + sympy.Integer(base)
            first_term = nth.subs(n, 1)
            step_rule = {"type": "figurate", "base": base, "increment": inc}
        elif pattern_type == "fraction_seq":
            # 1/n や n/(n+1) など
            choice = rng.choice(["one_over_n", "n_over_n_plus_1"])
            if choice == "one_over_n":
                nth = sympy.Integer(1) / n
                first_term = sympy.Integer(1)
                step_rule = {"type": "fraction_seq", "form": "1/n"}
            else:
                nth = n / (n + 1)
                first_term = sympy.Rational(1, 2)
                step_rule = {"type": "fraction_seq", "form": "n/(n+1)"}
        else:  # table_grid
            # 行 m, 列 k のような格子。MVP では n 番目 = 2n^2 のような二次形
            a_coef = rng.randint(1, 3)
            nth = sympy.Integer(a_coef) * n**2
            first_term = sympy.Integer(a_coef)
            step_rule = {"type": "table_grid", "coefficient": a_coef}

        return SequenceAtom(
            pattern_type=pattern_type,
            nth_term_expr=sympy.expand(nth) if nth.is_polynomial(n) else nth,
            first_term=sympy.simplify(first_term),
            step_rule=step_rule,
            min_terms_required=min_terms_required,
        )

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "nth_term_expr": self.nth_term_expr,
            "first_term": self.first_term,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        # 各 pattern_type ごとに 10〜25 通り程度
        return len(_PATTERN_TYPES) * 20
