"""一次方程式（1変数）を解く独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（方程式の文字列 equation_str と mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C1（g1 数と式・一次方程式）クラスタの解法セル群を1つの汎用ソルバに集約する（arithmetic.py の
`evaluate_numeric_expression` と同型）:
  `math.solve_linear_equation(equation_str, mode)` が "lhs=rhs" を sympy.solve で x について解く。
  答えは解 x=定数（Integer/Rational）。mode ごとに steps の op 列を変える（＝level_sep）。
  定数答えの G-Q5t は問題文の数値がすべて given 由来（whitelist・両符号）なので漏洩しない。
  narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers._step_text import fmt_expr, join_signed
from engine.packs.math.solvers.arithmetic import fmt_number

# mode -> op 列（steps の骨格）。level_sep はこの op 列の相異で作る。
_EQUATION_STEPS: dict[str, list[str]] = {
    # g1_l21 等式の性質
    "equality_add": ["subtract_constant_both_sides", "state_solution"],
    "equality_multi": ["subtract_constant_both_sides", "combine_like_terms",
                       "divide_both_sides"],
    # g1_l22 移項（+ g1_l26 過不足の解く＝同構造を別 signature で流用）
    "transpose_constant": ["transpose_constant", "state_solution"],
    "transpose_both": ["transpose_terms", "combine_like_terms", "divide_both_sides"],
    # g1_l23 Lv2 かっこ展開 / g1_l25 利用（代金）＝かっこを外してから解く
    "expand_parens": ["expand_parentheses", "transpose_terms", "combine_like_terms",
                      "divide_both_sides"],
    "word_linear": ["expand_parentheses", "transpose_terms", "combine_like_terms",
                    "divide_both_sides"],
    # g1_l27 Lv2 速さ（分数係数）＝分母を払ってから解く
    # 分母をはらう手は sympy が展開・整理まで行うので、その直後に「かっこを外す」
    # 「同類項をまとめる」を置くと**同じ式が2回出る**。手の数が seed で変わると
    # G-FP（同じ signature の fingerprint が一定であること）が落ちるので、
    # 飛ばすのではなく**最初から置かない**。
    "clear_denominators_simple": ["clear_denominators", "divide_both_sides"],
    # g1_l23 Lv3 かっこ＋分数＝分母を払い、かっこを外して移項してから解く
    "clear_denominators_two": ["clear_denominators", "transpose_terms",
                               "combine_like_terms", "divide_both_sides"],
    # g1_l24 Lv1 比例式＝たすきがけ（外項の積＝内項の積）1手
    "cross_multiply": ["cross_multiply", "solve_proportion"],
    # g1_l24 Lv2 比例式（文字を含む項）＝たすきがけ後にかっこを外して移項して解く
    "cross_multiply_expand": ["cross_multiply", "expand_parentheses", "transpose_terms",
                              "combine_like_terms", "divide_both_sides"],
    # g3_l54.find_value Lv3（C10 三平方 横展開）＝ x 軸上の等距離点。「PA²=PB²」の
    # 両辺の (x-定数)² を展開すると x² が消えて一次方程式になるので、この汎用ソルバに
    # そのまま渡せる（既存 op 列を再利用）。呼び出し側の recipe
    # （math.pythagorean_find_value）は答えの値だけを取り、steps は座標平面の語彙で
    # 組み直すので、ここの op 列は解説文には出ない（mode を受理させるための登録）。
    "pythagorean_equidistant_point_x_axis": ["expand_and_transpose", "solve"],
}

# **ここはヒントに出る文**（`t1_template._build_hints` は narration しか見ない）。
# 数字を書けないので操作を名指しできず、「たすかひくか」のようにぼかす形が残る。
# **解説に出る文は `_apply_step` / `_final_detail` が組む `detail`** で、そちらは
# 実際の値で名指しする（「両辺から 5 をひく」）。ヒントで先出しにならないのは
# detail が解説にしか流れないため（`Step` の docstring・鉄則⑦）。
_OP_NARRATION: dict[str, str] = {
    # 左辺は `x` とは限らない（`7x - 60 = 45` なら `7x` が残る）ので「x の項」と書く。
    "subtract_constant_both_sides": "左辺を x の項だけにするために、両辺に同じ数をたすかひくかする。",
    "state_solution": "両辺を計算して、解を求める。",
    "divide_both_sides": "等式の性質を使い、両辺を x の係数でわる。",
    "transpose_constant": "数の項を、符号を変えて反対の辺に移項する。",
    "transpose_terms": "文字の項を左辺に、数の項を右辺に、符号を変えて移項する。",
    "combine_like_terms": "両辺の同類項をそれぞれまとめて、ax = b の形にする。",
    "expand_parentheses": "分配法則を使って、かっこを外す。",
    "transpose_and_solve": "文字の項を左辺に、数の項を右辺に移項し、両辺を整理して解く。",
    "clear_denominators": "分母の最小公倍数を両辺にかけて、分母をはらう。",
    "combine_and_solve": "同類項をまとめ、x の係数で両辺をわって解を求める。",
    "expand_and_transpose": "分配法則でかっこを外し、文字の項を左辺・数の項を右辺に移項する。",
    "solve": "同類項をまとめ、x の係数で両辺をわって解を求める。",
    # 「たすきがけ」は因数分解（ax² + bx + c）の用語なので、比例式では使わない
    # （同じ語を別の操作に当てると、生徒がどちらの手続きか取り違える）。
    "cross_multiply": "比例式の性質を使い、外項の積と内項の積が等しい式をつくる。",
    "solve_proportion": "x の係数で両辺をわって、x の値を求める。",
}

# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**式そのもの**（面③）。以前は「分母をはらう」のような
# 指示の言い直しが入っていた。`narration` は触らない（ヒントは narration しか見ない）。
# ---------------------------------------------------------------------------
def _denominator_lcm(*exprs: sympy.Expr) -> int:
    """式に出てくる分母の最小公倍数（分母が無ければ 1）。"""
    lcm = 1
    for e in exprs:
        for term in sympy.expand(e).as_ordered_terms():
            lcm = sympy.ilcm(lcm, int(sympy.denom(sympy.together(term))))
    return lcm


def _signed(v: sympy.Expr) -> str:
    """項を符号つきで書く（`+6`・`-4x`）。移項する項を名指しするときに使う。"""
    s = fmt_expr(v)
    return s if s.startswith("-") else f"+{s}"


def _apply_step(
    op: str, lhs: sympy.Expr, rhs: sympy.Expr, equation_str: str
) -> tuple[str, str, sympy.Expr, sympy.Expr]:
    """1手ぶんの (括弧の中身, 指示文の detail, 直したあとの左辺, 右辺)。

    **手をつないで持ち回る**。前の手の結果でなく元の式から毎回組むと、
    分母をはらった次の手が分数のままの式を見せてしまう（実際そうなっていた）。

    detail は**その手で実際にやった操作を、実際の値で名指しした1文**（`Step` の
    docstring）。何をしたかを決めているのはこの関数なので、言うのもここでやる。
    `""` を返した手は従来どおり `_OP_NARRATION` が解説に出る。
    """
    x = sympy.Symbol("x")
    if op == "subtract_constant_both_sides":
        # **等式の性質を使う手は、両辺に同じ操作をした式をそのまま見せる**
        # （`x + 5 - 5 = -2 - 5`）。移項の形（`x = -2 - 5`）を見せていたので、
        # g1_l21（等式の性質）と g1_l22（移項）の解説が同じ式になっていて、
        # **単元が教えようとしている操作が解説に出ていなかった**。
        # 実物（佐賀県教委の学習プリント）もここは両辺を書く。
        const = lhs.subs(x, 0)
        sign = "-" if const > 0 else "+"
        a = fmt_expr(abs(const))
        disp = f"{fmt_expr(lhs)} {sign} {a} = {fmt_expr(rhs)} {sign} {a}"
        # **どちらをしたのかを言う。** 「たすかひくか」ではその問題で何をしたのかが
        # 読み手に分からない（実物は「両辺から ５ をひいて」と名指しする）。
        did = f"両辺から {a} をひく" if const > 0 else f"両辺に {a} をたす"
        detail = f"左辺を x の項だけにするために、{did}。"
        return disp, detail, sympy.expand(lhs - const), sympy.expand(rhs - const)
    if op == "transpose_constant":
        # 数の項を移した形（`x = 18 - 6`）。**計算はしない**——次の手の仕事なので。
        const = lhs.subs(x, 0)
        sign = "-" if const > 0 else "+"
        disp = (
            f"{fmt_expr(sympy.expand(lhs - const))} = "
            f"{fmt_expr(rhs)} {sign} {fmt_expr(abs(const))}"
        )
        detail = f"左辺の {_signed(const)} を、符号を変えて右辺に移項する。"
        return disp, detail, sympy.expand(lhs - const), sympy.expand(rhs - const)
    if op == "transpose_terms":
        # 文字は左辺・数は右辺（`2x - 4x = 11 - 9`）。
        lx, rx = lhs - lhs.subs(x, 0), rhs - rhs.subs(x, 0)
        lc, rc = lhs.subs(x, 0), rhs.subs(x, 0)
        # **0 の項は書かない。** 右辺に文字が無いと `7x + 0 = 54 + 2` になっていた。
        left = [v for v in (lx, -rx) if v != 0] or [sympy.Integer(0)]
        right = [v for v in (rc, -lc) if v != 0] or [sympy.Integer(0)]
        disp = f"{join_signed(left)} = {join_signed(right)}"
        # **動かした項だけを名指しする。** 動いていない項まで並べると、
        # 何が移項されたのかがかえって読めない。
        moved = []
        if rx != 0:
            moved.append(f"右辺の {_signed(rx)} を左辺に")
        if lc != 0:
            moved.append(f"左辺の {_signed(lc)} を右辺に")
        detail = f"{'、'.join(moved)}、符号を変えて移項する。" if moved else ""
        return disp, detail, sympy.expand(lx - rx), sympy.expand(rc - lc)
    if op == "combine_like_terms":
        # **「整理」と「わる」を分ける。** 実物（佐賀県教委の学習プリント）は
        #   2x + 3 = 9  →  2x = 9 - 3  →  2x = 6  →  x = 3
        # と1手ずつ見せる。ここを1手にまとめていたので `2x - 4x = 11 - 9` から
        # いきなり `x = -1` に飛んでいた（`-2x = 2` が抜けていた）。
        new_l, new_r = sympy.expand(lhs), sympy.expand(rhs)
        return f"{fmt_expr(new_l)} = {fmt_expr(new_r)}", "", new_l, new_r
    if op == "expand_parentheses":
        new_l, new_r = sympy.expand(lhs), sympy.expand(rhs)
        return f"{fmt_expr(new_l)} = {fmt_expr(new_r)}", "", new_l, new_r
    if op == "clear_denominators":
        m = _denominator_lcm(lhs, rhs)
        new_l, new_r = sympy.expand(m * lhs), sympy.expand(m * rhs)
        # **かける数を名指しする。** 実物は必ず「両辺に 6 をかけて」と数を書く。
        detail = f"分母の最小公倍数 {m} を両辺にかけて、分母をはらう。"
        return f"{fmt_expr(new_l)} = {fmt_expr(new_r)}", detail, new_l, new_r
    if op == "expand_and_transpose":
        moved = sympy.expand(lhs - rhs)
        coeff = moved.coeff(x, 1) * x
        const = moved.subs(x, 0)
        return f"{fmt_expr(coeff)} = {fmt_expr(-const)}", "", coeff, -const
    if op == "cross_multiply":
        # 比例式の外項の積＝内項の積。**かけ算をした形のまま**見せる
        # （`3(x - 1) = 9 × 1`）——展開は次の手の仕事。
        lhs_s, rhs_s = equation_str.split("=")

        def shown(part: str) -> str:
            # **× を落とさない**。落とすと `3 × 21` が `321` になる。
            text = str(sympy.sstr(sympy.sympify(part, evaluate=False)))
            return text.replace("*", " × ")

        return f"{shown(lhs_s)} = {shown(rhs_s)}", "", lhs, rhs
    raise ValueError(f"途中の表示を組めない op: {op!r}")


def _final_detail(op: str, lhs: sympy.Expr, rhs: sympy.Expr) -> str:
    """**最後の手**の指示文を、実際の値で名指しする。

    最後の手は `_apply_step` を通らない（括弧に答えを入れて打ち切るため）ので、
    ここで持ち回ってきた左辺・右辺から係数を読む。実物は「両辺を 8 でわって」と
    わる数を必ず書く。
    """
    coeff = sympy.expand(lhs).coeff(sympy.Symbol("x"), 1)
    if coeff in (0, 1):
        # 係数が 1 なら「わる」手がそもそも要らない。名指しできることが無い。
        return ""
    a = fmt_expr(coeff)
    if op == "divide_both_sides":
        return f"等式の性質を使い、両辺を x の係数 {a} でわる。"
    if op == "solve_proportion":
        return f"x の係数 {a} で両辺をわって、x の値を求める。"
    if op in ("solve", "combine_and_solve"):
        return f"同類項をまとめ、x の係数 {a} で両辺をわって解を求める。"
    return ""


def _equation_step_displays(
    ops: list[str], equation_str: str, final: str
) -> list[tuple[str, str, str]]:
    """各手の (op, 括弧の中身, 指示文の detail)。最後の手の括弧は答え。"""
    lhs_s, rhs_s = equation_str.split("=")
    lhs = sympy.sympify(lhs_s, rational=True)
    rhs = sympy.sympify(rhs_s, rational=True)
    out: list[tuple[str, str, str]] = []
    for i, op in enumerate(ops):
        if i == len(ops) - 1:
            out.append((op, final, _final_detail(op, lhs, rhs)))
            break
        disp, detail, lhs, rhs = _apply_step(op, lhs, rhs, equation_str)
        out.append((op, disp, detail))
    return out


@register_solver("math.solve_linear_equation")
def solve_linear_equation(equation_str: str, mode: object) -> Solution:
    """1変数の一次方程式を解いて解 x=定数を求める（g1 一次方程式 calculation）。

    equation_str（"lhs=rhs"）と mode だけから sympy.solve で x について解く（double-solve）。
    答えは解 x=定数（Integer/Rational）の SymbolicAnswer（display="x = ..."）。mode ごとに
    steps の op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _EQUATION_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    lhs_s, rhs_s = equation_str.split("=")
    x = sympy.Symbol("x")
    eq = sympy.Eq(sympy.sympify(lhs_s, rational=True), sympy.sympify(rhs_s, rational=True))
    sols = sympy.solve(eq, x)
    if len(sols) != 1:
        raise ValueError(f"一意に解けない方程式: {equation_str!r} -> {sols!r}")
    value = sympy.Rational(sols[0])
    r_srepr = sympy.srepr(value)
    r_disp = f"x = {fmt_number(value)}"

    shown = _equation_step_displays(_EQUATION_STEPS[mode_s], equation_str, r_disp)
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=display,
            narration=_OP_NARRATION[op],
            detail=detail,
        )
        for op, display, detail in shown
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l27.word_problem Lv4: 往復の道のりと平均の速さ（一次方程式の融合）
#
# 【台帳 example から離れた点と、その理由】台帳の Lv4 は「行きと帰りで速さの異なる
# 移動を自分で設定し、往復にかかった時間と平均の速さの関係が一次方程式で表せるような
# **問題をつくり**、その問題を解け」＝作問そのものを問う設問で、M0 の答えの型
# （SymbolicAnswer / ChoiceAnswer / GraphAnswer）のどれにも落ちない。
# そこで「設定を自分で置く」部分は engine が固定し、**誘導なしで2つの量を自分で順に
# 出す**形に落とす（箱ひげ図の記述セルで「説明せよ」の結論だけを答えさせたのと同じ手）。
#   往復の時間 T から片道の道のり d を一次方程式 d/a + d/b = T で求め、
#   さらに往復の平均の速さ 2d/T を求める。
# desc の「往復にかかった時間と平均の速さの関係が一次方程式で表せる」はこの形で満たす。
#
# 【平均の速さを問うだけにしない理由】平均の速さは 2ab/(a+b)（調和平均）で
# **道のりに依らない**。平均の速さだけを問うと、一次方程式を立てずに速さ2つだけで
# 答えが出てしまう（ゲートが素通りする退化）。道のりと組で問うことで、
# 一次方程式を解く段が必ず要る形になる。
# ---------------------------------------------------------------------------
_ROUND_TRIP_AVG_OPS = [
    "set_up_round_trip_equation",
    "clear_denominators",
    "solve_for_one_way_distance",
    "compute_round_trip_distance",
    "compute_average_speed",
]

