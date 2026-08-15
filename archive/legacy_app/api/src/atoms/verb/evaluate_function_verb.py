"""EvaluateFunctionVerb（§18.2）

比例 $y=ax$・反比例 $y=a/x$ のグラフ上で、指定した $x=x_0$ に対応する
$y_0=f(x_0)$ を SymPy 代入で求める Verb。

- LinearFuncAtom:  $y = ax(+b)$ → 任意の整数 $x_0$ で $y_0$ は整数（moat）。
- InverseFuncAtom: $y = a/x$   → $a$ を割り切る整数 $x_0$ を選び $y_0$ を整数化。

答えは常に SymPy が計算した $y_0$（＝グラフ上の点の y 座標）であり、
描画される直線／双曲線と整合する。式や座標そのものを echo するのではなく
実際に代入計算するため moat が強い。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


def _divisors(n: int) -> List[int]:
    n = abs(int(n))
    if n == 0:
        return [1]
    return [d for d in range(1, n + 1) if n % d == 0]


@register_verb
class EvaluateFunctionVerb(VerbAtom):
    arity: ClassVar = 1
    accepted_noun_types: ClassVar[List[str]] = ["LinearFuncAtom", "InverseFuncAtom"]
    tags: ClassVar[List[str]] = ["function_evaluate"]

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if len(nouns) != 1:
            return False, "EvaluateFunctionVerb は Noun を 1 つだけ受け取る"
        name = type(nouns[0]).__name__
        if name not in self.accepted_noun_types:
            return False, f"{name} は EvaluateFunctionVerb に渡せない"
        if name == "InverseFuncAtom":
            c = nouns[0].get_symbols().get("constant")
            if c is None or sympy.simplify(c) == 0:
                return False, "反比例の比例定数が 0"
        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        atom = nouns[0]
        name = type(atom).__name__
        x = sympy.Symbol("x")
        expr = atom.get_symbols()["expression"]

        if name == "LinearFuncAtom":
            # 任意の非ゼロ整数 x0（結果は必ず整数）
            x0 = rng.choice([v for v in range(-5, 6) if v != 0])
            narration = "比例のグラフ上で x の値に対応する y を求める"
        else:  # InverseFuncAtom
            c = int(atom.get_symbols()["constant"])
            divs = _divisors(c)  # y0 が整数になる |x0|
            mag = rng.choice(divs)
            sign = rng.choice([1, -1])
            x0 = sign * mag
            narration = "反比例のグラフ上で x の値に対応する y を求める"

        y0 = sympy.nsimplify(expr.subs(x, sympy.Integer(x0)))
        y0 = sympy.simplify(y0)

        return LogicStep(
            operation_name="evaluate_function",
            operands=[str(expr), f"x={x0}"],
            sympy_expr=y0,
            narration_hint=narration,
        )
