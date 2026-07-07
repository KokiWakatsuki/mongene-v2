"""FormulateVerb（立式型 word_problem 用・§18.2）

「数量を文字式で表す」型の文章題を生成する Verb。方程式を解く WordProblemStructure と異なり、
答えは **式そのもの**（解かない）。SymPy で式が well-formed であることを検証してから使う（moat）。

- mode="expression": 数量を文字式で表す（例: 3x+2）。答え = その式。

将来の拡張（別 mode）:
- mode="equation":   等式で表す（左辺 = 右辺）。
- mode="inequality": 不等式で表す。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Mode = Literal["expression"]


def _get_expr(noun: NounAtom) -> sympy.Expr:
    sym = noun.get_symbols()
    return sym.get("value") or sym.get("expression") or sympy.Integer(0)


@register_verb
class FormulateVerb(VerbAtom):
    """数量を文字式で表す（立式）。答えは式そのもので、計算・求解はしない。"""

    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["PolynomialAtom", "NumberAtom"]
    tags: ClassVar[List[str]] = ["word_problem", "formulate"]

    def __init__(self, mode: Mode = "expression") -> None:
        self.mode: Mode = mode

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "FormulateVerb は 1 つの Noun を要求する"
        n = nouns[0]
        if type(n).__name__ not in self.accepted_noun_types:
            return False, f"{type(n).__name__} は FormulateVerb に渡せない"
        if self.mode != "expression":
            return False, f"未対応の mode: {self.mode}"
        # 立式は「文字を含む式」を対象にする（定数だけでは『式で表す』題材にならない）
        expr = sympy.expand(_get_expr(n))
        if not expr.free_symbols:
            return False, "文字（変数）を含まない式は立式題材に不適"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        if self.mode != "expression":
            raise ValueError(f"未対応の mode: {self.mode}")

        atom = nouns[0]
        expr = sympy.expand(_get_expr(atom))

        # moat: 立式対象として well-formed（変数を含む有限の式）であることを SymPy で検証する
        if not expr.free_symbols:
            raise AssertionError(f"立式対象に変数が無い: {expr}")
        if not expr.is_finite and expr.is_finite is not None:
            raise AssertionError(f"式が有限でない: {expr}")

        expr_str = str(expr)
        return LogicStep(
            operation_name="formulate_expression",
            operands=[type(atom).__name__, expr_str],
            sympy_expr=expr,
            narration_hint=f"場面に現れる数量を文字式 {expr_str} で表す（立式・解かない）",
        )
