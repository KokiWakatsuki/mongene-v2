"""正の数・負の数の四則（数値式の評価）まわりの recipe（構成的生成・実装設計 §6.1）。

乱数は `draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した与式は独立ソルバ
`math.evaluate_numeric_expression` で再評価し、答えの一致を確認する（double-solve）。

C1（g1 数と式・正負の数）の計算セルを1つの汎用 recipe に集約する:
  `math.compute_signed_arithmetic(ctx, rng)` が mode ごとに演算対象の数（整数・分数・
  小数）を引いて与式を組み立てる。mode は spec_level.params["mode"]（各 unit の各 level に
  一意）。level_sep は solver 側の mode 別 op 列で担保する。答えの数は問題文（＝given のみ）
  の数値がすべて whitelist されるため、定数答えでも G-Q5t 漏洩は起きない（§引継 3）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.core.verify.answer_size import answer_is_too_big, limits_for
from engine.packs.math.visuals.number_line import number_line_labels


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


_SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def _superscript(n: int) -> str:
    """指数を上付き数字にする（例 2 -> "²"）。extract_numbers 非抽出＝次数の漏洩なし。"""
    return str(n).translate(_SUPERSCRIPT)


def _fmt_power_base(value: sympy.Rational, magnitude_disp: str) -> str:
    """累乗の底の表示（負・非整数はかっこで囲む＝底ごと累乗を明示）。

    例: Integer(2)->"2" / Integer(-3)->"(-3)" / Rational(-1,2)->"(-1/2)" / Rational(2,3)->"(2/3)"。
    """
    signed = _fmt_signed(value, magnitude_disp)
    if value < 0 or not value.is_Integer:
        return f"({signed})"
    return signed


# 小数として提示する既約分数（終端小数・表示文字列を明示）。負符号は draw で別途決める。
_DECIMALS: list[tuple[int, int, str]] = [
    (1, 2, "0.5"), (3, 2, "1.5"), (5, 2, "2.5"), (7, 2, "3.5"), (9, 2, "4.5"),
    (1, 4, "0.25"), (3, 4, "0.75"), (5, 4, "1.25"), (7, 4, "1.75"),
    (1, 5, "0.2"), (2, 5, "0.4"), (3, 5, "0.6"), (4, 5, "0.8"),
    (6, 5, "1.2"), (7, 5, "1.4"), (8, 5, "1.6"), (11, 5, "2.2"),
    (1, 10, "0.1"), (3, 10, "0.3"), (7, 10, "0.7"), (9, 10, "0.9"),
    (11, 10, "1.1"), (13, 10, "1.3"), (17, 10, "1.7"), (19, 10, "1.9"),
    (1, 8, "0.125"), (3, 8, "0.375"), (5, 8, "0.625"),
]


def _fmt_signed(value: sympy.Rational, magnitude_disp: str) -> str:
    """符号つき数の表示（負なら先頭に - ・分数/小数は magnitude_disp を使う）。

    magnitude_disp は絶対値の表示（"7"・"2/3"・"0.5"）。value<0 なら "-" を前置する。
    """
    return f"-{magnitude_disp}" if value < 0 else magnitude_disp


def _paren_if_neg(value: sympy.Rational, signed_disp: str) -> str:
    """負の数はかっこで囲む（例 -7 -> "(-7)" / 7 -> "7"）。"""
    return f"({signed_disp})" if value < 0 else signed_disp


def _draw_int_operand(rng: Rng, domain: object) -> tuple[sympy.Rational, str]:
    """整数の被演算子を引く（value, 絶対値表示）。"""
    n = int(draw(domain, rng))
    v = sympy.Integer(n)
    return v, str(abs(n))


def _draw_frac_operand(rng: Rng, domain: object) -> tuple[sympy.Rational, str]:
    """分数の被演算子を引く（既約分数・value, 絶対値表示 "p/q"）。"""
    r = draw(domain, rng)
    assert isinstance(r, sympy.Rational)
    return r, f"{abs(r.p)}/{r.q}"


def _draw_decimal_operand(rng: Rng) -> tuple[sympy.Rational, str]:
    """小数として提示する被演算子を引く（value, 絶対値表示 "0.5" 等）。"""
    p, q, disp = cast("tuple[int, int, str]", draw(_DECIMALS, rng))
    sign = int(draw([1, -1], rng))
    r = sympy.Rational(sign * p, q)
    return r, disp


def _draw_power_operand(
    rng: Rng, kind: str, p: dict[str, object], n: int, limit: int
) -> tuple[sympy.Rational, str]:
    """累乗の底を引く。**答えの分子・分母が limit を超える底は引き直す。**

    定義域を絞るのではなく答えの大きさで測る（絞ると dup_rate が跳ねる）。
    前は底の分子・分母をそのまま広くとっていたので「(-14/3)³ = -2744/27」という、
    中1の累乗としてありえない答えが出ていた。整数の底は対象外——「-13³ = -2197」は
    桁数が多くても教科書にある形で、壊れていたのは分数・小数の底のほうだけ。
    """
    if kind == "int":
        return _draw_operand(rng, kind, p)
    for _ in range(200):
        bval, bmag = _draw_operand(rng, kind, p)
        v = sympy.Rational(bval) ** n
        if abs(v.p) > limit or v.q > limit:
            continue
        # 小数の底は答えも小数で書くので、小数第3位までに収まるものだけ
        # （0.625³ = 0.244140625 は中1の計算問題にならない）。
        if kind == "dec" and 1000 % v.q != 0:
            continue
        return bval, bmag
    raise ValueError("_draw_power_operand: 答えが大きすぎない底を引けず")


def _draw_operand(rng: Rng, kind: str, p: dict[str, object]) -> tuple[sympy.Rational, str]:
    """kind（"int"/"frac"/"dec"）に応じて1つの被演算子を引く（value, 絶対値表示）。"""
    if kind == "int":
        return _draw_int_operand(rng, p["int_domain"])
    if kind == "frac":
        return _draw_frac_operand(rng, p["frac_domain"])
    if kind == "dec":
        return _draw_decimal_operand(rng)
    raise ValueError(f"未知の operand kind: {kind!r}")


def _build(expr_str: str, given_display: str, mode: str, ctx: CellContext) -> MR:
    """与式文字列と表示から MR を組み立てる（double-solve で答え一致を確認）。"""
    solver = REGISTRY.solver("math.evaluate_numeric_expression")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    expected = sympy.sympify(expr_str, rational=True)
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"expr_str": expr_str, "mode": mode, "given_disp": given_display},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_signed_arithmetic"),
    )


# 各 unit の各 level が宣言する concept をすべて列挙（R6: family の concept_tags は
# この集合の部分集合であること）。recipe は _effective_concept_tags で family の宣言を返す。
_SIGNED_ARITHMETIC_CONCEPTS = [
    "signed_number.add_pair",
    "signed_number.add_terms",
    "signed_number.subtract_pair",
    "signed_number.subtract_terms",
    "signed_number.multiply_pair",
    "signed_number.multiply_chain",
    "signed_number.divide_pair",
    "signed_number.divide_chain",
    "signed_number.add_sub_terms_basic",
    "signed_number.add_sub_terms_rational",
    "signed_number.power_single",
    "signed_number.power_sign_contrast",
    "signed_number.four_operations",
    "signed_number.distributive_trick",
    "signed_number.absolute_value",
    "signed_number.order_numbers",
]


@register_recipe("math.compute_signed_arithmetic", provides_concepts=_SIGNED_ARITHMETIC_CONCEPTS)
def compute_signed_arithmetic(ctx: CellContext, rng: Rng) -> MR:
    """正負の数の四則（数値式）を構成して評価する（構成的生成・calculation）。

    `answer_denominator_max` を宣言したレベルは、**答えの分母がその上限に収まるまで
    組み直す**。正負の数の加減は分数と小数を各項で独立に引くので、分母 9 と 7 の
    最小公倍数 63 に小数の 10 と 5 が掛かって `7/9-(-1.2)+4/7-0.6 → 614/315` が
    出ていた（実測で `g1_l5.calculation.Lv2` は 60問中44問が分母13以上）。
    この単元の狙いは符号の処理なので、通分の負荷が支配してはいけない。

    **定義域は狭めない**（狭めると dup_rate が跳ねる）。答えの大きさで測る——
    `g1_l7`（累乗）で同じ手が効いたのと同じ考え方。
    """
    # `answer_denominator_max`（旧・分母だけを見る宣言）と、`answer_size_max`
    # （分母・分子・根号の中をまとめて見る宣言＝`engine.core.verify.answer_size`）の
    # 両方を満たす式を引く。後者は宣言が無くても既定の上限（分母12・分子100）が効くので、
    # `(1/12)³ → 1/1728`・`4/7÷9/8×1/9 → 32/567` はここで落ちて引き直しになる。
    limit = int(ctx.spec_level.params.get("answer_denominator_max", 0))
    limits = limits_for(ctx.spec_level)
    last: MR | None = None
    for _ in range(80):
        mr = _compute_signed_arithmetic_once(ctx, rng)
        last = mr
        if limit > 0:
            value = sympy.Rational(sympy.sympify(mr.params["expr_str"], rational=True))
            if value.q > limit:
                continue
        display = str(getattr(mr.sub_questions[0].answer, "display", "") or "")
        if not answer_is_too_big(display, limits):
            return mr
    # 80回引いても収まらないときは最後の式で通す（1セル丸ごと消えるより軽い。
    # 常態化していれば `python -m engine.eval.answer_size` が上限超えとして見つける）。
    assert last is not None
    return last


def _compute_signed_arithmetic_once(ctx: CellContext, rng: Rng) -> MR:
    """1回ぶんの構成（答えの分母の上限は見ない）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])

    if mode == "addition_pair":
        # 2数の加法（整数）。和が 0 に退化しないよう2つ目を絞る。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        cands = [n for n in _int_domain_values(p["int_domain"]) if n != 0 and (v1 + n) != 0]
        n2 = int(draw({"int_set": cands}, rng))
        v2, m2 = sympy.Integer(n2), str(abs(n2))
        expr_str = f"({v1})+({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}+{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "addition_terms":
        # 3項の加法（整数・分数・小数の混在）。和が 0 に退化しないよう最後の項を絞る。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds[:-1]]
        running = sum((v for v, _ in ops), sympy.Integer(0))
        last = _draw_nonzero_last(rng, kinds[-1], p, running)
        ops.append(last)
        expr_str = "+".join(f"({v})" for v, _ in ops)
        disp = "+".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode == "subtraction_pair":
        # 2数の減法（整数）。差が 0 に退化しないよう絞る。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        cands = [n for n in _int_domain_values(p["int_domain"]) if n != 0 and (v1 - n) != 0]
        n2 = int(draw({"int_set": cands}, rng))
        v2, m2 = sympy.Integer(n2), str(abs(n2))
        expr_str = f"({v1})-({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}-{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "subtraction_terms":
        # 3項の減法（整数・分数・小数の混在）。op1 - op2 - op3。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds]
        # 退化（答え 0）を避けるため最後の項を再抽選で調整。
        while (ops[0][0] - ops[1][0] - ops[2][0]) == 0:
            ops[2] = _draw_operand(rng, kinds[2], p)
        expr_str = f"({ops[0][0]})-({ops[1][0]})-({ops[2][0]})"
        disp = "-".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode in ("add_sub_terms", "add_sub_terms_rational"):
        # 加法と減法の混じった計算（項の概念）。各項に + / - の演算子をつけて並べる。
        # Lv1（add_sub_terms・整数）/ Lv2（add_sub_terms_rational・分数小数を含む）。
        kinds = list(cast("list[str]", p["term_kinds"]))
        terms, opsyms, value = _draw_add_sub_terms(rng, kinds, p)
        expr_str = f"({terms[0][0]})" + "".join(
            f"{opsyms[i]}({terms[i + 1][0]})" for i in range(len(opsyms))
        )
        disp = _paren_if_neg(terms[0][0], _fmt_signed(terms[0][0], terms[0][1]))
        for i, opsym in enumerate(opsyms):
            v, m = terms[i + 1]
            disp += opsym + _paren_if_neg(v, _fmt_signed(v, m))
        assert value == sympy.sympify(expr_str, rational=True)
        return _build(expr_str, disp, mode, ctx)

    if mode == "absolute_value":
        # 絶対値を求める。**問題文には裸の数を出す**（`|-5|` ではなく `-5`）。
        # テンプレートが「次の数の絶対値を求めよ。」と言っているので、ここで
        # 絶対値記号を付けると「絶対値の絶対値」を問うことになる。
        # 教科書も裸の数を並べる（FdData 中1 は `-5, -2.5, -1/2`）。
        kind = str(draw(p["value_kinds"], rng))
        aval, amag = _draw_operand(rng, kind, p)
        # 小数は**小数のまま**式に載せる（solver が「小数で与えたら小数で答える」を
        # 判断できるように。Rational に直すと -2.5 の絶対値が 5/2 と出る）。
        src = _fmt_signed(aval, amag) if kind == "dec" else str(aval)
        expr_str = f"Abs({src})"
        disp = _fmt_signed(aval, amag)
        return _build(expr_str, disp, mode, ctx)

    if mode == "order_numbers":
        return _build_order_numbers(ctx, rng, p)

    if mode == "four_operations":
        # 四則の混じった計算（累乗・かっこを含む）。骨格 A - (B)²×C + D÷E（D=k·E で割り切れる）。
        big_a = int(draw(p["lead_domain"], rng))  # 先頭項（正）
        b = int(draw(p["base_domain"], rng))  # 累乗の底（|b|≥2）
        c = int(draw(p["multiplier_domain"], rng))  # ≥2
        e = int(draw(p["divisor_domain"], rng))  # |e|≥2
        k = int(draw(p["quotient_domain"], rng))  # 商（≠0）
        dd = k * e  # 割り切れる被除数
        expr_str = f"({big_a})-({b})**2*({c})+({dd})/({e})"
        disp = (
            f"{big_a}-{_paren_if_neg(sympy.Integer(b), str(b))}{_superscript(2)}×{c}"
            f"+{_paren_if_neg(sympy.Integer(dd), str(dd))}÷{_paren_if_neg(sympy.Integer(e), str(e))}"
        )
        return _build(expr_str, disp, mode, ctx)

    if mode == "distributive_trick":
        # 分配法則で工夫して計算。base=(R+off)、multiplier m。value=base·m=(R·m)+(off·m)。
        r = int(draw(p["round_domain"], rng))  # きりのよい数（10,100,…）
        off = int(draw(p["offset_domain"], rng))  # 小さな数（±1..±4, ≠0）
        mul = int(draw(p["multiplier_domain"], rng))  # かける数（≥2）
        base = r + off
        expr_str = f"({base})*({mul})"
        disp = f"{base}×{mul}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "power_single":
        # 累乗の計算。底は整数・分数・小数（符号つき）、指数 n。底の種類で dup を分散する。
        kind = str(draw(p["base_kinds"], rng))
        n = int(draw(p["exponent_domain"], rng))
        bval, bmag = _draw_power_operand(rng, kind, p, n, int(p["answer_magnitude_max"]))
        # 小数の底は**小数のまま**式に載せる（solver が「小数で与えた累乗は小数で
        # 答える」を判断できるように。Rational に直して渡すと (-0.9)³ の答えが
        # -729/1000 と出ていた）。sympify(..., rational=True) なので値は厳密。
        base_src = f"-{bmag}" if (kind == "dec" and bval < 0) else (bmag if kind == "dec" else str(bval))
        expr_str = f"({base_src})**{n}"
        disp = f"{_fmt_power_base(bval, bmag)}{_superscript(n)}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "power_sign_contrast":
        # (-a)^n と -a^n の区別。整数底のみ form=neg_inside（-a^n）を出し、指数のかかる範囲を
        # 見分けさせる。分数・小数底は neg_outside（かっこつき）で dup 分散のみに使う。
        kind = str(draw(p["base_kinds"], rng))
        n = int(draw(p["exponent_domain"], rng))
        bval, bmag = _draw_power_operand(rng, kind, p, n, int(p["answer_magnitude_max"]))
        form = str(draw(["neg_outside", "neg_inside"], rng)) if kind == "int" else "neg_outside"
        if form == "neg_inside":
            # 指数は数だけにかかり、先頭の - は最後（常に負）。底の絶対値を使う。
            expr_str = f"-{bmag}**{n}"
            disp = f"-{bmag}{_superscript(n)}"
        else:
            # 底ごと累乗（負の底はかっこで囲む）。分数・小数底もここで扱う。
            neg_src = f"-{bmag}" if kind == "dec" else str(-abs(bval))
            expr_str = f"({neg_src})**{n}"
            disp = f"(-{bmag}){_superscript(n)}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "multiplication_pair":
        # 2数の乗法（整数）。
        v1, m1 = _draw_int_operand(rng, p["int_domain"])
        v2, m2 = _draw_int_operand(rng, p["int_domain"])
        expr_str = f"({v1})*({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}×{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "multiplication_chain":
        # 3数の乗法（整数・分数・小数の混在）。
        kinds = list(cast("list[str]", p["term_kinds"]))
        ops = [_draw_operand(rng, k, p) for k in kinds]
        expr_str = "*".join(f"({v})" for v, _ in ops)
        disp = "×".join(_paren_if_neg(v, _fmt_signed(v, m)) for v, m in ops)
        return _build(expr_str, disp, mode, ctx)

    if mode == "divide_pair":
        # 2数の除法（整数・割り切れる）。answer-first: 商 q と除数 d を引き、被除数 q·d を作る。
        d = int(draw(p["divisor_domain"], rng))
        q = int(draw(p["quotient_domain"], rng))
        dividend = q * d
        v1, m1 = sympy.Integer(dividend), str(abs(dividend))
        v2, m2 = sympy.Integer(d), str(abs(d))
        expr_str = f"({v1})/({v2})"
        disp = f"{_paren_if_neg(v1, _fmt_signed(v1, m1))}÷{_paren_if_neg(v2, _fmt_signed(v2, m2))}"
        return _build(expr_str, disp, mode, ctx)

    if mode == "divide_chain":
        # 分数の乗除混在（逆数）。op1 ÷ op2 × op3。分母が 0 にならないよう frac は既約非零。
        f1 = _draw_frac_operand(rng, p["frac_domain"])
        f2 = _draw_frac_operand(rng, p["frac_domain"])
        f3 = _draw_frac_operand(rng, p["frac_domain"])
        expr_str = f"({f1[0]})/({f2[0]})*({f3[0]})"
        disp = (
            f"{_paren_if_neg(f1[0], _fmt_signed(f1[0], f1[1]))}"
            f"÷{_paren_if_neg(f2[0], _fmt_signed(f2[0], f2[1]))}"
            f"×{_paren_if_neg(f3[0], _fmt_signed(f3[0], f3[1]))}"
        )
        return _build(expr_str, disp, mode, ctx)

    raise ValueError(f"未知の mode: {mode!r}")


