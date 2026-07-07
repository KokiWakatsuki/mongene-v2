"""ReadCoordinateVerb（§18.2）

座標平面上の点 $A(x, y)$ について、その座標を答えとして返す Verb。
中1「座標の概念と点のとり方」（g1_l30）の visual form に用いる。

図（Graph_Renderer が描く点マーカー）と整合する $(x, y)$ を SymPy Tuple として
返すため、読み取り問題「図の点 A の座標を答えなさい」の ground truth になる。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class ReadCoordinateVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["PointAtom"]
    tags: ClassVar[List[str]] = ["coordinate_read"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "ReadCoordinateVerb は Noun を 1 つだけ受け取る"
        if type(nouns[0]).__name__ != "PointAtom":
            return False, f"{type(nouns[0]).__name__} は ReadCoordinateVerb に渡せない"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        sym = nouns[0].get_symbols()
        x = sym["x"]
        y = sym["y"]
        label = str(sym.get("label", sympy.Symbol("A")))
        return LogicStep(
            operation_name="read_coordinate",
            operands=[label, str(x), str(y)],
            sympy_expr=sympy.Tuple(x, y),
            narration_hint="座標平面上の点の座標を読み取る",
        )
