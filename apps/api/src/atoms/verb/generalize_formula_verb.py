"""GeneralizeFormulaVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class GeneralizeFormulaVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["SequenceAtom"]
    tags: ClassVar[List[str]] = ["sequence", "generalization"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "数列 1 つを要求"
        seq = nouns[0]
        if type(seq).__name__ != "SequenceAtom":
            return False, "SequenceAtom のみ受理"
        nth = seq.get_symbols().get("nth_term_expr")
        if nth is None:
            return False, "nth_term_expr が無い"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        seq = nouns[0]
        nth = seq.get_symbols()["nth_term_expr"]
        return LogicStep(
            operation_name="generalize_formula",
            operands=[type(seq).__name__],
            sympy_expr=sympy.simplify(nth),
            narration_hint="数列の第 n 項の一般式を導く",
        )