def _int_domain_values(domain: object) -> list[int]:
    """int_range/int_set の候補整数を列挙する（exclude 適用）。"""
    d = cast("dict[str, object]", domain)
    if "int_range" in d:
        lo, hi = cast("list[int]", d["int_range"])
        vals = list(range(int(lo), int(hi) + 1))
    elif "int_set" in d:
        vals = [int(v) for v in cast("list[int]", d["int_set"])]
    else:
        raise ValueError(f"未対応 int domain: {domain!r}")
    excl = {int(v) for v in cast("list[int]", d.get("exclude", []))}
    return [v for v in vals if v not in excl]


def _draw_nonzero_last(
    rng: Rng, kind: str, p: dict[str, object], running: sympy.Rational
) -> tuple[sympy.Rational, str]:
    """和が 0 にならない最後の項を引く（有界リトライ）。"""
    for _ in range(200):
        v, m = _draw_operand(rng, kind, p)
        if (running + v) != 0:
            return v, m
    raise ValueError("nonzero last term を確保できず")


def _build_order_numbers(ctx: CellContext, rng: Rng, p: dict[str, object]) -> MR:
    """複数の数を小さい／大きい順に並べる MR を組む（g1_l2.calculation Lv2）。

    整数・分数・小数を混ぜて count 個引き、値が相異する集合を作る（同値だと順序が一意でない）。
    元の提示順（シャッフル）と、小さい／大きい順の別を surface とし、独立ソルバ
    math.order_signed_numbers で整列を再計算する（double-solve）。
    """
    count = int(draw(p["count_domain"], rng))
    kinds = list(cast("list[str]", p["number_kinds"]))
    ascending = str(draw(["asc", "desc"], rng)) == "asc"

    # 値が相異する count 個を引く（有界リトライ）。表示トークンと値を保持。
    tokens: list[str] = []
    values: list[sympy.Rational] = []
    for _ in range(400):
        if len(tokens) >= count:
            break
        kind = kinds[len(tokens) % len(kinds)]
        v, mag = _draw_operand(rng, kind, p)
        vr = sympy.Rational(v)
        if any(vr == e for e in values):
            continue
        tokens.append(_order_token(v, mag))
        values.append(vr)
    if len(tokens) < count:
        raise ValueError("相異する数を確保できず")

    numbers_str = ", ".join(tokens)
    order_word = "小さい" if ascending else "大きい"
    given_display = f"{numbers_str} を{order_word}順に並べよ"

    solver = REGISTRY.solver("math.order_signed_numbers")
    sol = cast(Solution, solver(numbers_str, ascending))
    assert isinstance(sol.answer, SymbolicAnswer)
    assert [s.op for s in sol.steps] == [
        "convert_to_common_form", "compare_on_number_line", "arrange_in_order",
    ]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"numbers_str": numbers_str, "ascending": ascending, "mode": "order_numbers"},
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compute_signed_arithmetic"),
    )


