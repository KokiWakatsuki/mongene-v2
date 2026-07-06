"""AnalyzeDataVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Metric = Literal["mean", "median", "mode", "q1", "q3", "iqr", "cumulative_frequency", "cumulative_relative_frequency"]


@register_verb
class AnalyzeDataVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["DataSetAtom"]
    tags: ClassVar[List[str]] = ["data_analysis"]

    _KEY_MAP = {
        "mean": "mean", "median": "median", "mode": "mode",
        "q1": "q1", "q3": "q3",
        "cumulative_frequency": "cumulative_frequency",
        "cumulative_relative_frequency": "cumulative_relative_frequency",
    }

    def __init__(self, metric: Metric = "mean") -> None:
        self.metric: Metric = metric

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "DataSetAtom 1 つを要求"
        d = nouns[0]
        if type(d).__name__ != "DataSetAtom":
            return False, "DataSetAtom のみ受理"
        size_expr = d.get_symbols().get("size")
        size_val = int(size_expr) if size_expr is not None else len(getattr(d, "values", []) or [])
        if size_val < 5:
            return False, "データ数 n>=5 が必要"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        d = nouns[0]
        symbols = d.get_symbols()
        if self.metric == "iqr":
            q3 = symbols.get("q3", sympy.Integer(0))
            q1 = symbols.get("q1", sympy.Integer(0))
            expr = sympy.simplify(q3 - q1)
        else:
            expr = symbols.get(self._KEY_MAP[self.metric], sympy.Integer(0))
        return LogicStep(
            operation_name=f"analyze_{self.metric}",
            operands=["DataSetAtom"],
            sympy_expr=sympy.sympify(expr),
            narration_hint=f"データの {self.metric} を求める",
        )