_ROUND_TRIP_AVG_NARRATION: dict[str, str] = {
    "set_up_round_trip_equation": "片道の道のりを x とおき、行きにかかる時間と帰りにかかる時間の和が往復の時間に等しいという方程式をつくる。",
    "clear_denominators": "両辺に分母の最小公倍数をかけて、分数のない形に直す。",
    "solve_for_one_way_distance": "方程式を解いて片道の道のりを求める。",
    "compute_round_trip_distance": "片道の道のりを二倍して、往復の道のり全体を求める。",
    "compute_average_speed": "往復の道のりを往復にかかった時間でわって、往復の平均の速さを求める。",
}

def _round_trip_display(op: str, a, b, t, distance) -> str:
    """往復の手の括弧（この手で得た式・値）。指示の言い直しは置かない（面③）。"""
    if op == "set_up_round_trip_equation":
        return f"x/{fmt_number(a)} + x/{fmt_number(b)} = {fmt_number(t)}"
    if op == "clear_denominators":
        m = sympy.ilcm(int(a), int(b))
        return f"{fmt_number(m / a)}x + {fmt_number(m / b)}x = {fmt_number(m * t)}"
    if op == "solve_for_one_way_distance":
        return f"x = {fmt_number(distance)}"
    if op == "compute_round_trip_distance":
        return f"{fmt_number(2 * distance)}km"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