def _order_token(value: sympy.Rational, magnitude_disp: str) -> str:
    """並べ替え問題で提示する数の表記（符号つき・そのまま・かっこ無し）。"""
    return _fmt_signed(value, magnitude_disp)


def _draw_add_sub_terms(
    rng: Rng, kinds: list[str], p: dict[str, object]
) -> tuple[list[tuple[sympy.Rational, str]], list[str], sympy.Rational]:
    """加減混合の項と演算子（+/-）を引く（結果が 0 に退化しないよう有界リトライ）。

    戻り値: (項の [(value, 絶対値表示)] 列, 各項間の演算子 "+"/"-" 列, 評価値)。
    """
    for _ in range(200):
        terms = [_draw_operand(rng, k, p) for k in kinds]
        opsyms = [str(draw(["+", "-"], rng)) for _ in range(len(kinds) - 1)]
        # 加減が「混じる」よう + と - を両方含める（加減混合の忠実性）。
        if "+" not in opsyms or "-" not in opsyms:
            continue
        value = terms[0][0]
        for opsym, (tv, _) in zip(opsyms, terms[1:]):
            value = value + tv if opsym == "+" else value - tv
        if value != 0:
            return terms, opsyms, value
    raise ValueError("非退化の加減混合を確保できず")


# ---------------------------------------------------------------------------
# 素因数分解（g1_l11.calculation）— C1 bespoke
#
# 対象数 N を「最大素因数」で層別して mode ごとに引く。候補は最大素因数のふるい
# （lpf[n]==n ⇔ n は素数）でモジュール読込時に一度だけ算出する（factorint を N 個回さない）。
#   factorize_basic    : 合成数・最大素因数 ≤ 13・[12, 3000]（C≈409）。
#   factorize_advanced : 合成数・17 ≤ 最大素因数 ≤ 47・[200, 3000]（大きめ＋大きい素数）。
# dup_key は params の N のみで分散するため、候補プールを 400+ 取り dup に余裕を持たせる
# （100-seed 実測は推定よりやや高く出るため、推定 ~0.11 で実測を 0.20 未満に収める）。
# ---------------------------------------------------------------------------
_FACTORIZE_SIEVE_LIMIT = 3000


