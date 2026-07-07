"""FormulateVerb（立式型 word_problem 用・§18.2）

「数量を文字式で表す／等式・不等式で表す」型の文章題を生成する Verb。方程式を解く
WordProblemStructure と異なり、答えは **式・等式・不等式そのもの**（解かない）。
SymPy で well-formed であることを検証してから使う（moat）。

- mode="expression": 数量を文字式で表す（例: 3x+2）。答え = その式。
- mode="equation":   数量の関係を等式で表す（例: 3x+2 = 20）。答え = sympy.Eq。
- mode="inequality": 数量の関係を不等式で表す（例: 3x <= 20）。答え = sympy.Rel。

equation/inequality は変数 x を Verb 側で導入し、係数を Atom の値＋seeded rng から構成する
（Atom の具体値が難易度 atom_constraints を尊重する）。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Mode = Literal["expression", "equation", "inequality"]

_X = sympy.Symbol("x")


def _get_expr(noun: NounAtom) -> sympy.Expr:
    sym = noun.get_symbols()
    return sym.get("value") or sym.get("expression") or sympy.Integer(0)


def _coeff_from_atom(noun: NounAtom, rng: random.Random) -> int:
    """Atom の値から 0 でない小さな整数係数を得る（無ければ rng でフォールバック）。"""
    expr = sympy.expand(_get_expr(noun))
    val: Optional[int] = None
    if expr.is_Integer:
        val = int(expr)
    else:
        # 多項式なら主要係数（の 1 つ）を使う
        try:
            coeffs = [int(c) for c in sympy.Poly(expr, *sorted(expr.free_symbols, key=str)).coeffs()]
            val = next((c for c in coeffs if c != 0), None)
        except (sympy.PolynomialError, TypeError, ValueError):
            val = None
    if not val:
        val = rng.randint(2, 9)
    # 立式に扱いやすい範囲へ収める（符号は保つ）
    val = int(val)
    if val == 0:
        val = rng.randint(2, 9)
    return val


@register_verb
class FormulateVerb(VerbAtom):
    """数量を文字式・等式・不等式で表す（立式）。答えはその式自体で、計算・求解はしない。"""

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
        if self.mode not in ("expression", "equation", "inequality"):
            return False, f"未対応の mode: {self.mode}"
        if self.mode == "expression":
            # expression は「文字を含む式」を対象にする（定数だけでは『式で表す』題材にならない）
            expr = sympy.expand(_get_expr(n))
            if not expr.free_symbols:
                return False, "文字（変数）を含まない式は立式題材に不適"
        # equation/inequality は変数を Verb 側で導入するため NumberAtom でも可
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        if self.mode == "expression":
            return self._solve_expression(nouns[0])
        if self.mode == "equation":
            return self._solve_equation(nouns[0], rng)
        if self.mode == "inequality":
            return self._solve_inequality(nouns[0], rng)
        raise ValueError(f"未対応の mode: {self.mode}")

    def _solve_expression(self, atom: NounAtom) -> LogicStep:
        expr = sympy.expand(_get_expr(atom))
        # moat: 立式対象として well-formed（変数を含む式）であることを SymPy で検証する
        if not expr.free_symbols:
            raise AssertionError(f"立式対象に変数が無い: {expr}")
        expr_str = str(expr)
        return LogicStep(
            operation_name="formulate_expression",
            operands=[type(atom).__name__, expr_str],
            sympy_expr=expr,
            narration_hint=f"場面に現れる数量を文字式 {expr_str} で表す（立式・解かない）",
        )

    def _solve_equation(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        a = _coeff_from_atom(atom, rng)
        b = rng.randint(1, 9)
        c = rng.randint(10, 30)
        lhs = a * _X + b
        eq = sympy.Eq(lhs, c)

        # moat: well-formed な等式（変数を含み、恒真/恒偽でない）であることを SymPy で検証
        if not isinstance(eq, sympy.Eq):
            raise AssertionError(f"等式の構成に失敗: {eq}")
        if not eq.free_symbols:
            raise AssertionError(f"等式に変数が無い: {eq}")
        if sympy.simplify(lhs - c) == 0:
            raise AssertionError(f"恒真な等式（両辺一致）: {eq}")

        eq_str = str(eq)
        return LogicStep(
            operation_name="formulate_equation",
            operands=[type(atom).__name__, eq_str],
            sympy_expr=eq,
            narration_hint=f"数量の関係を等式 {sympy.latex(eq)} で表す（立式・解かない）",
        )

    def _solve_inequality(self, atom: NounAtom, rng: random.Random) -> LogicStep:
        a = _coeff_from_atom(atom, rng)
        b = rng.randint(0, 9)
        c = rng.randint(10, 30)
        lhs = a * _X + b
        rel_builder = rng.choice([sympy.Le, sympy.Ge, sympy.Lt, sympy.Gt])
        ineq = rel_builder(lhs, c)

        # moat: well-formed な不等式（変数を含み、恒真/恒偽でない）であることを SymPy で検証
        from sympy.core.relational import Relational

        if not isinstance(ineq, Relational):
            raise AssertionError(f"不等式の構成に失敗: {ineq}")
        if not ineq.free_symbols:
            raise AssertionError(f"不等式に変数が無い: {ineq}")
        if ineq in (sympy.true, sympy.false):
            raise AssertionError(f"恒真/恒偽な不等式: {ineq}")

        ineq_str = str(ineq)
        return LogicStep(
            operation_name="formulate_inequality",
            operands=[type(atom).__name__, ineq_str],
            sympy_expr=ineq,
            narration_hint=f"数量の関係を不等式 {sympy.latex(ineq)} で表す（立式・解かない）",
        )