@register_solver("math.solve_round_trip_average_speed")
def solve_round_trip_average_speed(
    speed_go: object, speed_back: object, total_time: object
) -> Solution:
    """往復の片道の道のりと平均の速さを求める（g1_l27.word_problem Lv4）。

    問題パラメータ（行きの速さ・帰りの速さ・往復の時間）だけから導く。
    x/a + x/b = T を既存ソルバ `math.solve_linear_equation` で解いて片道の道のり x を
    得たうえで、往復の平均の速さ 2x/T を合成する（方程式を解く段は再実装しない）。
    """
    a = sympy.Rational(str(speed_go))
    b = sympy.Rational(str(speed_back))
    t = sympy.Rational(str(total_time))
    if a <= 0 or b <= 0 or t <= 0:
        raise ValueError("速さ・時間は正であること")
    if a == b:
        raise ValueError("行きと帰りの速さが同じだと往復が2区間に分かれない")

    inner = solve_linear_equation(f"x/{a} + x/{b} = {t}", "clear_denominators_simple")
    assert isinstance(inner.answer, SymbolicAnswer)
    distance = sympy.nsimplify(sympy.sympify(inner.answer.srepr))
    average = sympy.nsimplify(2 * distance / t)
    # 恒真: 平均の速さは調和平均 2ab/(a+b) に一致する（道のりに依らない）。
    if not (average - 2 * a * b / (a + b)).equals(0):
        raise ValueError(f"平均の速さが調和平均と一致しない: {average}")

    pair = sympy.Tuple(distance, average)
    srepr = sympy.srepr(pair)
    disp = f"片道の道のりは{fmt_number(distance)}km、往復の平均の速さは時速{fmt_number(average)}km"
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(_ROUND_TRIP_AVG_OPS) - 1 else "",
            result_display=disp if i == len(_ROUND_TRIP_AVG_OPS) - 1
            else _round_trip_display(op, a, b, t, distance),
            narration=_ROUND_TRIP_AVG_NARRATION[op],
        )
        for i, op in enumerate(_ROUND_TRIP_AVG_OPS)
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


__all__ = ["solve_linear_equation", "solve_round_trip_average_speed"]
