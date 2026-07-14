"""比例・反比例まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

C4（g1 関数・比例と反比例）クラスタの非 visual セル群。solver は**問題パラメータだけ**
から答えと steps を導く（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。
乱数は引かない。

- `math.evaluate_direct_proportion(a, x0, mode)`: y=ax に x=x0 を代入して y を求める
  （mode="basic"=Lv1・1手順／mode="signed"=Lv2・負や分数の比例定数で複数手順・g1_l29.calculation）。
- `math.evaluate_inverse_proportion(a, known, mode)`: y=a/x に x=x0 を代入して y を求める
  （mode="forward"=Lv1）、または y=y0 から x を逆算する（mode="backward"=Lv2・g1_l33.calculation）。
- `math.judge_direct_proportion_table`: 表（x,y の対応）が比例かを商 y/x が一定かで判別する
  （g1_l29.knowledge Lv2）。
- `math.judge_inverse_proportion_table`: 表が反比例かを積 xy が一定かで判別する
  （g1_l33.knowledge Lv2）。
- `math.judge_functional_relation`: 2量の関係が関数（xの値を決めるとyがただ1つに決まるか）を
  判別する（g1_l28.knowledge Lv2）。

narration には数字を書かない（G-Q5t 偽陽性の元・鉄則⑦）。"0" は例外（=0 の 0 等）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import ChoiceAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers.arithmetic import fmt_number


def _paren_neg(v: sympy.Expr) -> str:
    """負数は括弧で囲む（代入表示の可読性。例: -4 -> "(-4)"）。"""
    s = fmt_number(v)
    return f"({s})" if v < 0 else s


# ---------------------------------------------------------------------------
# math.evaluate_direct_proportion（g1_l29.calculation Lv1/Lv2）
# 比例 y=ax に x=x0 を代入して y を求める（代入1手順）。
# ---------------------------------------------------------------------------
@register_solver("math.evaluate_direct_proportion")
def evaluate_direct_proportion(a: object, x0: object, mode: object) -> Solution:
    """比例 y=ax の x=x0 における y の値を求める（g1_l29.calculation）。

    mode="basic"（Lv1）: 代入して計算するだけ（2手順）。
    mode="signed"（Lv2）: 負・分数の比例定数を含むため、符号の確認を1手順増やす（3手順・level_sep）。
    答えは1つの数値 y（asked=value）。narration には数字を書かない。
    """
    m = str(mode)
    if m not in ("basic", "signed"):
        raise ValueError(f"mode は 'basic' か 'signed' のいずれか（受領: {mode!r}）")
    a_s, x_s = sympy.nsimplify(a), sympy.nsimplify(x0)
    y = a_s * x_s
    prod_disp = f"y = {_paren_neg(a_s)} × {_paren_neg(x_s)}"

    steps: list[Step] = []
    if m == "signed":
        steps.append(
            Step(
                op="check_signs",
                args=[],
                result_srepr=sympy.srepr(a_s * x_s),
                result_display="比例定数とxの値の符号を確認する",
                narration="比例定数とxの値、それぞれの符号（正か負か）を確認する。",
            )
        )
    steps.append(
        Step(
            op="substitute_x",
            args=[fmt_number(a_s), fmt_number(x_s)],
            result_srepr=sympy.srepr(a_s * x_s),
            result_display=prod_disp,
            narration="比例定数と x の値を、比例の式 y=ax の x にあてはめる。",
        )
    )
    steps.append(
        Step(
            op="evaluate",
            args=[prod_disp],
            result_srepr=sympy.srepr(y),
            result_display=f"y = {fmt_number(y)}",
            narration="かけ算を計算して y の値を求める。",
        )
    )
    answer = SymbolicAnswer(srepr=sympy.srepr(y), display=fmt_number(y))
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.evaluate_inverse_proportion（g1_l33.calculation Lv1/Lv2）
# 反比例 y=a/x に x=x0 を代入して y を求める（順方向）、または y=y0 から x を逆算する（逆方向）。
# ---------------------------------------------------------------------------
@register_solver("math.evaluate_inverse_proportion")
def evaluate_inverse_proportion(a: object, known: object, mode: object) -> Solution:
    """反比例 y=a/x の値を求める（g1_l33.calculation）。

    mode="forward": x=known を代入して y=a/known を求める（1手順・Lv1）。
    mode="backward": y=known から x=a/known を逆に解いて求める（複数手順・Lv2）。
    どちらも比例定数 a・積 xy=a が一定という関係だけから決定論的に定まる（double-solve）。
    """
    a_s, k_s = sympy.nsimplify(a), sympy.nsimplify(known)
    m = str(mode)
    if m == "forward":
        y = a_s / k_s
        steps = [
            Step(
                op="substitute_x",
                args=[fmt_number(a_s), fmt_number(k_s)],
                result_srepr=sympy.srepr(y),
                result_display=f"y = {fmt_number(a_s)} / {_paren_neg(k_s)}",
                narration="比例定数と x の値を、反比例の式 y=a/x の x にあてはめる。",
            ),
            Step(
                op="evaluate",
                args=[f"y = {fmt_number(a_s)} / {_paren_neg(k_s)}"],
                result_srepr=sympy.srepr(y),
                result_display=f"y = {fmt_number(y)}",
                narration="わり算を計算して y の値を求める。",
            ),
        ]
        answer = SymbolicAnswer(srepr=sympy.srepr(y), display=fmt_number(y))
        return Solution(answer=answer, steps=steps)
    if m == "backward":
        x = a_s / k_s
        steps = [
            Step(
                op="substitute_y",
                args=[fmt_number(a_s), fmt_number(k_s)],
                result_srepr=sympy.srepr(x),
                result_display=f"{fmt_number(k_s)} = {fmt_number(a_s)} / x",
                narration="比例定数と y の値を、反比例の式 y=a/x の y にあてはめる。",
            ),
            Step(
                op="solve_for_x",
                args=[f"{fmt_number(k_s)} = {fmt_number(a_s)} / x"],
                result_srepr=sympy.srepr(x),
                result_display=f"x = {fmt_number(x)}",
                narration="式を x について整理し直して、x の値を求める。",
            ),
        ]
        answer = SymbolicAnswer(srepr=sympy.srepr(x), display=fmt_number(x))
        return Solution(answer=answer, steps=steps)
    raise ValueError(f"mode は 'forward' か 'backward' のいずれか（受領: {mode!r}）")


# ---------------------------------------------------------------------------
# math.judge_functional_relation（g1_l28.knowledge Lv2）
# 2量の関係が「yはxの関数」といえるか（xの値を決めるとyがただ1つに決まるか）を判別する。
# ---------------------------------------------------------------------------
@register_solver("math.judge_functional_relation")
def judge_functional_relation(is_functional: object) -> Solution:
    """2量の関係が関数関係かを判別する（knowledge 判別・g1_l28 Lv2）。

    is_functional（bool 相当）だけから判定する（具体的な場面文は recipe が構成する
    surface であり、判定そのものは「x を決めると y がただ1つに決まるか」という bool
    フラグに既に還元されている・double-solve）。答えは ChoiceAnswer（真偽で correct が
    変わる verify 型）。narration に数字は書かない。
    """
    truthy = str(is_functional).lower() in ("true", "1")
    correct = "yはxの関数であるといえる" if truthy else "yはxの関数であるとはいえない"
    other = "yはxの関数であるとはいえない" if truthy else "yはxの関数であるといえる"
    steps = [
        Step(
            op="check_unique_determination",
            args=[],
            result_srepr=("functional" if truthy else "not_functional"),
            result_display="xの値を1つ決めたとき、yの値がただ1つに決まるかを調べる",
            narration="xの値を1つ決めたとき、それに対応するyの値がただ1つに決まるかどうかを調べる。",
        ),
        Step(
            op="judge_functional",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="yの値がただ1つに決まるなら関数であるといえ、決まらなければ関数であるとはいえない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="function.judge_functional_relation")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_direct_proportion_table（g1_l29.knowledge Lv2）
# 表のx,yの対応が比例か(商y/xが一定か)を判別する。
# ---------------------------------------------------------------------------
@register_solver("math.judge_direct_proportion_table")
def judge_direct_proportion_table(xs: object, ys: object) -> Solution:
    """表の対応 (x_i, y_i) が比例かを、商 y/x が一定かで判別する（g1_l29.knowledge Lv2）。

    x, y の数値列だけから double-solve する。比例なら比例定数 a=y/x（一定値）を答えに含める。
    答えは ChoiceAnswer（「比例するといえる（比例定数は a）」／「比例するとはいえない」）。
    narration に数字は書かない。
    """
    x_list = [sympy.nsimplify(v) for v in cast("list[object]", xs)]
    y_list = [sympy.nsimplify(v) for v in cast("list[object]", ys)]
    if len(x_list) != len(y_list) or len(x_list) < 2:
        raise ValueError("xs と ys は同じ長さ(2以上)であること")
    ratios = [y_list[i] / x_list[i] for i in range(len(x_list))]
    is_proportional = all(r == ratios[0] for r in ratios)
    # 答えは digit-free（鉄則①）: 比例定数の値そのものは選択肢に含めない
    # （判別そのものが学習点であり、値の算出は calculation セルの領域）。
    correct = "比例するといえる" if is_proportional else "比例するとはいえない"
    other = "比例するとはいえない" if is_proportional else "比例するといえる"
    steps = [
        Step(
            op="compute_ratio_y_over_x",
            args=[],
            result_srepr=str([sympy.srepr(r) for r in ratios]),
            result_display="対応するxとyの商 y/x を、それぞれ計算する",
            narration="表の対応するxとyについて、商y/xをそれぞれ計算する。",
        ),
        Step(
            op="judge_constant_ratio",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="商y/xがすべて等しければ比例するといえる。等しくなければ比例するとはいえない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="proportion.judge_table")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_inverse_proportion_table（g1_l33.knowledge Lv2）
# 表のx,yの対応が反比例か(積xyが一定か)を判別する。
# ---------------------------------------------------------------------------
@register_solver("math.judge_inverse_proportion_table")
def judge_inverse_proportion_table(xs: object, ys: object) -> Solution:
    """表の対応 (x_i, y_i) が反比例かを、積 xy が一定かで判別する（g1_l33.knowledge Lv2）。

    x, y の数値列だけから double-solve する。答えは ChoiceAnswer（「反比例するといえる」／
    「反比例するとはいえない」）。digit-free（鉄則①・比例定数の値そのものは選択肢に含めない
    ＝判別そのものが学習点であり、値の算出は calculation セルの領域）。narration に数字は書かない。
    """
    x_list = [sympy.nsimplify(v) for v in cast("list[object]", xs)]
    y_list = [sympy.nsimplify(v) for v in cast("list[object]", ys)]
    if len(x_list) != len(y_list) or len(x_list) < 2:
        raise ValueError("xs と ys は同じ長さ(2以上)であること")
    products = [x_list[i] * y_list[i] for i in range(len(x_list))]
    is_inverse = all(p == products[0] for p in products)
    correct = "反比例するといえる" if is_inverse else "反比例するとはいえない"
    other = "反比例するとはいえない" if is_inverse else "反比例するといえる"
    steps = [
        Step(
            op="compute_product_xy",
            args=[],
            result_srepr=str([sympy.srepr(p) for p in products]),
            result_display="対応するxとyの積 xy を、それぞれ計算する",
            narration="表の対応するxとyについて、積xyをそれぞれ計算する。",
        ),
        Step(
            op="judge_constant_product",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="積xyがすべて等しければ反比例するといえる。等しくなければ反比例するとはいえない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="proportion.judge_inverse_table")
    return Solution(answer=answer, steps=steps)


__all__ = [
    "evaluate_direct_proportion",
    "evaluate_inverse_proportion",
    "judge_functional_relation",
    "judge_direct_proportion_table",
    "judge_inverse_proportion_table",
]
