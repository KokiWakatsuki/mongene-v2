"""GraphDrawingVerb - 関数グラフの書き方・読み取り問題用 Verb

グラフ問題の典型構造:
  (1) x=N のとき y の値を求める（代入計算）
  (2) y=0 のとき x の値を求める（切片・解）
  (3) グラフ上の特定点の座標を求める
  (4) 2直線の交点を求める（連立方程式）

generate する MiddleRepresentation には:
  - 関数の式（expression）
  - キーポイント（x切片、y切片、代表点）
  - グラフの VisualDSL 情報
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class GraphDrawingVerb(VerbAtom):
    """関数グラフの書き方・読み取り問題を生成する Verb。

    LinearFuncAtom または QuadraticFuncAtom を受け取り、
    グラフの特徴点（切片・代表点・交点）を SymPy で計算して返す。
    """

    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = [
        "LinearFuncAtom",
        "QuadraticFuncAtom",
        "InverseFuncAtom",
    ]
    tags: ClassVar[List[str]] = ["linear_function", "quadratic_function", "graph"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "関数 Atom を 1 つ要求"
        if type(nouns[0]).__name__ not in self.accepted_noun_types:
            return False, f"{type(nouns[0]).__name__} は GraphDrawingVerb に渡せない"
        sym = nouns[0].get_symbols()
        if sym.get("expression") is None:
            return False, "expression が無い"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        sym = atom.get_symbols()
        x = sympy.Symbol("x")
        expr = sym.get("expression", sympy.Integer(0))
        name = type(atom).__name__

        # y 切片（x=0）
        y_intercept = sympy.simplify(expr.subs(x, 0))

        # x 切片（y=0 → x を求める）
        try:
            x_intercepts = sympy.solve(expr, x)
            x_int_str = str(x_intercepts[0]) if x_intercepts else "なし"
        except Exception:
            x_int_str = "なし"

        # 代表点（x=1, x=2 の値）
        pt1 = sympy.simplify(expr.subs(x, 1))
        pt2 = sympy.simplify(expr.subs(x, 2))

        # 傾き（LinearFuncAtom の場合）
        slope = sym.get("slope")
        slope_str = f", 傾き={slope}" if slope is not None else ""

        return LogicStep(
            operation_name="graph_key_points",
            operands=[str(expr)],
            sympy_expr=y_intercept,  # y 切片を主要答えとして返す
            narration_hint=(
                f"関数 $y = {sympy.latex(expr)}$ のグラフ{slope_str}: "
                f"y切片={y_intercept}, x切片={x_int_str}, "
                f"点(1,{pt1}), 点(2,{pt2})"
            ),
        )
