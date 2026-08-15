"""TriangleAreaVerb

2 本の LinearFuncAtom (y=a₁x+b₁, y=a₂x+b₂) と y 軸が作る三角形の面積を求める Verb。

面積公式: S = (b₁-b₂)² / (2|a₁-a₂|)
  y 軸上の 2 切片 b₁, b₂ → 底辺 |b₁-b₂|
  2 直線の交点 x₀ = (b₁-b₂)/(a₂-a₁) → 高さ |x₀|
  S = ½ × |b₁-b₂| × |x₀| = (b₁-b₂)² / (2|a₁-a₂|)
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class TriangleAreaVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = ["LinearFuncAtom"]
    tags: ClassVar[List[str]] = ["triangle_area"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 2:
            return False, "LinearFuncAtom 2 つが必要"
        for n in nouns:
            if type(n).__name__ != "LinearFuncAtom":
                return False, f"{type(n).__name__} は TriangleAreaVerb に渡せない"
        s1 = nouns[0].get_symbols()["slope"]
        s2 = nouns[1].get_symbols()["slope"]
        if sympy.simplify(s1 - s2) == 0:
            return False, "平行直線（三角形が形成されない）"
        # 両直線が原点を通る比例関数の場合 → y 切片 = 0 → 面積 = 0
        b1 = nouns[0].y_intercept()
        b2 = nouns[1].y_intercept()
        if sympy.simplify(b1) == 0 and sympy.simplify(b2) == 0:
            return False, "両直線が原点を通る（三角形の面積 = 0）"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        b1 = nouns[0].y_intercept()
        b2 = nouns[1].y_intercept()
        a1 = nouns[0].get_symbols()["slope"]
        a2 = nouns[1].get_symbols()["slope"]
        area = sympy.Rational(1, 2) * sympy.Abs(b1 - b2) ** 2 / sympy.Abs(a1 - a2)
        area = sympy.simplify(area)
        return LogicStep(
            operation_name="triangle_area",
            operands=[str(b1), str(b2), str(a1), str(a2)],
            sympy_expr=area,
            narration_hint="交点と座標軸で囲まれる三角形の面積",
        )
