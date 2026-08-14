"""正の数・負の数の四則（数値式の評価）まわりの独立再計算ソルバ（実装設計 §6.2 double-solve）。

solver は**問題パラメータだけ**（与式の文字列 expr_str と mode）から答えと steps を導く
（recipe の構成値は見ない）。純粋・決定論・SymPy 恒真であること。乱数は引かない。

C1（g1 数と式・正負の数）クラスタの計算セル群を1つの汎用ソルバに集約する:
  `math.evaluate_numeric_expression(expr_str, mode)` が数値式を sympy で厳密評価し、
  mode ごとに steps の op 列を変える（＝level_sep）。答えは定数（Integer/Rational）の
  SymbolicAnswer。定数答えの G-Q5t は given whitelist と narration の数字不記載で守る
  （問題文の数値はすべて given 由来＝whitelist なので、答えは原理上漏洩しない・§引継 3）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver
from engine.packs.math.solvers._step_text import top_level_parts


def fmt_number(v: sympy.Expr) -> str:
    """数（Integer / Rational）を教材表記にする（分数は p/q・符号は分子に載る）。

    例: Integer(-8) -> "-8" / Rational(-1, 3) -> "-1/3" / Rational(2, 3) -> "2/3"。
    """
    if v.is_Integer:
        return str(int(v))
    if isinstance(v, sympy.Rational):
        return f"{v.p}/{v.q}"
    raise ValueError(f"数として表示できない値: {v!r}")


def _decimal_display(v: sympy.Expr) -> str | None:
    """有限小数で書ける値を小数の文字列にする（書けなければ None）。"""
    if v.is_Integer:
        return str(int(v))
    if not isinstance(v, sympy.Rational):
        return None
    q = int(v.q)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    if q != 1:
        return None
    digits, r = 0, sympy.Rational(v)
    while r.q != 1:
        r *= 10
        digits += 1
    return f"{float(v):.{digits}f}"


def fmt_measure(v: sympy.Expr) -> str:
    """**長さ・面積・体積の値**の表示。有限小数なら小数で書く。

    量には小数で答えるのが教材の作法（`112.5 cm³` と書き、`225/2 cm³` とは書かない）。
    式の中の数（`x = -107/12`）は分数のままが正しいので、そちらは `fmt_number`。

    同じ量が、箱ひげ図のセルでは `13.5`、四分位数のセルでは `27/2` になっていた
    （`_fmt_half`）のと同じ食い違いが、面積・体積・線分の長さにもあった:
    `173/2`（二等辺三角形の底辺）・`333/2`（長方形の対角線の半分）・
    `225/2 cm³`（三角柱の体積）・`2065/2`（動点の三角形の面積）。
    割り切れない値（1/3 など）は分数のまま出す——量として書けない形を隠さないため。
    """
    return _decimal_display(v) or fmt_number(v)


# mode -> op 列（steps の骨格）。level_sep はこの op 列の相異で作る（同一 unit の
# Lv1/Lv2 が異なる mode を持つ）。narration に数字は書かない（G-Q5t 偽陽性の元・§5-#9）。
_MODE_STEPS: dict[str, list[str]] = {
    # g1_l3 加法
    "addition_pair": ["determine_sum_sign", "add_magnitudes"],
    "addition_terms": ["rewrite_as_term_sum", "group_by_sign", "total_terms"],
    # g1_l4 減法
    "subtraction_pair": ["rewrite_subtraction_as_addition", "add_signed"],
    "subtraction_terms": ["rewrite_all_as_addition", "group_by_sign", "total_terms"],
    # g1_l5 加減混合（項の概念）
    "add_sub_terms": ["drop_parentheses_to_terms", "group_by_sign", "total_terms"],
    "add_sub_terms_rational": ["drop_parentheses_to_terms", "align_fractions", "total_terms"],
    # g1_l6 乗法
    "multiplication_pair": ["determine_product_sign", "multiply_magnitudes"],
    "multiplication_chain": ["count_negative_factors", "multiply_all_magnitudes"],
    # g1_l7 累乗
    "power_single": ["rewrite_power_as_product", "evaluate_power_with_sign"],
    "power_sign_contrast": ["identify_base_scope", "evaluate_power_with_sign"],
    # g1_l8 除法
    "divide_pair": ["rewrite_division_as_reciprocal", "multiply_signed"],
    "divide_chain": ["rewrite_all_as_reciprocal", "determine_product_sign", "multiply_all_magnitudes"],
    # g1_l9 四則混合・分配法則
    "four_operations": ["evaluate_powers_and_parentheses", "multiply_and_divide", "add_and_subtract"],
    "distributive_trick": ["rewrite_as_round_plus_offset", "distribute_over_round", "combine_easy_parts"],
    # g1_l2 絶対値
    "absolute_value": ["locate_on_number_line", "read_distance_from_zero"],
}

# op -> (narration, 非終端 step の result_display フレーズ)。数字は書かない。
_OP_NARRATION: dict[str, str] = {
    "determine_sum_sign": "たがいの数の符号を見て、和の符号を先に決める（同符号なら絶対値の和、異符号なら絶対値の差）。",
    "add_magnitudes": "決めた符号のもとで絶対値を計算し、和を求める。",
    "rewrite_as_term_sum": "かっこを外し、それぞれの数を符号のついた項として並べる。",
    "group_by_sign": "正の項どうし、負の項どうしをそれぞれまとめる。",
    "total_terms": "正の合計と負の合計を合わせて、答えを求める。",
    "rewrite_subtraction_as_addition": "ひく数の符号を変えて、たし算に直す。",
    "add_signed": "符号に注意して和を計算する。",
    "rewrite_all_as_addition": "すべてのひき算を、符号を変えてたし算に直す。",
    "drop_parentheses_to_terms": "かっこを外して、符号のついた項の和とみなす。",
    "align_fractions": "分数・小数を通分してそろえる。",
    "determine_product_sign": "かけ合わせる数の符号から、積の符号を先に決める。",
    "multiply_magnitudes": "絶対値どうしをかけて、積を求める。",
    "count_negative_factors": "負の数の個数を数え、積の符号を決める（偶数個なら正、奇数個なら負）。",
    "multiply_all_magnitudes": "すべての絶対値をかけ合わせて、積を求める。",
    "rewrite_power_as_product": "累乗を、同じ数を指数の回数だけかけ合わせる積に書き直す。",
    "evaluate_power_with_sign": "符号に注意して計算し、累乗の値を求める。",
    "identify_base_scope": "指数がどの数にかかっているか（かっこの有無）を見分ける。",
    "rewrite_division_as_reciprocal": "わる数の逆数をかけるかけ算に直す。",
    "multiply_signed": "符号に注意してかけ算を計算する。",
    "rewrite_all_as_reciprocal": "すべてのわり算を、逆数をかけるかけ算に直す。",
    "evaluate_powers_and_parentheses": "累乗とかっこの中を先に計算する。",
    "multiply_and_divide": "乗法と除法を計算する。",
    "add_and_subtract": "加法と減法を計算して答えを求める。",
    "rewrite_as_round_plus_offset": "計算しやすいように、片方の数をきりのよい数と小さな数の和や差に分ける。",
    "distribute_over_round": "分配法則を使って、きりのよい数の積と小さな数の積に分けて計算する。",
    "combine_easy_parts": "2つの積を合わせて、答えを求める。",
    "locate_on_number_line": "その数が数直線上で 0 からどちら側にあるかを見る。",
    "read_distance_from_zero": "0 からの距離が絶対値なので、符号を取り去った大きさを答える。",
}

# ---------------------------------------------------------------------------
# 途中の手の括弧に入れる**式そのもの**（面③）。
#
# 以前はここに「和の符号を先に決める」のような**指示の言い直し**を置いていた。
# 解説の括弧は「その手で得たもの」を入れるところなので、言い直しだと読んでも
# 新しいことが1つも増えない（(-8)-3+(-9) の解説が3行とも指示文だった）。
#
# **narration には数字を書かない規約はそのまま。** ヒントは narration しか見ない
# （`t1_template._build_hints`）ので、ここに値を書いても答えの先出しにはならない。
#
# solver は expr_str（recipe が組んだ標準形。被演算子は必ずかっこ付き）しか
# 受け取らないので、途中の式もここで組み直す。
# ---------------------------------------------------------------------------
def _rat(s: str) -> sympy.Rational:
    return sympy.Rational(sympy.sympify(s, rational=True))


def _disp(v: sympy.Rational, decimal: bool) -> str:
    """値の表示。与式に小数が出ていれば小数で書く（問題文の書き方に合わせる）。"""
    if decimal:
        d = _decimal_display(v)
        if d is not None:
            return d
    return fmt_number(v)


def _paren(v: sympy.Rational, decimal: bool) -> str:
    d = _disp(v, decimal)
    return f"({d})" if v < 0 else d


def _join_terms(terms: list[sympy.Rational], decimal: bool) -> str:
    """符号のついた項の和（`3/4 - 1/2 + 7`）。"""
    out = _disp(terms[0], decimal)
    for t in terms[1:]:
        out += f" - {_disp(-t, decimal)}" if t < 0 else f" + {_disp(t, decimal)}"
    return out


def _join_as_additions(terms: list[sympy.Rational], decimal: bool) -> str:
    """すべてたし算に直した並び（`3/4 + (1/2) + (-7)`）。"""
    return " + ".join(_paren(t, decimal) for t in terms)


def _group_by_sign(terms: list[sympy.Rational], decimal: bool) -> str:
    """正の項の和と負の項の和（`10 + (-30)`）。

    **片方の符号しか無いときは和を書かない。** 書くと次の手（答え）と同じ値になり、
    2行つづけて同じ数が並ぶ。この場合は絶対値の和の形（`-(8 + 3 + 9)`）にする
    ——教科書がそう書くし、次の手で計算する余地が残る。
    """
    zero = sympy.Integer(0)
    pos = sum((t for t in terms if t > 0), zero)
    neg = sum((t for t in terms if t < 0), zero)
    if pos and neg:
        return f"{_disp(pos, decimal)} + ({_disp(neg, decimal)})"
    sign = "-" if neg else "+"
    return f"{sign}({' + '.join(_disp(abs(t), decimal) for t in terms)})"


def _common_denominator(terms: list[sympy.Rational], decimal: bool) -> str:
    """通分した項の並び（`24/40 - 4/40 - 5/40 + 10/40`）。"""
    lcm = 1
    for t in terms:
        lcm = sympy.ilcm(lcm, int(t.q))
    def one(t: sympy.Rational) -> str:
        return f"{int(t * lcm)}/{lcm}" if lcm != 1 else fmt_number(t)
    out = one(terms[0])
    for t in terms[1:]:
        out += f" - {one(-t)}" if t < 0 else f" + {one(t)}"
    return out


def _sign_of(v: sympy.Rational) -> str:
    return "-" if v < 0 else "+"


def _magnitudes(values: list[sympy.Rational], decimal: bool) -> str:
    return " × ".join(_disp(abs(v), decimal) for v in values)


def _round_split(base: int) -> tuple[int, int]:
    """`297` → `(300, -3)`。分配法則で使う「きりのよい数」と「小さな数」。

    recipe は base = r + off（r は 10・100…、|off| ≤ 4）として引く。solver は
    expr_str しか受け取らないので、ここで同じ分け方を復元する。
    """
    for k in (1000, 100, 10):
        r = int(round(base / k)) * k
        if r and abs(base - r) <= 4:
            return r, base - r
    return base, 0


def _signed_step_displays(expr_str: str, mode: str, final: str) -> list[str]:
    """mode ごとの、各手の括弧に入れる表示（最後は答え）。"""
    dec = "." in expr_str

    if mode in ("addition_pair", "multiplication_pair"):
        sep = "+" if mode == "addition_pair" else "*"
        vals = [_rat(t) for _, t in top_level_parts(expr_str, sep)]
        a, b = vals[0], vals[1]
        if mode == "addition_pair":
            if (a > 0) == (b > 0):
                inner = f"{_disp(abs(a), dec)} + {_disp(abs(b), dec)}"
            else:
                hi, lo = sorted([abs(a), abs(b)], reverse=True)
                inner = f"{_disp(hi, dec)} - {_disp(lo, dec)}"
            return [f"{_sign_of(a + b)}({inner})", final]
        return [f"{_sign_of(a * b)}({_magnitudes(vals, dec)})", final]

    if mode in ("addition_terms", "add_sub_terms", "subtraction_terms",
                "add_sub_terms_rational"):
        parts = top_level_parts(expr_str, "+-")
        terms = [(-_rat(t) if op == "-" else _rat(t)) for op, t in parts]
        # 「すべてのひき算をたし算に直す」手は、たし算の形で見せる。
        first = (
            _join_as_additions(terms, dec)
            if mode == "subtraction_terms"
            else _join_terms(terms, dec)
        )
        if mode == "add_sub_terms_rational":
            return [first, _common_denominator(terms, dec), final]
        return [first, _group_by_sign(terms, dec), final]

    if mode == "subtraction_pair":
        parts = top_level_parts(expr_str, "-")
        a = _rat(parts[0][1])
        b = -_rat(parts[1][1])
        return [f"{_paren(a, dec)} + {_paren(b, dec)}", final]

    if mode == "multiplication_chain":
        vals = [_rat(t) for _, t in top_level_parts(expr_str, "*")]
        product = sympy.Integer(1)
        for v in vals:
            product *= v
        return [f"{_sign_of(product)}({_magnitudes(vals, dec)})", final]

    if mode in ("divide_pair", "divide_chain"):
        parts = top_level_parts(expr_str, "*/")
        vals = [(1 / _rat(t) if op == "/" else _rat(t)) for op, t in parts]
        as_product = " × ".join(_paren(v, dec) for v in vals)
        if mode == "divide_pair":
            return [as_product, final]
        product = sympy.Integer(1)
        for v in vals:
            product *= v
        return [as_product, f"{_sign_of(product)}({_magnitudes(vals, dec)})", final]

    if mode == "power_single":
        base_str, n = expr_str.rsplit("**", 1)
        base = _rat(base_str)
        return [" × ".join([_paren(base, dec)] * int(n)), final]

    if mode == "power_sign_contrast":
        base_str, n = expr_str.rsplit("**", 1)
        # `(-5)³` は底ごと・`-5³` は指数が 5 だけにかかる。**この違いがこの手の中身**
        # なので、括弧にはどちらの積になるかを書く。
        if base_str.startswith("("):
            base = _rat(base_str)
            return [" × ".join([_paren(base, dec)] * int(n)), final]
        magnitude = _rat(base_str.lstrip("-"))
        product = " × ".join([_disp(magnitude, dec)] * int(n))
        return [f"-({product})", final]

    if mode == "four_operations":
        return _four_operations_displays(expr_str, dec, final)

    if mode == "distributive_trick":
        parts = top_level_parts(expr_str, "*")
        base, mul = int(_rat(parts[0][1])), int(_rat(parts[1][1]))
        r, off = _round_split(base)
        sign = "+" if off > 0 else "-"
        return [
            f"({r} {sign} {abs(off)}) × {mul}",
            f"{r} × {mul} {sign} {abs(off)} × {mul}",
            final,
        ]

    if mode == "absolute_value":
        inner = _rat(expr_str[len("Abs("):-1])
        side = "左" if inner < 0 else "右"
        return [f"{_disp(inner, dec)} は 0 より{side}", final]

    raise ValueError(f"途中の表示を組めない mode: {mode!r}")


def _four_operations_displays(expr_str: str, dec: bool, final: str) -> list[str]:
    """四則混合の3手（累乗・かっこ → 乗除 → 加減）。

    `(8)-(6)**2*(5)+(16)/(-4)` を
    `8 - 36 × 5 + 16 ÷ (-4)` → `8 - 180 + (-4)` → `-176` と刻む。
    """
    terms = top_level_parts(expr_str, "+-")
    after_power: list[str] = []
    after_muldiv: list[sympy.Rational] = []
    for _op, term in terms:
        factors = top_level_parts(term, "*/")
        shown: list[str] = []
        value = sympy.Integer(1)
        for i, (fop, factor) in enumerate(factors):
            v = _rat(factor)
            value = value / v if fop == "/" else (v if i == 0 else value * v)
            piece = _paren(v, dec)
            shown.append(piece if i == 0 else f"{'÷' if fop == '/' else '×'} {piece}")
        after_power.append(" ".join(shown))
        after_muldiv.append(value)

    signed = [(-v if op == "-" else v) for (op, _), v in zip(terms, after_muldiv, strict=True)]
    line1 = after_power[0]
    for (op, _), text in zip(terms[1:], after_power[1:], strict=True):
        line1 += f" {'-' if op == '-' else '+'} {text}"
    line2 = _join_terms(signed, dec)
    return [line1, line2, final]


@register_solver("math.evaluate_numeric_expression")
def evaluate_numeric_expression(expr_str: str, mode: object) -> Solution:
    """正負の数の四則（数値式）を評価して1つの数にする（g1 正負の数 calculation）。

    与式の文字列だけから sympy で厳密評価する（double-solve）。答えは定数
    （Integer/Rational）の SymbolicAnswer。mode ごとに steps の op 列を変える＝level_sep。
    narration には数字を書かない（G-Q5t 偽陽性の元・§5-#9）。
    """
    mode_s = str(mode)
    if mode_s not in _MODE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    # rational=True で小数リテラル（0.5 等）も既約分数として厳密評価する。
    value = sympy.sympify(expr_str, rational=True)
    if not value.is_number:
        raise ValueError(f"数値に評価されない与式: {expr_str!r} -> {value!r}")
    r_srepr = sympy.srepr(value)
    r_disp = fmt_number(value)
    # **小数で与えた累乗は小数で答える。** 中1の「(-0.9)³」の答えを -729/1000 と
    # 書く教材は無い（-0.729 と書く）。累乗は底がそのまま与式に出るので、与式に
    # 小数が入っていれば答えも小数で書ける（分数は登場しない mode）。
    if mode_s in ("power_single", "power_sign_contrast", "absolute_value") and "." in expr_str:
        as_decimal = _decimal_display(value)
        if as_decimal is not None:
            r_disp = as_decimal

    ops = _MODE_STEPS[mode_s]
    displays = _signed_step_displays(expr_str, mode_s, r_disp)
    assert len(displays) == len(ops), (
        f"{mode_s}: 手の数 {len(ops)} と途中の表示 {len(displays)} が合わない"
    )
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=r_srepr,
            result_display=displays[i],
            narration=_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=r_disp)
    return Solution(answer=answer, steps=steps)


@register_solver("math.order_signed_numbers")
def order_signed_numbers(numbers_str: str, ascending: object) -> Solution:
    """複数の数を小さい／大きい順に並べる（g1_l2.calculation Lv2）。

    numbers_str は元の提示順の数を "," で区切った sympy 評価可能な文字列（分数・小数を含む）。
    これを厳密値で整列し、順序を SymbolicAnswer（display=整列した表示・srepr=Tuple）で返す。
    ascending が真なら小さい順、偽なら大きい順。数の表示は元の提示表記を保つため、
    (値, 表示) のペアを numbers_str と併せて渡さず、ここでは値のみ整列して既約表記で表示する。
    """
    tokens = [t.strip() for t in numbers_str.split(",")]
    pairs = [(t, sympy.Rational(sympy.sympify(t, rational=True))) for t in tokens]
    asc = bool(ascending)
    ordered_pairs = sorted(pairs, key=lambda tv: tv[1], reverse=not asc)
    # 答えの表示は元の提示表記（0.2・-3/4 等）を保ったまま並べかえる。
    disp = ", ".join(t for t, _ in ordered_pairs)
    result = sympy.Tuple(*(v for _, v in ordered_pairs))
    r_srepr = sympy.srepr(result)
    steps = [
        Step(
            op="convert_to_common_form",
            args=[],
            result_srepr=r_srepr,
            result_display="、".join(fmt_number(v) for _t, v in pairs),
            narration="分数と小数がまざっているので、大きさを比べやすい形にそろえる。",
        ),
        Step(
            op="compare_on_number_line",
            args=[],
            result_srepr=r_srepr,
            result_display="、".join(fmt_number(v) for _t, v in ordered_pairs),
            narration="それぞれの数が数直線上でどの位置にあるかで大小を比べる（負の数は絶対値が大きいほど小さい）。",
        ),
        Step(
            op="arrange_in_order",
            args=[],
            result_srepr=r_srepr,
            result_display=disp,
            narration="小さい順（または大きい順）に並べかえて答える。",
        ),
    ]
    answer = SymbolicAnswer(srepr=r_srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 素因数分解（g1_l11.calculation）— C1 bespoke
#
# sympy.factorint で分解し、srepr（"2**3*3**2"・sympify で元の数に戻る恒真識別子）と
# display（"2³×3²"・教材表記）を返す。level_sep は mode 別 op 列で作る:
#   factorize_basic    (Lv1): 小さい素数から順にわる 2 手順。
#   factorize_advanced (Lv2): 大きい素数まで順に試す手順を先頭に足した 3 手順。
# 答えは定数扱いの SymbolicAnswer。G-Q5t は問題文の数値が対象数 N のみ（given whitelist）で、
# 答えの素因数・上付き（NFKC 分解後は基数と指数が連結した多桁数になる）はいずれも N と一致しない
# ため漏洩しない（narration に数字も書かない）。
# ---------------------------------------------------------------------------
_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript_int(n: int) -> str:
    """指数を上付き数字にする（例 3 -> "³"）。"""
    return str(n).translate(_SUPERSCRIPT)


def factorization_forms(n: int) -> tuple[str, str]:
    """n の素因数分解の (srepr, display) を返す。

    srepr は "2**3*3**2" 形（素数昇順・sympify で n に戻る）。double-solve は srepr の
    一致で判定するため、solver と checker が同じ n から本関数で導けば恒真に一致する。
    display は "2³×3²" 形（× 区切り・指数は上付き）。
    """
    factors = sympy.factorint(n)  # {prime: exponent}
    items = sorted(factors.items())
    srepr = "*".join(f"{p}**{e}" if e > 1 else f"{p}" for p, e in items)
    display = "×".join(f"{p}{_superscript_int(e)}" if e > 1 else f"{p}" for p, e in items)
    return srepr, display


_FACTORIZE_MODE_STEPS: dict[str, list[str]] = {
    "factorize_basic": ["divide_out_primes_in_order", "write_prime_power_form"],
    "factorize_advanced": [
        "test_successive_prime_divisors",
        "divide_out_primes_in_order",
        "write_prime_power_form",
    ],
}

_FACTORIZE_OP_NARRATION: dict[str, str] = {
    "divide_out_primes_in_order": "小さい素数から順にわり、商が素数になるまでわり続ける。",
    "write_prime_power_form": "現れた素数を、同じ素数の個数を指数にして、累乗の積の形に表す。",
    "test_successive_prime_divisors": (
        "小さい素数でわり切れなくなったら、次に大きい素数を順に試して、"
        "わり切れる素数があるか（残った数が素数かどうか）を調べる。"
    ),
}

def _factorize_phrase(n: int) -> dict[str, str]:
    """素因数分解の手の括弧（わり出した素数そのもの・面③）。"""
    primes = sorted(sympy.factorint(n))
    # 「小さい素数から順にわる」＝1桁の素数、「次に大きい素数を順に試す」＝2桁以上。
    small = [p for p in primes if p < 10]
    large = [p for p in primes if p >= 10]
    return {
        "divide_out_primes_in_order": "、".join(str(p) for p in small) or "わり切れない",
        "test_successive_prime_divisors": "、".join(str(p) for p in large) or "残りは素数",
    }


@register_solver("math.factorize_integer")
def factorize_integer(value: object, mode: object) -> Solution:
    """自然数を素因数分解し、累乗の積の形で表す（g1_l11.calculation）。

    問題パラメータ（対象数 value と mode）だけから sympy.factorint で分解する（double-solve）。
    答えは定数の SymbolicAnswer（srepr="2**3*3**2" / display="2³×3²"）。mode ごとに steps の
    op 列を変える＝level_sep。narration には数字を書かない（G-Q5t 偽陽性の元）。
    """
    mode_s = str(mode)
    if mode_s not in _FACTORIZE_MODE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    n = int(str(value))
    if n < 2:
        raise ValueError(f"素因数分解の対象は 2 以上の整数: {n!r}")
    srepr, disp = factorization_forms(n)

    ops = _FACTORIZE_MODE_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr,
            result_display=disp if i == len(ops) - 1 else _factorize_phrase(n)[op],
            narration=_FACTORIZE_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 科学的記数法 a×10ⁿ（g1_l60.calculation）— C1 bespoke
#
# 正の整数 N を a×10ⁿ（1≤a<10）の形にする。srepr は "4.8E4" 形（"10" トークンを出さない＝
# 問題文の "a×10ⁿ" の "10" と衝突させない）。display は "4.8×10⁴"（NFKC で "10⁴"→"104" と連結
# されるため、こちらも "10" 単独トークンは生じない）。level_sep は mode 別 op 列で作る:
#   sci_notation_basic  (Lv1): 末尾0を除いた有効数字でそのまま a×10ⁿ にする 2 手順。
#   sci_notation_sigfig (Lv2): 指定された有効数字の桁で四捨五入してから a×10ⁿ にする 3 手順。
# G-Q5t: 問題文の数値は N と有効数字の桁数（given・whitelist、「桁」は counter で除外）と、
# 構造的な 1・10（"1以上10未満"・"10ⁿ"）のみ。答えの mantissa は 1 より大きく（純粋な 10 の
# 累乗を除外）、指数は 2〜9 に収まる（N の桁を制御）ため、いずれも漏洩しない。
# ---------------------------------------------------------------------------
_SCI_MODE_STEPS: dict[str, list[str]] = {
    "sci_notation_basic": ["locate_decimal_point", "write_scientific_form"],
    "sci_notation_sigfig": [
        "round_to_significant_figures",
        "locate_decimal_point",
        "write_scientific_form",
    ],
}

_SCI_OP_NARRATION: dict[str, str] = {
    "round_to_significant_figures": (
        "指定された有効数字の桁になるように、その次の位を四捨五入する。"
    ),
    "locate_decimal_point": (
        "小数点を、一の位が1以上10未満になる位置まで動かし、動かした桁数を数える。"
    ),
    "write_scientific_form": (
        "1以上10未満の数と、10を動かした桁数だけ累乗した数との積の形に表す。"
    ),
}

_FROM_SUPERSCRIPT = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")


def _sci_phrase(n: int, sig: int | None, disp: str) -> dict[str, str]:
    """科学的記数法の手の括弧（四捨五入した数・動かした桁数）。"""
    mantissa, superscript = disp.split("×10")
    exponent = int(superscript.translate(_FROM_SUPERSCRIPT))
    digits = mantissa.replace(".", "")
    rounded = digits + "0" * (exponent + 1 - len(digits))
    return {
        "round_to_significant_figures": rounded,
        "locate_decimal_point": f"{mantissa}（小数点を{exponent}桁動かす）",
    }


def scientific_forms(n: int, sig_figs: int | None) -> tuple[str, str]:
    """正の整数 n を科学的記数法にした (srepr, display) を返す。

    sig_figs=None: 末尾0を除いた有効数字をそのまま用いる（Lv1・厳密表現）。
    sig_figs=k   : k 桁の有効数字に四捨五入する（末尾の有効数字の0も残す・Lv2）。
    srepr は "<mantissa>E<exponent>"（"10" を含まない機械識別子）、display は
    "<mantissa>×10^<exponent>"（指数は上付き）。solver と checker が同じ (n, sig_figs) から
    本関数で導けば srepr が恒真に一致する（double-solve）。
    """
    if n <= 0:
        raise ValueError(f"科学的記数法の対象は正の整数: {n!r}")
    if sig_figs is None:
        exponent = len(str(n)) - 1
        sig_digits = str(n).rstrip("0") or "0"
    else:
        if sig_figs < 1:
            raise ValueError(f"有効数字は1以上: {sig_figs!r}")
        exponent = len(str(n)) - 1
        drop = (exponent + 1) - sig_figs
        if drop > 0:
            factor = 10**drop
            rounded = ((n + factor // 2) // factor) * factor  # 四捨五入（round half up）
        else:
            rounded = n
        exponent = len(str(rounded)) - 1  # 繰り上がり（例 999→1000）を反映
        sig_digits = str(rounded)[:sig_figs]  # 先頭 sig_figs 桁（有効数字の0も保持）

    if len(sig_digits) == 1:
        mantissa = sig_digits
    else:
        mantissa = f"{sig_digits[0]}.{sig_digits[1:]}"

    srepr = f"{mantissa}E{exponent}"
    display = f"{mantissa}×10{_superscript_int(exponent)}"
    return srepr, display


@register_solver("math.scientific_notation")
def scientific_notation(value: object, mode: object, sig_figs: object = None) -> Solution:
    """正の整数を a×10ⁿ の形で表す（g1_l60.calculation）。

    問題パラメータ（対象数 value・mode・有効数字 sig_figs）だけから科学的記数法を構成する
    （double-solve）。答えは定数扱いの SymbolicAnswer（srepr="4.8E4" / display="4.8×10⁴"）。
    mode ごとに steps の op 列を変える＝level_sep。narration には数字を書かない。
    """
    mode_s = str(mode)
    if mode_s not in _SCI_MODE_STEPS:
        raise ValueError(f"未知の mode: {mode_s!r}")
    n = int(str(value))
    sig = None if sig_figs is None else int(str(sig_figs))
    srepr, disp = scientific_forms(n, sig)

    ops = _SCI_MODE_STEPS[mode_s]
    steps = [
        Step(
            op=op,
            args=[],
            result_srepr=srepr,
            result_display=disp if i == len(ops) - 1 else _sci_phrase(n, sig, disp)[op],
            narration=_SCI_OP_NARRATION[op],
        )
        for i, op in enumerate(ops)
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# 数直線上の点が表す数を読む（g1_l2.graph_table Lv1）— C1 bespoke（図つき初 C1）
#
# 単位区間 [a, a+1] を k 等分した i 番目の目盛に点 P がある。P が表す数は a + i/k（分数）。
# 問題パラメータ（a, k, i）だけから Rational として恒真に構成する（double-solve）。答えは
# 分数の SymbolicAnswer。narration には数字を書かない（G-Q5t 偽陽性の元）。図の目盛（整数）は
# 図側の whitelist で守り、答え（分数）は図にも問題文にも出さない（漏洩防止）。
# ---------------------------------------------------------------------------
def _read_number_line_point(a: int, k: int, i: int) -> sympy.Rational:
    """点 P が表す数 a + i/k を既約分数（sympy.Rational）で返す。"""
    if k < 2:
        raise ValueError(f"等分数 k は 2 以上: {k!r}")
    if not (1 <= i <= k - 1):
        raise ValueError(f"目盛の位置 i は 1..k-1 の範囲: i={i!r}, k={k!r}")
    return sympy.Rational(a * k + i, k)


@register_solver("math.read_number_line_point")
def read_number_line_point(a: object, k: object, i: object) -> Solution:
    """数直線上の点 P が表す数を読み取る（g1_l2.graph_table Lv1「読む」）。

    問題パラメータ（区間左端 a・等分数 k・目盛位置 i）だけから P の値 a + i/k を導く。
    答えは既約分数の SymbolicAnswer。steps は2手（間の目盛を読む → 等分位置から値を出す）で、
    steps_prefix ヒントが最初の1手の narration（数字なし）を開示できるようにする。
    """
    a_i, k_i, i_i = int(str(a)), int(str(k)), int(str(i))
    value = _read_number_line_point(a_i, k_i, i_i)
    # **2等分・4等分・5等分の目もりは小数で読む。** 教科書は数直線から読んだ数を
    # 「-8.5」と書き、「-17/2」とは書かない（EVALUATION D-5）。3等分のように
    # 小数で書き切れないときだけ分数のままにする。
    disp = _decimal_display(value) or fmt_number(value)
    srepr = sympy.srepr(value)

    steps = [
        Step(
            op="identify_interval",
            args=[],
            result_srepr="",
            result_display=f"{a_i} と {a_i + 1} の間",
            narration="点Pをはさむ両側の整数の目もりを数直線から読み取る。",
        ),
        Step(
            op="read_point",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="目もりの間を等分した位置に着目し、点Pが表す数を求める。",
        ),
    ]
    answer = SymbolicAnswer(srepr=srepr, display=disp)
    return Solution(answer=answer, steps=steps)


__all__ = [
    "evaluate_numeric_expression",
    "factorization_forms",
    "factorize_integer",
    "fmt_number",
    "order_signed_numbers",
    "read_number_line_point",
    "scientific_forms",
    "scientific_notation",
]