def _largest_prime_factor_sieve(limit: int) -> list[int]:
    """0..limit の各数の最大素因数を返す（素数 n は lpf[n]==n）。O(n log log n)。"""
    lpf = [0] * (limit + 1)
    for i in range(2, limit + 1):
        if lpf[i] == 0:  # i は素数
            for j in range(i, limit + 1, i):
                lpf[j] = i  # 昇順に上書き＝最後に残るのが最大素因数
    return lpf


_LPF = _largest_prime_factor_sieve(_FACTORIZE_SIEVE_LIMIT)

_FACTORIZE_BASIC_NUMBERS = [
    n for n in range(12, _FACTORIZE_SIEVE_LIMIT + 1) if _LPF[n] != n and _LPF[n] <= 13
]
_FACTORIZE_ADVANCED_NUMBERS = [
    n for n in range(200, _FACTORIZE_SIEVE_LIMIT + 1) if _LPF[n] != n and 17 <= _LPF[n] <= 47
]

_FACTORIZE_CANDIDATES: dict[str, list[int]] = {
    "factorize_basic": _FACTORIZE_BASIC_NUMBERS,
    "factorize_advanced": _FACTORIZE_ADVANCED_NUMBERS,
}

_FACTORIZE_CONCEPTS = [
    "prime_factorization.execute_basic",
    "prime_factorization.execute_advanced",
]


