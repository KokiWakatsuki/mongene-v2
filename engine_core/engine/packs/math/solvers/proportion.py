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


def _format_direct_proportion_expr(a: sympy.Expr) -> str:
    """比例の式 y=ax の表示（a=1,-1 の特殊表記を含む）。"""
    if a == 1:
        return "y = x"
    if a == -1:
        return "y = -x"
    # **分数の比例定数はかっこで囲む。** `y = -4/3x` と書くと
    # `(-4/3)x` なのか `-4/(3x)` なのか読めない（反比例を隣の単元で扱うので紛れる）。
    if sympy.nsimplify(a).q != 1:
        return f"y = ({fmt_number(a)})x"
    return f"y = {fmt_number(a)}x"


def _format_inverse_proportion_expr(a: sympy.Expr) -> str:
    """反比例の式 y=a/x の表示。

    **分数の比例定数は分母をまとめる。** `fmt_number` が `-62/5` を返すので、
    そのまま `/x` を継ぐと `y = -62/5/x` になり、スラッシュが2つ並んで
    式の意味が確定しない（答えから逆算しないと読めなかった）。
    `-62/5` は `-62/(5x)` と書けば一意になる。
    """
    r = sympy.nsimplify(a)
    if r.q != 1:
        sign = "-" if r < 0 else ""
        return f"y = {sign}{abs(r.p)}/({r.q}x)"
    return f"y = {fmt_number(a)}/x"


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
                result_display=(
                    f"aは{'正' if a_s > 0 else '負'}、xは{'正' if x_s > 0 else '負'}"
                ),
                narration="比例定数と x の値、それぞれの符号（正か負か）を確認する。",
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
            result_display=("ただ1つに決まる" if truthy else "ただ1つには決まらない"),
            narration="x の値を1つ決めたとき、それに対応する y の値がただ1つに決まるかどうかを調べる。",
        ),
        Step(
            op="judge_functional",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="y の値がただ1つに決まるなら関数であるといえ、決まらなければ関数であるとはいえない。",
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
            result_display="、".join(fmt_number(r) for r in ratios),
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
            result_display="、".join(fmt_number(pr) for pr in products),
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


# ---------------------------------------------------------------------------
# math.solve_direct_proportion_from_point（g1_l32.find_value Lv1/Lv2）
# 比例のグラフ・条件が通る1点 (x0,y0) から比例定数 a=y0/x0 を求め、式 y=ax を決める。
# ---------------------------------------------------------------------------
@register_solver("math.solve_direct_proportion_from_point")
def solve_direct_proportion_from_point(x0: object, y0: object, mode: object) -> Solution:
    """比例が通る1点から比例定数を求め、式 y=ax を決める（g1_l32.find_value）。

    mode="integer"（Lv1）: 比例定数 a が整数になる1手順。
    mode="fraction"（Lv2）: 比例定数 a が分数になり、約分の1手順が増える（level_sep）。
    答えは式 y=ax（asked=expression）。narration には数字を書かない。
    """
    m = str(mode)
    if m not in ("integer", "fraction"):
        raise ValueError(f"mode は 'integer' か 'fraction' のいずれか（受領: {mode!r}）")
    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a = y0_s / x0_s
    expr = a * sympy.Symbol("x")
    disp = _format_direct_proportion_expr(a)

    steps: list[Step] = [
        Step(
            op="substitute_point",
            args=[fmt_number(x0_s), fmt_number(y0_s)],
            result_srepr=sympy.srepr(a),
            result_display=f"a = {fmt_number(y0_s)} / {_paren_neg(x0_s)}",
            narration="比例の式 y=ax に、通る点の x, y の値をあてはめ、比例定数を求める式をつくる。",
        ),
    ]
    if m == "fraction":
        steps.append(
            Step(
                op="simplify_fraction",
                args=[],
                result_srepr=sympy.srepr(a),
                result_display=f"a = {fmt_number(a)}",
                narration="求めた商を約分し、比例定数を最も簡単な分数の形に整理する。",
            )
        )
    steps.append(
        Step(
            op="form_expression",
            args=[fmt_number(a)],
            result_srepr=sympy.srepr(expr),
            result_display=disp,
            narration="求めた比例定数を使って、比例の式を組み立てる。",
            # **`a = -5` の行が無かった。** `a = -20 / 4` の次がいきなり `y = -5x` で、
            # 比例定数の値そのものが解説に一度も出ていない（Lv2 には約分の手があるのに
            # Lv1 には無い、という単元内の食い違いでもあった）。
            detail=f"比例定数は a = {fmt_number(a)} なので、y = ax にあてはめる。",
        )
    )
    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.solve_inverse_proportion_from_point（g1_l35.find_value Lv1/Lv2）
# 反比例のグラフ・条件が通る1点 (x0,y0) から比例定数 a=x0*y0 を求め、式 y=a/x を決める。
# ---------------------------------------------------------------------------
@register_solver("math.solve_inverse_proportion_from_point")
def solve_inverse_proportion_from_point(x0: object, y0: object, mode: object) -> Solution:
    """反比例が通る1点から比例定数を求め、式 y=a/x を決める（g1_l35.find_value）。

    mode="basic"（Lv1）: 正の座標の点から、積 x0*y0 がそのまま比例定数になる1手順。
    mode="signed"（Lv2）: 負の座標を含む点から求めるため、符号の確認が1手順増える（level_sep）。
    答えは式 y=a/x（asked=expression）。narration には数字を書かない。
    """
    m = str(mode)
    if m not in ("basic", "signed"):
        raise ValueError(f"mode は 'basic' か 'signed' のいずれか（受領: {mode!r}）")
    x0_s, y0_s = sympy.nsimplify(x0), sympy.nsimplify(y0)
    a = x0_s * y0_s
    expr = a / sympy.Symbol("x")
    disp = _format_inverse_proportion_expr(a)

    steps: list[Step] = []
    if m == "signed":
        steps.append(
            Step(
                op="check_signs",
                args=[],
                result_srepr=sympy.srepr(a),
                result_display=(
                    f"x は{'正' if x0_s > 0 else '負'}、y は{'正' if y0_s > 0 else '負'}"
                ),
                narration="通る点の x 座標と y 座標、それぞれの符号（正か負か）を確認する。",
            )
        )
    steps.append(
        Step(
            op="substitute_point",
            args=[fmt_number(x0_s), fmt_number(y0_s)],
            result_srepr=sympy.srepr(a),
            result_display=f"a = {_paren_neg(x0_s)} × {_paren_neg(y0_s)}",
            narration="反比例の式 y=a/x に、通る点の x, y の値をあてはめ、比例定数を求める式をつくる。",
        ),
    )
    steps.append(
        Step(
            op="form_expression",
            args=[fmt_number(a)],
            result_srepr=sympy.srepr(expr),
            result_display=disp,
            narration="求めた比例定数を使って、反比例の式を組み立てる。",
            detail=f"比例定数は a = {fmt_number(a)} なので、y = a/x にあてはめる。",
        )
    )
    answer = SymbolicAnswer(srepr=sympy.srepr(expr), display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_proportion_graph_direction（g1_l31.knowledge Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.judge_proportion_graph_direction")
def judge_proportion_graph_direction(is_a_positive: object) -> Solution:
    """比例定数 a の符号から比例グラフの向きを判別する（g1_l31.knowledge Lv1）。

    is_a_positive（bool 相当）だけから判定する（double-solve）。答えは ChoiceAnswer
    （原点を通ることは符号によらない不変の事実として correct 文に含める）。
    narration に数字は書かない。
    """
    truthy = str(is_a_positive).lower() in ("true", "1")
    correct = "右上がりの直線になる（原点を通る）" if truthy else "右下がりの直線になる（原点を通る）"
    other = "右下がりの直線になる（原点を通る）" if truthy else "右上がりの直線になる（原点を通る）"
    steps = [
        Step(
            op="check_sign",
            args=[],
            result_srepr=("positive" if truthy else "negative"),
            result_display=("aは正" if truthy else "aは負"),
            narration="比例の式 y=ax の比例定数 a の符号（正か負か）を確認する。",
        ),
        Step(
            op="judge_proportion_graph_direction",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="aが正なら右上がり、負なら右下がりの直線になる。どちらも必ず原点を通る。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="proportion.judge_graph_direction")
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.judge_hyperbola_quadrants（g1_l34.knowledge Lv1）
# ---------------------------------------------------------------------------
@register_solver("math.judge_hyperbola_quadrants")
def judge_hyperbola_quadrants(is_a_positive: object) -> Solution:
    """比例定数 a の符号から双曲線が座標平面のどの部分にあるかを判別する（g1_l34.knowledge Lv1）。

    is_a_positive（bool 相当）だけから判定する（double-solve）。答えは ChoiceAnswer
    （二つの枝からなり軸に交わらないことは符号によらない不変の事実として correct 文に
    含める）。narration に数字は書かない。

    **「象限」は使わない。** 中学の教科書に無い用語（高校で扱う）なので、中1の
    反比例のグラフでは「右上と左下の部分」「左上と右下の部分」と書く。
    """
    truthy = str(is_a_positive).lower() in ("true", "1")
    positive_side = "右上と左下の部分にある（二つの枝からなり、x軸・y軸と交わらない）"
    negative_side = "左上と右下の部分にある（二つの枝からなり、x軸・y軸と交わらない）"
    correct = positive_side if truthy else negative_side
    other = negative_side if truthy else positive_side
    steps = [
        Step(
            op="check_sign",
            args=[],
            result_srepr=("positive" if truthy else "negative"),
            result_display=("aは正" if truthy else "aは負"),
            narration="反比例の式 y=a/x の比例定数 a の符号（正か負か）を確認する。",
        ),
        Step(
            op="judge_hyperbola_quadrants",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration="aが正なら右上と左下、負なら左上と右下の部分に双曲線がある。"
            "どちらも二つの枝からなり、x軸・y軸と交わらない。",
        ),
    ]
    answer = ChoiceAnswer(correct=correct, distractors=[other], fact_id="proportion.judge_hyperbola_quadrants")
    return Solution(answer=answer, steps=steps)


__all__ = [
    "evaluate_direct_proportion",
    "evaluate_inverse_proportion",
    "judge_functional_relation",
    "judge_direct_proportion_table",
    "judge_inverse_proportion_table",
    "solve_direct_proportion_from_point",
    "solve_inverse_proportion_from_point",
    "judge_proportion_graph_direction",
    "judge_hyperbola_quadrants",
]
