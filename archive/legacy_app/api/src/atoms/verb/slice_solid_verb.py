"""SliceSolidVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class SliceSolidVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["PrismAtom", "PyramidAtom", "SphereAtom"]
    tags: ClassVar[List[str]] = ["slice", "cross_section"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "立体 1 つを要求"
        solid = nouns[0]
        if type(solid).__name__ not in self.accepted_noun_types:
            return False, f"{type(solid).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        solid = nouns[0]
        symbols = solid.get_symbols()
        vol = sympy.simplify(symbols["volume_expr"])
        # 平面切断の比率 (1/2 〜 2/3 を乱択)
        ratio = sympy.Rational(*rng.choice([(1, 2), (1, 3), (2, 3), (1, 4)]))
        upper_volume = sympy.simplify(vol * ratio)
        lower_volume = sympy.simplify(vol - upper_volume)
        return LogicStep(
            operation_name="slice_solid",
            operands=[type(solid).__name__, str(ratio)],
            sympy_expr=sympy.Tuple(upper_volume, lower_volume),
            narration_hint=f"立体を比率 {ratio} で切断した上下の体積",
        )
