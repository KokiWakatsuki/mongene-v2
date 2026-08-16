"""2次方程式まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 eq_str と mode）から答えと steps を導く。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C3（g3 数と式・2次方程式）クラスタの求解セル群（平方根の考え・平方完成・解の公式・
因数分解・解法選択）を1つの汎用ソルバ `math.solve_quadratic(eq_str, mode)` に集約する。
eq_str は "左辺=右辺" 形式で "=" で分割して解く。答えは解を昇順に並べた Tuple の
SymbolicAnswer（解が2つ）。根号は √ 表示、分数＋根号は together で単一分数にまとめる
（例 (-5+√17)/4）。mode ごとに steps の op 列を変える＝level_sep。

代入して左辺の値を求める mode（evaluate_quadratic）だけは答えが単一の値（SymbolicAnswer）。
"""
from __future__ import annotations

import re

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers._step_text import fmt_expr

_X = sympy.Symbol("x")
_SQRT_RE = re.compile(r"sqrt\((\d+)\)")


def _fmt_scalar(v: sympy.Expr) -> str:
    """1つの解／値の表示（sqrt(n)→√n・分数＋根号は together で単一分数・`*` 除去）。"""
    s = _SQRT_RE.sub(r"√\1", str(sympy.sstr(sympy.together(v))))
    return s.replace("*", "")


def _parse_eq(eq_str: str) -> sympy.Expr:
    """"左辺=右辺" を (左辺)-(右辺) の式に直す（=0 の左辺）。"""
    lhs_s, rhs_s = eq_str.split("=", 1)
    return sympy.sympify(lhs_s) - sympy.sympify(rhs_s)


def _sorted_roots(eq_str: str) -> list[sympy.Expr]:
    """2次方程式の解を実部→虚部の昇順で並べて返す（決定論）。"""
    expr = _parse_eq(eq_str)
    roots = sympy.solve(sympy.Eq(expr, 0), _X)
    return sorted(
        roots,
        key=lambda r: (float(sympy.re(r.evalf())), float(sympy.im(r.evalf()))),
    )


# mode -> op 列（level_sep はこの op 列の相異で作る）。narration に数字を書かない。
_QUAD_STEPS: dict[str, list[str]] = {
    # g3_l24 代入して左辺の値を求める（＝解かどうかの確認）
    "evaluate_quadratic": ["substitute_value", "evaluate_left_side"],
    # g3_l25 平方根の考え方
    "solve_square_form": ["take_square_root", "solve_two_cases"],
    # **平方完成は3手に割る。** 1手で `x² + 12x - 2 = 0` から `(x + 6)² = 38` へ
    # 飛んでいた（実物は「定数項を移項」「両辺に 36 を加える」「平方の形にまとめる」を
    # 1行ずつ見せる）。この mode の与式は必ず x² の係数が 1・x の係数が偶数
    # （recipe が `x**2+(2m)*x+(q)=0` を組む）なので、割った各手が必ず整数で書ける。
    "solve_complete_square": ["move_constant", "add_square_both_sides", "complete_the_square",
                              "take_square_root", "solve_two_cases"],
    # g3_l26 解の公式
    # **代入した式を見せる手を挟む。** 係数を読み取った次がいきなり答えで、
    # 公式のどこに何を入れたのかが解説に出ていなかった。
    "solve_formula": ["identify_coefficients", "substitute_into_formula",
                      "apply_quadratic_formula"],
    "solve_formula_hard": ["identify_coefficients", "substitute_into_formula",
                           "compute_discriminant", "apply_quadratic_formula"],
    # g3_l27 因数分解
    "solve_factoring": ["factor_left_side", "apply_zero_product"],
    "solve_factoring_common": ["factor_out_common", "apply_zero_product"],
    # g3_l28 解法の選択
    "solve_rearrange": ["expand_and_rearrange", "factor_left_side", "apply_zero_product"],
    "solve_choose": ["factor_out_common_binomial", "apply_zero_product"],
    # g3_l29/l30 立式した2次方程式の求解（x(x+c)=k 型）
    "solve_product_form": ["expand_and_rearrange", "factor_left_side", "apply_zero_product"],
    # g3_l30.find_value 図形条件から立式し、正の解のみを採用する
    "solve_product_form_positive_root": [
        "expand_and_rearrange", "factor_left_side", "apply_zero_product", "select_positive_root",
    ],
}

