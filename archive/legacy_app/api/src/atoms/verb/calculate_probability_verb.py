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
        # EventAtom が記述可能な事象条件から導出した適合数を最優先で使う
        # （乱数の任意 favorable は「何の確率か」が定まらず題材が破綻するため廃止）。
        derived = symbols.get("favorable")
        description = symbols.get("event_description") or ""
        if self.favorable is not None:
            fav = max(0, min(self.favorable, sample_space))
        elif derived is not None and int(derived) > 0:
            fav = min(int(derived), sample_space)
        else:
            # 後方互換フォールバック（本来 EventAtom が favorable を供給する）
            fav = rng.randint(1, max(1, sample_space - 1))
        prob = sympy.Rational(fav, sample_space)
        hint = (
            f"{description}確率（全事象 {sample_space} のうち適合 {fav}）"
            if description
            else f"全事象 {sample_space} のうち適合 {fav} の確率"
        )
        return LogicStep(
            operation_name="calculate_probability",
            operands=[str(fav), str(sample_space)],
            sympy_expr=prob,
            narration_hint=hint,
        )
