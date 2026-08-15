"""平方根（根号）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 expr_str と mode）から答えと steps を導く。
純粋・決定論・SymPy 恒真であること。乱数は引かない。

C3（g3 数と式・平方根）クラスタの簡約セル群（乗除・a√b 変形・有理化・加減・分配/共役）を
1つの汎用ソルバ `math.simplify_radical(expr_str, mode)` に集約する。sympy で根号式を
正準形へ簡約し、mode ごとに steps の op 列を変える（＝level_sep）。答えは根号を含む定数式の
SymbolicAnswer。表示は `sqrt(n)` を `√n` に直す（教材表記）。

有理化（分母に根号）系の mode は sympy.radsimp（分母の有理化を確実に行う）、それ以外は
sympy.simplify（乗除・簡単化・加減・展開の正準化）で分ける。
"""
from __future__ import annotations

import re
from typing import cast

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers._step_text import top_level_parts, wrapped_in_parens

_SQRT_RE = re.compile(r"sqrt\((\d+)\)")
_TO_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def fmt_radical(expr: sympy.Expr) -> str:
    """根号式の表示形（`sqrt(n)`→`√n`・`*` 除去）。例: 3*sqrt(2)->"3√2" / sqrt(2)+sqrt(5)->"√2 + √5"。"""
    s = _SQRT_RE.sub(r"√\1", str(sympy.sstr(expr)))
    return s.replace("*", "")


def fmt_radical_source(expr_str: str) -> str:
    """**与式の文字列**の表示形（簡約しない）。例: "sqrt(44)"->"√44" / "3*sqrt(2)"->"3√2"。

    `fmt_radical` は sympy の式を受けるので簡約後の形になる。問題文に出ている形を
    そのまま答えに使いたいときはこちらを使う。

    **累乗は上付きにしてから `*` を落とす。** 先に `*` を落とすと `x**2` が `x2` になる
    （代入した式の解説が `(√59+(-6))2` と出ていた）。
    """
    text = re.sub(r"\*\*(\d+)", lambda m: m.group(1).translate(_TO_SUPERSCRIPT), expr_str)
    return _SQRT_RE.sub(r"√\1", text).replace("*", "")


# mode -> op 列（level_sep はこの op 列の相異で作る）。narration に数字を書かない。
_RADICAL_STEPS: dict[str, list[str]] = {
    # g3_l14 根号と平方の相互変換
    "square_of_root": ["square_the_root"],
    # g3_l17 平方根の乗法・除法
    "root_mult": ["multiply_under_one_root", "simplify_root"],
    "root_mult_div": ["rewrite_division_as_multiplication", "combine_roots", "simplify_result"],
    # g3_l18 根号の中を簡単にする（a√b）
    "simplify_root": ["factor_out_square", "take_root_outside"],
    "simplify_root_large": ["factor_into_squares", "take_roots_outside", "simplify_result"],
    # g3_l19 分母の有理化（単項）
    "rationalize_mono": ["multiply_by_same_root", "simplify_fraction"],
    # g3_l20 平方根の加法・減法
    "add_roots": ["combine_like_radicals"],
    "add_roots_simplify": ["simplify_each_root", "combine_like_radicals"],
    # g3_l21 いろいろな計算（分配・共役有理化）
    "expand_roots": ["expand_with_distribution", "combine_like_terms_and_radicals"],
    "rationalize_conjugate": ["multiply_by_conjugate", "simplify_fraction"],
    # g3_l23 平方根の利用（乗除と加減が混在する立式後の計算）
    "calculate_and_combine": ["multiply_and_simplify_roots", "combine_like_radicals_final"],
    # g3_l23.find_value 面積から1辺の長さを求める（√a² の簡約と同型）
    "find_side_from_area": ["factor_out_square", "take_root_outside"],
}