_QUAD_OP_NARRATION: dict[str, str] = {
    # narration の数字は原則書かない（G-Q5t 偽陽性の元＝§5-#9。特に "b²-4ac" の 4 が
    # 答えの根号係数トークンと衝突した実バグあり→語で述べる）。ただし "0" は given の
    # "=0" で常に whitelist されるため自然に用いてよい。
    "substitute_value": "指定された値を左辺の文字に代入する。",
    "evaluate_left_side": "左辺を計算して、その値を求める（値が 0 なら等式が成り立つ）。",
    "take_square_root": "平方根の考え方で、両辺の平方根をとる。",
    "solve_two_cases": "正の場合と負の場合に分けて x を求める。",
    "move_constant": "定数項を、符号を変えて右辺に移項する。",
    "add_square_both_sides": "左辺を平方の形にするために、x の係数の半分を平方した数を両辺に加える。",
    "complete_the_square": "左辺を、かっこの平方の形にまとめる。",
    "identify_coefficients": "与式を整理して、それぞれの項の係数 a・b・c を読み取る。",
    "substitute_into_formula": "読み取った a・b・c を、解の公式にそのまま代入する。",
    "apply_quadratic_formula": "根号の中を計算し、約分できるところを約分して x を求める。",
    "compute_discriminant": "根号の中の値（判別式）を計算する。",
    "factor_left_side": "左辺を因数分解する。",
    "apply_zero_product": "積が 0 になるのは各因数が 0 のときだから、それぞれを 0 とおいて x を求める。",
    "factor_out_common": "左辺の共通因数をくくり出す。",
    "expand_and_rearrange": "かっこを展開し、右辺を左辺に移項して、=0 の形に整理する。",
    # 移項するのは「項」であって「両辺」ではない（「両辺を移項」は日本語として誤り）。
    "factor_out_common_binomial": "右辺を左辺に移項し、共通なかっこをくくり出す。",
    "select_positive_root": "求めるものは正の数だから、2つの解のうち条件に合う正の解を選ぶ。",
}

# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**式そのもの**（面③）。以前は「左辺を因数分解する」のような
# 指示の言い直しが入っていて、`apply_zero_product` に至っては括弧が空だった。
# `narration` は触らない（ヒントは narration しか見ない）。
# ---------------------------------------------------------------------------
def _completed_square(expr: sympy.Expr) -> tuple[sympy.Expr, sympy.Expr]:
    """`x² + bx + c`（=0 の左辺）を `(x + p)² = q` の形にした (x + p, q)。"""
    poly = sympy.Poly(sympy.expand(expr), _X)
    a, b, c = (poly.coeff_monomial(_X**2), poly.coeff_monomial(_X), poly.coeff_monomial(1))
    p = sympy.Rational(b, 2 * a)
    return _X + p, sympy.simplify(p**2 - sympy.Rational(c, a))


def _zero_product_lines(expr: sympy.Expr) -> str:
    """`(x - 2)(x - 3)` を `x - 2 = 0、x - 3 = 0` にする。"""
    factored = sympy.factor(sympy.expand(expr))
    factors = factored.as_ordered_factors() if factored.is_Mul else [factored]
    parts = [f"{fmt_expr(f)} = 0" for f in factors if _X in f.free_symbols]
    return "、".join(parts)


def _abc(expr: sympy.Expr) -> tuple[sympy.Expr, sympy.Expr, sympy.Expr]:
    """`=0` の左辺から係数 (a, b, c) を取る。"""
    poly = sympy.Poly(sympy.expand(expr), _X)
    return (poly.coeff_monomial(_X**2), poly.coeff_monomial(_X), poly.coeff_monomial(1))


def _paren_negative(v: sympy.Expr) -> str:
    """負の数はかっこで囲む（`4 × (-7)` の `(-7)`）。"""
    return f"({_fmt_scalar(v)})" if v < 0 else _fmt_scalar(v)


def _quad_step_detail(op: str, eq_str: str) -> str:
    """解説にだけ出る、**実際の値で操作を名指しした**指示文（`Step` の docstring）。

    narration は hints に流れるので数字を書けない。ここは解説専用なので書ける。
    """
    expr = _parse_eq(eq_str)
    a, b, c = _abc(expr)
    if op == "move_constant":
        return f"定数項 {_fmt_scalar(c)} を、符号を変えて右辺に移項する。"
    if op == "add_square_both_sides":
        half = sympy.Rational(b, 2 * a)
        return (
            f"左辺を平方の形にするために、x の係数 {_fmt_scalar(b)} の半分 "
            f"{_fmt_scalar(half)} を平方した {_fmt_scalar(half**2)} を両辺に加える。"
        )
    if op == "complete_the_square":
        base, _q = _completed_square(expr)
        return f"左辺を ({fmt_expr(base)}) の平方の形にまとめる。"
    if op == "substitute_into_formula":
        return (
            f"解の公式に a = {_fmt_scalar(a)}、b = {_fmt_scalar(b)}、"
            f"c = {_fmt_scalar(c)} を代入する。"
        )
    return ""