@register_recipe("math.factorize_integer", provides_concepts=_FACTORIZE_CONCEPTS)
def factorize_integer(ctx: CellContext, rng: Rng) -> MR:
    """自然数を素因数分解する MR を組む（g1_l11.calculation）。

    mode で層別した候補プールから対象数 N を引き、独立ソルバ math.factorize_integer で
    分解して答えを刻印する（double-solve）。given は対象数のみ（＝問題文の数値も N だけ）で、
    答えの素因数はいずれも N と一致しないため G-Q5t 漏洩は起きない。
    """
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])
    candidates = _FACTORIZE_CANDIDATES.get(mode)
    if candidates is None:
        raise ValueError(f"未知の mode: {mode!r}")
    n = int(draw({"int_set": candidates}, rng))

    solver = REGISTRY.solver("math.factorize_integer")
    sol = cast(Solution, solver(n, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: srepr（"2**3*3**2"）を評価すると元の数 N に戻る。
    assert sympy.sympify(sol.answer.srepr) == n, (
        f"double-solve 不一致: srepr {sol.answer.srepr!r} が {n} に戻らない"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"value": str(n), "mode": mode},
        given={"expression": str(n)},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.factorize_integer"),
    )


# ---------------------------------------------------------------------------
# 科学的記数法 a×10ⁿ（g1_l60.calculation）— C1 bespoke
#
# 対象数 N を「きれいな有効数字部 × 10 のべき」で構成し、独立ソルバ math.scientific_notation で
# a×10ⁿ に直す。dup は N（Lv2 は N と有効数字桁数）で分散。答えの mantissa が 1 になる
# （＝問題文の "1以上" と衝突）ことを避けるため、純粋な 10 の累乗・丸め繰り上がりを構成側で除外する。
# ---------------------------------------------------------------------------
# 有効数字部（末尾0を含まない・1桁〜3桁・先頭が「1」単独＝mantissa 1 になる 1 は除く）。
_SCI_SIG_PARTS = (
    [k for k in range(2, 10)]
    + [k for k in range(11, 100) if k % 10 != 0]
    + [k for k in range(101, 1000) if k % 10 != 0]
)


def _sci_mantissa_is_one(n: int, sig: int | None) -> bool:
    """科学的記数法にしたとき mantissa が 1（= 1以上 と衝突）になるか。"""
    from engine.packs.math.solvers.arithmetic import scientific_forms

    srepr, _ = scientific_forms(n, sig)
    mantissa = srepr.split("E")[0]
    return bool(sympy.Rational(mantissa) == 1)


_SCI_CONCEPTS = [
    "scientific_notation.express_basic",
    "scientific_notation.express_sigfig",
]


@register_recipe("math.scientific_notation", provides_concepts=_SCI_CONCEPTS)
def scientific_notation(ctx: CellContext, rng: Rng) -> MR:
    """自然数を a×10ⁿ の形で表す MR を組む（g1_l60.calculation）。

    Lv1（sci_notation_basic）: N = 有効数字部 × 10^scale を厳密に a×10ⁿ にする。
    Lv2（sci_notation_sigfig）: 有効数字より多い桁の N を引き、指定桁で四捨五入して a×10ⁿ にする。
    mantissa=1（"1以上" と衝突）や指数の範囲外を避けるよう構成する。given は N と（Lv2 は）
    有効数字桁数で、いずれも whitelist されるため漏洩しない。
    """
    p = ctx.spec_level.params
    mode = cast(str, p["mode"])

    if mode == "sci_notation_basic":
        # 有効数字部 × 10^scale。scale は 1桁部で 3〜6、2桁部で 2〜5、3桁部で 1〜4 とし
        # 指数を 3〜6 に収める（指数 1・10 を避ける）。mantissa は必ず 1 より大きい。
        sig_part = int(draw({"int_set": _SCI_SIG_PARTS}, rng))
        base_len = len(str(sig_part))
        scale = int(draw({"int_range": [7 - base_len - 3, 7 - base_len]}, rng))
        n = sig_part * (10**scale)
        sig = None
        given = {"expression": str(n)}
    elif mode == "sci_notation_sigfig":
        # 有効数字桁 sig と、それより 1〜2 桁多い N を引き、四捨五入で丸める。
        sig = int(draw({"int_set": [2, 3]}, rng))
        n = 0
        for _ in range(200):
            extra = int(draw({"int_set": [1, 2]}, rng))
            total = sig + extra
            lo, hi = 10 ** (total - 1), 10**total - 1
            cand = int(draw({"int_range": [lo, hi]}, rng))
            if _sci_mantissa_is_one(cand, sig):
                continue  # 丸めが 10 の累乗へ繰り上がる（mantissa 1）ものは除外
            n = cand
            break
        if n == 0:
            raise ValueError("科学的記数法 Lv2 の N を構成できず")
        given = {"expression": str(n), "sig_figs": str(sig)}
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.scientific_notation")
    sol = cast(Solution, solver(n, mode, sig))
    assert isinstance(sol.answer, SymbolicAnswer)

    params: dict[str, object] = {"value": str(n), "mode": mode}
    if sig is not None:
        params["sig_figs"] = str(sig)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="value",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )
    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params=params,
        given=given,
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.scientific_notation"),
    )