_RADICAL_OP_NARRATION: dict[str, str] = {
    "square_the_root": "根号のついた数を2乗し、根号の中の数にもどす。",
    "multiply_under_one_root": "根号の積を、1つの根号の中の積にまとめる。",
    "simplify_root": "根号の中を素因数分解し、平方の因数を根号の外に出す。",
    "rewrite_division_as_multiplication": "わり算を、逆数をかけるかけ算に直す。",
    "combine_roots": "係数どうし・根号の中どうしをそれぞれまとめる。",
    "simplify_result": "根号の中をできるだけ簡単な形に直す。",
    "factor_out_square": "根号の中を素因数分解し、平方の因数を見つける。",
    "take_root_outside": "平方の因数を根号の外に出して a√b の形にする。",
    "factor_into_squares": "根号の中の大きな数を、平方の因数と残りに分ける。",
    "take_roots_outside": "それぞれの平方の因数を根号の外に出す。",
    "multiply_by_same_root": "分母と分子に、分母と同じ根号をかける。",
    "simplify_fraction": "分母を根号のない形にし、約分して簡単にする。",
    "combine_like_radicals": "根号の中が同じ項を、同類項のようにまとめる。",
    "simplify_each_root": "それぞれの根号を a√b の形に直す。",
    "expand_with_distribution": "分配法則や乗法公式で根号を含む式を展開する。",
    "combine_like_terms_and_radicals": "数の項どうし・根号の項どうしをまとめる。",
    "multiply_by_conjugate": "分母と分子に、分母の共役な式をかける。",
    "multiply_and_simplify_roots": "根号どうしの乗除を先に計算して、1つの根号にまとめる。",
    "combine_like_radicals_final": "それぞれの根号を簡単にし、根号の中が同じ項をまとめる。",
}

# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**式そのもの**（面③）。以前は「1つの根号にまとめる」の
# ような指示の言い直しが入っていた。`narration` は触らない。
# ---------------------------------------------------------------------------
def _square_split(n: int) -> tuple[int, int]:
    """根号の中の数を（平方の因数, 残り）に分ける（`180` → `(36, 5)`）。"""
    square = 1
    rest = n
    for base, exp in sympy.factorint(n).items():
        square *= base ** (exp // 2 * 2)
        rest //= base ** (exp // 2 * 2)
    return square, rest


def _parse_factors(text: str) -> tuple[sympy.Integer, list[int]]:
    """`4*sqrt(6)*sqrt(2)` を（係数 4, 根号の中 [6, 2]）に分ける。

    **文字列から読む。** `sympy.sympify("sqrt(20)")` は `2√5` に簡約してしまうので、
    「まだ簡単にしていない形」を見せるこの手では sympy を通せない。
    """
    coeff = sympy.Integer(1)
    radicands: list[int] = []
    for _op, part in top_level_parts(text.strip(), "*"):
        token = part.strip()
        while wrapped_in_parens(token):
            token = token[1:-1].strip()
        m = _SQRT_RE.fullmatch(token)
        if m:
            radicands.append(int(m.group(1)))
        elif token:
            coeff *= sympy.Integer(token)
    return coeff, radicands


def _as_a_root_b(coeff: sympy.Integer, radicand: int) -> str:
    """`3*sqrt(180)` を `18√5` の形の文字列にする（外に出せる分を出す）。"""
    square, rest = _square_split(radicand)
    outside = coeff * sympy.Integer(square) ** sympy.Rational(1, 2)
    if rest == 1:
        return sympy.sstr(outside)
    head = "" if outside == 1 else ("-" if outside == -1 else sympy.sstr(outside))
    return f"{head}√{rest}"


def _radical_step_display(op: str, expr_str: str, expr: sympy.Expr) -> str:
    """1手ぶんの括弧の中身（この手で得た式）。"""
    if op == "multiply_under_one_root":
        # `√20 × √10` → `√200`（まだ簡単にしない）。
        coeff, radicands = _parse_factors(expr_str)
        product = 1
        for r in radicands:
            product *= r
        head = "" if coeff == 1 else sympy.sstr(coeff)
        return f"{head}√{product}"
    if op == "rewrite_division_as_multiplication":
        num, den = expr_str.rsplit("/", 1)
        coeff, radicands = _parse_factors(num)
        head = [] if coeff == 1 else [sympy.sstr(coeff)]
        shown = " × ".join([*head, *(f"√{r}" for r in radicands)])
        return f"{shown} × 1/{fmt_radical_source(den)}"
    if op == "combine_roots":
        # 係数どうし・根号の中どうしをまとめた形（`4√(6 × 2 / 3)`）。
        num, den = expr_str.rsplit("/", 1)
        coeff, radicands = _parse_factors(num)
        _dcoeff, dradicands = _parse_factors(den)
        inside = " × ".join(str(r) for r in radicands)
        if dradicands:
            inside += " / " + " × ".join(str(r) for r in dradicands)
        head = "" if coeff == 1 else sympy.sstr(coeff)
        return f"{head}√({inside})"
    if op == "multiply_and_simplify_roots":
        # 乗除を計算して1つの根号にした形（`√2025 + √80`）。a√b に直すのは次の手。
        pieces: list[str] = []
        for i, (sign, part) in enumerate(top_level_parts(expr_str, "+-")):
            coeff, radicands = _parse_factors(part)
            product = 1
            for r in radicands:
                product *= r
            head = "" if coeff == 1 else sympy.sstr(coeff)
            body = f"{head}√{product}" if radicands else sympy.sstr(coeff)
            joiner = "" if i == 0 else (" - " if sign == "-" else " + ")
            pieces.append(joiner + body)
        return "".join(pieces)
    if op == "simplify_each_root":
        # 項ごとに根号の中を計算し、a√b の形に直した並び（`6√5 - 5√5 + 3√5`）。
        pieces: list[str] = []
        for i, (sign, part) in enumerate(top_level_parts(expr_str, "+-")):
            coeff, radicands = _parse_factors(part)
            product = 1
            for r in radicands:
                product *= r
            body = _as_a_root_b(coeff, product) if radicands else sympy.sstr(coeff)
            joiner = "" if i == 0 else (" - " if sign == "-" else " + ")
            pieces.append(joiner + body)
        return "".join(pieces)
    if op == "expand_with_distribution":
        # かっこごとに展開した形（まとめる前）。
        parts = []
        for i, (sign, part) in enumerate(top_level_parts(expr_str, "+-")):
            joiner = "" if i == 0 else (" - " if sign == "-" else " + ")
            parts.append(f"{joiner}({fmt_radical(sympy.expand(sympy.sympify(part)))})")
        return "".join(parts)
    if op in ("factor_out_square", "factor_into_squares"):
        # 根号の中を「平方の因数 × 残り」に分けた形（`2 × √(4 × 35)`）。
        coeff, radicands = _parse_factors(expr_str)
        square, rest = _square_split(radicands[0])
        head = "" if coeff == 1 else f"{sympy.sstr(coeff)} × "
        return f"{head}√({square} × {rest})"
    if op == "take_roots_outside":
        # 平方の因数を外に出した形（`3 × 6√5`。かけ算は次の手）。
        coeff, radicands = _parse_factors(expr_str)
        square, rest = _square_split(radicands[0])
        outside = sympy.Integer(square) ** sympy.Rational(1, 2)
        head = "" if coeff == 1 else f"{sympy.sstr(coeff)} × "
        return f"{head}{sympy.sstr(outside)}√{rest}"
    if op == "multiply_by_same_root":
        num, den = expr_str.rsplit("/", 1)
        d = fmt_radical_source(den)
        return f"({fmt_radical_source(num)} × {d}) / ({d} × {d})"
    if op == "multiply_by_conjugate":
        num, den = expr_str.split("/", 1)
        shown_d, shown_conj = _denominator_and_conjugate(den)
        return (
            f"({fmt_radical_source(num)} × ({shown_conj})) / "
            f"(({shown_d}) × ({shown_conj}))"
        )
    raise ValueError(f"途中の表示を組めない op: {op!r}")


def _denominator_and_conjugate(den: str) -> tuple[str, str]:
    """分母とその共役を、**書かれた順のまま**文字列で組む。

    sympy に渡すと `√3 - √13` が `-√13 + √3` に並べかえられ、共役も
    `-√13 - √3` という見慣れない形になる（教科書は `√3 + √13` と書く）。
    """
    text = den.strip()
    while wrapped_in_parens(text):
        text = text[1:-1].strip()
    parts = top_level_parts(text, "+-")
    if len(parts) != 2:
        raise ValueError(f"2項でない分母の共役は組めない: {den!r}")
    (_, first), (sign, second) = parts
    shown = f"{fmt_radical_source(first)} {sign} {fmt_radical_source(second)}"
    flipped = "+" if sign == "-" else "-"
    conj = f"{fmt_radical_source(first)} {flipped} {fmt_radical_source(second)}"
    return shown, conj

# 分母の有理化を確実に行う mode（sympy.radsimp を使う）。
_RATIONALIZE_MODES = {"rationalize_mono", "rationalize_conjugate"}


def _canonicalize(expr: sympy.Expr, mode: str) -> sympy.Expr:
    """mode に応じて根号式を正準形へ簡約する。

    非有理化系は sympy.expand で正準化する（sympy は sqrt を自動で a√b に簡約するため、
    expand は乗除・簡単化・加減・展開のすべてで sympy.simplify と同一結果を与え、かつ
    約15倍高速。全 mode の代表式で expand==simplify を実測確認済み）。有理化系は分母の
    有理化を確実に行う sympy.radsimp を使う。
    """
    if mode in _RATIONALIZE_MODES:
        return sympy.radsimp(expr)
    return sympy.expand(expr)


@register_solver("math.simplify_radical")
def simplify_radical(expr_str: str, mode: object) -> Solution:
    """根号を含む式を簡約する（C3 g3_l14/l17〜l21.calculation）。

    与式の文字列だけから sympy で正準形へ簡約する（recipe の構成内訳は見ない・double-solve）。
    答えは根号を含む定数式の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _RADICAL_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    expr = sympy.sympify(expr_str)
    result = _canonicalize(expr, mode_s)
    disp = fmt_radical(result)
    srepr = sympy.srepr(result)

    ops = _RADICAL_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _radical_step_display(op, expr_str, expr),
            narration=_RADICAL_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 式の値（C3 g3_l22.calculation）— 根号を含む値を式に代入して式の値を求める。
#
# x = p+√a（p は 0 でない整数、a は非平方の squarefree）を expr_str（x の式）に
# 代入し、sympy.expand で厳密評価する（double-solve）。recipe 側で 1次の係数を
# -2p に固定して構成する（x²-2px = (p+√a)²-2p(p+√a) = a-p² と根号が恒等的に
# 消える・a が非平方なので a-p²=0 に退化しない＝構成のみで退化ガードが効く）。
# 答えは根号を含まない定数（Integer）の SymbolicAnswer。mode ごとに steps の
# op 列を変える＝level_sep。narration には数字を書かない。
# ---------------------------------------------------------------------------
_SUBSTITUTE_ROOT_STEPS: dict[str, list[str]] = {
    # g3_l22 Lv2 √を含む値を代入し展開して式の値を求める
    "substitute_root_quadratic": ["substitute_root_value", "expand_and_simplify"],
    # g3_l22 Lv3 共役な√を含む値の組(x,y)を対称式に代入し展開して式の値を求める
    "substitute_conjugate_pair_sum_squares": ["substitute_conjugate_pair_values", "expand_and_simplify"],
}

_SUBSTITUTE_ROOT_NARRATION: dict[str, str] = {
    "substitute_root_value": "式の文字に、根号を含む値をそのままあてはめる。",
    "substitute_conjugate_pair_values": "式の2つの文字に、根号を含む共役な値の組をそれぞれあてはめる。",
    "expand_and_simplify": "かっこを展開し、根号を含む項どうしを整理して式の値を求める。",
}

def _substitute_root_phrase(expr_str: str, value_str: str, value_str_y: str | None) -> dict[str, str]:
    """代入した式そのもの（面③）。`x²-2·5·x` に `√7+5` を入れた形を見せる。"""
    shown = fmt_radical_source(value_str)
    body = fmt_radical_source(expr_str).replace("x", f"({shown})")
    if value_str_y:
        body = fmt_radical_source(expr_str)
        body = body.replace("x", f"({shown})").replace(
            "y", f"({fmt_radical_source(value_str_y)})"
        )
    return {
        "substitute_root_value": body,
        "substitute_conjugate_pair_values": body,
    }


@register_solver("math.evaluate_radical_substitution")
def evaluate_radical_substitution(
    expr_str: str, value_str: str, mode: object, value_str_y: str | None = None
) -> Solution:
    """根号を含む値を式に代入して式の値を求める（C3 g3_l22.calculation）。

    expr_str（x の式、Lv3 は x,y の式）と value_str（"sqrt(a)+p" 形の x への代入値）
    だけから sympy.expand で代入・厳密評価する（recipe の構成内訳は見ない・double-solve）。
    value_str_y が与えられれば（Lv3）y にもその値を代入する（2変数の対称式）。
    答えは根号を含まない定数（Integer）の SymbolicAnswer。mode ごとに steps の
    op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _SUBSTITUTE_ROOT_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    x = sympy.Symbol("x")
    subs_map: dict[sympy.Symbol, sympy.Expr] = {x: sympy.sympify(value_str)}
    if value_str_y is not None:
        y = sympy.Symbol("y")
        subs_map[y] = sympy.sympify(value_str_y)
    result = sympy.expand(sympy.sympify(expr_str).subs(subs_map))
    if result.free_symbols:
        raise ValueError(
            f"代入結果が定数にならない: {expr_str!r} [x={value_str!r}, y={value_str_y!r}] -> {result!r}"
        )
    disp = fmt_radical(result)
    srepr = sympy.srepr(result)

    ops = _SUBSTITUTE_ROOT_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            result_display=disp if i == len(ops) - 1
            else _substitute_root_phrase(expr_str, value_str, value_str_y)[op],
            narration=_SUBSTITUTE_ROOT_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# math.compare_radical_values（g3_l15.calculation Lv1/Lv2）— 根号を含む数の大小比較・並べ替え
#
# 平方根は正の実数の範囲では2乗の大小と一致する（sympy の厳密な代数比較で判定・evalf 不使用）。
# 答えは昇順に並べた Tuple の SymbolicAnswer（display は "<" でつないだ不等号チェーン）。
# ---------------------------------------------------------------------------
_COMPARE_STEPS: dict[str, list[str]] = {
    "compare_pair": ["square_each_value", "compare_squares"],
    "compare_triplet": ["convert_to_squared_form", "compare_and_order"],
}

_COMPARE_OP_NARRATION: dict[str, str] = {
    "square_each_value": "根号を含む数はそれぞれ2乗し、根号のない数どうしで比べられるようにする。",
    "compare_squares": "2乗した値どうしを比べ、値が大きいほうがもとの数も大きいと判断する。",
    "convert_to_squared_form": "整数や係数つきの根号もふくめ、すべての数を2乗した値に直す。",
    "compare_and_order": "2乗した値の大小の順に、もとの数を並べる。",
}

_COMPARE_OP_PHRASE: dict[str, str] = {
    "square_each_value": "",
    "convert_to_squared_form": "",
}


@register_solver("math.compare_radical_values")
def compare_radical_values(exprs: object, mode: object) -> Solution:
    """根号を含む数の大小を比較・並べ替える（C3 g3_l15.calculation Lv1/Lv2）。

    式の文字列のリスト（各要素は整数または根号を含む式）だけから、sympy の厳密な
    代数比較（evalf を使わない正確な大小判定）で昇順に並べる（double-solve）。答えは
    昇順の Tuple の SymbolicAnswer（display は "<" でつないだ不等号チェーン）。
    """
    mode_s = str(mode)
    if mode_s not in _COMPARE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    # **答えは問題文に出ている形のまま並べる。** sympy に簡約させると √44 が 2√11 に
    # なり、「√82 と √44 の大小を表せ」に対して「2√11 < √82」と答えることになっていた
    # （EVALUATION D-21）。Lv1 は「2乗して比べる」だけの段なので、変形は答えに要らない。
    raw = [str(e) for e in cast("list[str]", exprs)]
    pairs = sorted(((sympy.sympify(s), s) for s in raw), key=lambda t: t[0])
    ordered = [v for v, _ in pairs]
    disp = " < ".join(fmt_radical_source(s) for _, s in pairs)
    srepr = sympy.srepr(sympy.Tuple(*ordered))

    ops = _COMPARE_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr if i == len(ops) - 1 else "",
            # 2乗した値そのものを見せる（面③）。ここが比較の根拠になる。
            result_display=disp if i == len(ops) - 1
            else "、".join(sympy.sstr(sympy.expand(v**2)) for v, _ in pairs),
            narration=_COMPARE_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "simplify_radical", "fmt_radical", "fmt_radical_source",
    "evaluate_radical_substitution", "compare_radical_values",
]
