"""UnfoldNetVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class UnfoldNetVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["PrismAtom", "PyramidAtom"]
    tags: ClassVar[List[str]] = ["unfold", "net"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "立体 1 つを要求"
        solid = nouns[0]
        if type(solid).__name__ not in self.accepted_noun_types:
            return False, f"{type(solid).__name__} は展開不可（球は不可）"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        solid = nouns[0]
        symbols = solid.get_symbols()
        # 展開図の総面積 = 表面積
        total_area = sympy.simplify(symbols.get("surface_area_expr", sympy.Integer(0)))
        return LogicStep(
            operation_name="unfold_net",
            operands=[type(solid).__name__],
            sympy_expr=total_area,
            narration_hint=f"{type(solid).__name__}の展開図の総面積（=表面積）",
        )
