"""TransformShapeVerb（§18.2）"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

TransformType = Literal["translation", "rotation", "reflection", "revolution"]


@register_verb
class TransformShapeVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["PolygonAtom", "PrismAtom", "LinearFuncAtom"]
    tags: ClassVar[List[str]] = ["transform"]

    def __init__(self, transform_type: TransformType = "translation") -> None:
        self.transform_type: TransformType = transform_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "Atom 1 つを要求"
        atom = nouns[0]
        if type(atom).__name__ not in self.accepted_noun_types:
            return False, f"{type(atom).__name__} は不可"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        name = type(atom).__name__
        symbols = atom.get_symbols()

        if self.transform_type == "revolution" and name == "PolygonAtom":
            # 多角形を回転させた回転体の体積（円柱・円錐近似）
            area = sympy.simplify(symbols.get("area_expr", sympy.Integer(0)))
            # 簡略化: 回転半径を頂点の最大 x 座標と仮定し、Pappus の定理 V = 2π r̄ A
            r_bar = sympy.Rational(3)  # ダミーの重心距離
            volume = 2 * sympy.pi * r_bar * area
            return LogicStep(
                operation_name="revolution",
                operands=[name],
                sympy_expr=sympy.simplify(volume),
                narration_hint="多角形を回転させた回転体の体積",
            )

        if self.transform_type == "translation":
            dx, dy = rng.randint(1, 5), rng.randint(1, 5)
            expr = sympy.Tuple(sympy.Integer(dx), sympy.Integer(dy))
            narration = f"({dx}, {dy}) だけ平行移動"
        elif self.transform_type == "rotation":
            angle = rng.choice([90, 180, 270])
            expr = sympy.Integer(angle)
            narration = f"{angle} 度回転"
        elif self.transform_type == "reflection":
            expr = sympy.Integer(0)
            narration = "x 軸に対する対称移動"
        else:
            expr = sympy.Integer(0)
            narration = self.transform_type
        return LogicStep(
            operation_name=f"transform_{self.transform_type}",
            operands=[name],
            sympy_expr=expr,
            narration_hint=narration,
        )