def _quad_step_display(op: str, eq_str: str, value: object) -> str:
    """1手ぶんの括弧の中身（この手で得た式）。"""
    expr = _parse_eq(eq_str)
    if op == "substitute_value":
        # 代入したままの式（sympy に渡すと計算されるので、記号に置きかえて表示だけ作る）。
        val = sympy.nsimplify(sympy.sympify(str(value)))
        shown = f"({_fmt_scalar(val)})"
        return fmt_expr(sympy.sympify(eq_str.split("=", 1)[0]).subs(_X, sympy.Symbol(shown)))
    if op in ("factor_left_side", "factor_out_common", "factor_out_common_binomial"):
        return f"{fmt_expr(sympy.factor(sympy.expand(expr)))} = 0"
    if op == "expand_and_rearrange":
        return f"{fmt_expr(sympy.expand(expr))} = 0"
    if op == "apply_zero_product":
        return _zero_product_lines(expr)
    if op == "identify_coefficients":
        a, b, c = _abc(expr)
        return f"a = {_fmt_scalar(a)}、b = {_fmt_scalar(b)}、c = {_fmt_scalar(c)}"
    if op == "substitute_into_formula":
        # 公式に値を入れたままの形。**計算はしない**——次の手の仕事なので。
        a, b, c = _abc(expr)
        return (
            f"x = (-{_paren_negative(b)} ± √({_paren_negative(b)}² "
            f"- 4 × {_paren_negative(a)} × {_paren_negative(c)}))"
            f" / (2 × {_paren_negative(a)})"
        )
    if op == "compute_discriminant":
        a, b, c = _abc(expr)
        return (
            f"{_paren_negative(b)}² - 4 × {_paren_negative(a)} × {_paren_negative(c)}"
            f" = {_fmt_scalar(b**2 - 4 * a * c)}"
        )
    if op == "move_constant":
        a, b, c = _abc(expr)
        return f"{fmt_expr(a * _X**2 + b * _X)} = {_fmt_scalar(-c)}"
    if op == "add_square_both_sides":
        a, b, c = _abc(expr)
        half_sq = sympy.Rational(b, 2 * a) ** 2
        return (
            f"{fmt_expr(a * _X**2 + b * _X)} + {_fmt_scalar(half_sq)}"
            f" = {_fmt_scalar(-c)} + {_fmt_scalar(half_sq)}"
        )
    if op == "complete_the_square":
        base, q = _completed_square(expr)
        return f"({fmt_expr(base)})² = {_fmt_scalar(q)}"
    if op == "take_square_root":
        base, q = _completed_square(expr)
        return f"{fmt_expr(base)} = ±{_fmt_scalar(sympy.sqrt(q))}"
    raise ValueError(f"途中の表示を組めない op: {op!r}")


_EVALUATE_MODES = {"evaluate_quadratic"}
_POSITIVE_ROOT_MODES = {"solve_product_form_positive_root"}


@register_solver("math.solve_quadratic")
def solve_quadratic(eq_str: str, mode: object, value: object = None) -> Solution:
    """2次方程式を解く／左辺に値を代入して評価する（C3 g3_l24〜l28.calculation）。

    与式の文字列 eq_str と mode だけから答えを導く（recipe の構成内訳は見ない・double-solve）。
    solve 系: 答えは解を昇順に並べた Tuple の SymbolicAnswer。evaluate 系: value を代入した
    左辺の値の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    """
    mode_s = str(mode)
    if mode_s not in _QUAD_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    ops = _QUAD_STEPS[mode_s]

    if mode_s in _EVALUATE_MODES:
        expr = _parse_eq(eq_str)  # 左辺（右辺は0）
        val = sympy.nsimplify(sympy.sympify(str(value)))
        result = sympy.simplify(expr.subs(_X, val))
        disp = _fmt_scalar(result)
        srepr = sympy.srepr(result)
    elif mode_s in _POSITIVE_ROOT_MODES:
        roots = _sorted_roots(eq_str)
        positive = [r for r in roots if r.is_real and r > 0]
        assert len(positive) == 1, f"正の解がちょうど1つでない: {eq_str} -> {roots}"
        disp = _fmt_scalar(positive[0])
        srepr = sympy.srepr(positive[0])
    else:
        roots = _sorted_roots(eq_str)
        answer_tuple = sympy.Tuple(*roots)
        srepr = sympy.srepr(answer_tuple)
        disp = ", ".join(f"x = {_fmt_scalar(r)}" for r in roots)

    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1 else _quad_step_display(op, eq_str, value),
            narration=_QUAD_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = ["solve_quadratic"]