# ---------------------------------------------------------------------------
# 数直線上の点が表す数を読む（g1_l2.graph_table Lv1）— C1 bespoke（図つき初 C1）
#
# 単位区間 [a, a+1] を k 等分した i 番目の目盛に点 P を置き、P が表す数 a + i/k を答えとする
# （answer-first）。独立ソルバ math.read_number_line_point で同じ (a,k,i) から再計算し一致を
# assert（double-solve）。given は空（数直線は図で提示され、テキストに接地すべき given は無い＝
# graph_read と同じ設計判断・G-GND は given 空なら自明に通過）。
#
# dup: params (a, k, i) の3自由度で分散する。a の範囲 × (k,i) の組（k∈{2..5}・1≤i≤k-1 で 10 組）
# で 400+ の候補を確保する（鉄則②）。答え（分数）は図にも問題文にも出さない（漏洩防止）。
# 図内テキストは整数目盛ラベルと「P」のみ（number_line_labels）＝ G-Q5v の whitelist に一致。
# ---------------------------------------------------------------------------
_NUMBER_LINE_CONCEPTS = [
    "number_line.read_point",
]


@register_recipe("math.read_number_line_point", provides_concepts=_NUMBER_LINE_CONCEPTS)
def read_number_line_point(ctx: CellContext, rng: Rng) -> MR:
    """数直線上の点 P が表す数を読み取る MR を組む（g1_l2.graph_table Lv1）。"""
    p = ctx.spec_level.params
    a = int(draw(p["interval_domain"], rng))
    k = int(draw(p["subdivisions"], rng))
    i = int(draw({"int_range": [1, k - 1]}, rng))

    solver = REGISTRY.solver("math.read_number_line_point")
    sol = cast(Solution, solver(a, k, i))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: srepr（"Rational(...)"）を評価すると a + i/k に戻る。
    assert sympy.sympify(sol.answer.srepr) == sympy.Rational(a * k + i, k), (
        f"double-solve 不一致: srepr {sol.answer.srepr!r} が a+i/k に戻らない"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="read_point",
        answer=sol.answer,
        steps=sol.steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    visual_plan = VisualPlan(
        style="number_line",
        labels=number_line_labels(a),
        elements=[
            VisualElement(kind="number_line", attrs={}),
            VisualElement(kind="point", attrs={}),
        ],
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={"a": str(a), "k": str(k), "i": str(i)},
        given={},
        sub_questions=[sub_question],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.read_number_line_point"),
    )


__all__ = [
    "compute_signed_arithmetic",
    "factorize_integer",
    "read_number_line_point",
    "scientific_notation",
]
