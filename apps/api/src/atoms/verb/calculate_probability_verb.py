"""CalculateProbabilityVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class CalculateProbabilityVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["EventAtom"]
    tags: ClassVar[List[str]] = ["probability"]

    def __init__(self, favorable: Optional[int] = None) -> None:
        self.favorable = favorable

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "EventAtom 1 つを要求"
        event = nouns[0]
        if type(event).__name__ != "EventAtom":
            return False, "EventAtom のみ受理"
        sample_space = event.get_symbols().get("sample_space_size")
        if sample_space is None or int(sample_space) <= 0:
            return False, "sample_space_size > 0 が必要"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        event = nouns[0]
        symbols = event.get_symbols()
        sample_space = int(symbols["sample_space_size"])
        if self.favorable is not None:
            fav = max(0, min(self.favorable, sample_space))
        else:
            descriptors = symbols.get("event_descriptors") or []
            fav = max(1, len(descriptors)) if descriptors else max(1, sample_space // 2)
        prob = sympy.Rational(fav, sample_space)
        return LogicStep(
            operation_name="calculate_probability",
            operands=[str(fav), str(sample_space)],
            sympy_expr=prob,
            narration_hint=f"全事象 {sample_space} のうち適合 {fav} の確率",
        )
