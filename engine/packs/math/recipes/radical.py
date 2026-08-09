"""平方根（根号）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は与式（根号を含む未簡約の式）を構成し、独立ソルバ math.simplify_radical で
簡約して答えを刻印する（double-solve）。given には未簡約の式（display）を出し、答えは
簡約後の根号式。答えは根号を含む定数式で、G-Q5t は答えの数値トークンを検査するが、問題文の
数値はすべて given 由来（whitelist）＝答えが問題文に現れる値はすべて whitelist されるため
漏洩は起きない（テンプレは数字を含まない）。narration にも数字を書かない。

C3（g3 数と式・平方根）クラスタ。乱数は `engine.core.rng.draw` 以外で解釈しない。
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
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

_RADICAL_CONCEPTS = [
    "radical.square_of_root",
    "radical.multiply_divide",
    "radical.simplify_form",
    "radical.rationalize_denominator",
    "radical.add_subtract",
    "radical.various_calculation",
]

# 平方因数を持たない数（1 より大きい squarefree）。a√b の b・根号の中身に使う。
_SQUAREFREE = [
    n for n in range(2, 60)
    if all(n % (p * p) != 0 for p in range(2, int(n**0.5) + 1))
]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _coef_sqrt(c: int, rad: int) -> str:
    """係数つき根号の表示。例: (1,2)->"√2" / (-1,2)->"-√2" / (3,2)->"3√2"。c≠0。"""
    if c == 1:
        return f"√{rad}"
    if c == -1:
        return f"-√{rad}"
    return f"{c}√{rad}"


def _sqrt_term_tail(c: int, rad: int) -> str:
    """先頭以外の根号項を符号つきで後置。例: (3,2)->" + 3√2" / (-1,2)->" - √2"。c≠0。"""
    body = _coef_sqrt(abs(c), rad)
    return f" + {body}" if c > 0 else f" - {body}"


def _radical_construct(mode: str, rng: Rng) -> tuple[str, str]:
    """mode ごとに (expr_str[sympy用], given_display[未簡約の表示]) を構成する。"""
    if mode == "square_of_root":
        # DOF が n（と2形式）のみで少ないため n を広くとる（dup 分散）。
        form = str(draw(["squared", "sqrt_square"], rng))
        if form == "squared":
            n = int(draw({"int_set": [k for k in range(2, 300)
                                      if int(k**0.5) ** 2 != k]}, rng))
            return f"(sqrt({n}))**2", f"(√{n})²"
        k = int(draw({"int_set": list(range(2, 60))}, rng))
        return f"sqrt({k * k})", f"√{k * k}"

    if mode == "root_mult":
        a = int(draw({"int_set": list(range(2, 21))}, rng))
        b = int(draw({"int_set": list(range(2, 21))}, rng))
        return f"sqrt({a})*sqrt({b})", f"√{a} × √{b}"

    if mode == "root_mult_div":
        # 根号の中に**平方数を残さない**（教科書は √4 とは書かず 2 と書く）。
        # また割る数と掛ける数が同じだと相殺するだけの式になり、問題として成立しない
        # （「4√6 × √8 ÷ √8」が実際に出ていた）。
        radicands = [n for n in range(2, 13) if int(n**0.5) ** 2 != n]
        c = int(draw({"int_set": list(range(1, 5))}, rng))
        a = int(draw({"int_set": radicands}, rng))
        b = int(draw({"int_set": radicands}, rng))
        d = int(draw({"int_set": [n for n in radicands if n not in (a, b)]}, rng))
        expr = f"{c}*sqrt({a})*sqrt({b})/sqrt({d})"
        disp = f"{'' if c == 1 else c}√{a} × √{b} ÷ √{d}"
        return expr, disp

    if mode in ("simplify_root", "simplify_root_large"):
        # 根号の中の数に上限を置く。前は k を 9、m を 59 まで独立に引いていたので
        # 「3√4617」（=3√(9²×57)）のように、中学の手に負えない素因数分解を
        # 要求する式が出ていた（教科書は √72・√180 のあたり）。
        krange = list(range(2, 6)) if mode == "simplify_root" else list(range(2, 10))
        n_max = 300 if mode == "simplify_root" else 800
        pairs = [(k, m) for k in krange for m in _SQUAREFREE if k * k * m <= n_max]
        c = int(draw({"int_set": list(range(1, 10))}, rng))
        k, m = pairs[int(draw({"int_set": list(range(len(pairs)))}, rng))]
        n = k * k * m
        expr = f"{c}*sqrt({n})"
        disp = f"{'' if c == 1 else c}√{n}"
        return expr, disp

    if mode == "rationalize_mono":
        k = int(draw({"int_set": list(range(1, 21))}, rng))
        a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 20]}, rng))
        return f"{k}/sqrt({a})", f"{k}/√{a}"

    if mode == "add_roots":
        a = int(draw({"int_set": _SQUAREFREE}, rng))
        p = int(draw({"int_set": list(range(2, 10))}, rng))
        q = int(draw({"int_set": list(range(1, 10))}, rng))
        r = int(draw({"int_set": list(range(1, 10))}, rng))
        # 答え (p+q-r)√a が 0 に退化しないよう r を引き直す（0 は根号が消え題材が破綻）。
        while p + q - r == 0:
            r = int(draw({"int_set": list(range(1, 10))}, rng))
        expr = f"{p}*sqrt({a})+{q}*sqrt({a})-{r}*sqrt({a})"
        disp = f"{_coef_sqrt(p, a)}{_sqrt_term_tail(q, a)}{_sqrt_term_tail(-r, a)}"
        return expr, disp

    if mode == "add_roots_simplify":
        a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 7]}, rng))
        # 3つの平方因数 k1,k2,k3 を「段階的に相異」させて引く（一括判定 while だと
        # k1==k2 のとき 3 つ揃わず無限ループになるため、各段で前の値を除外して引く）。
        kdom = list(range(2, 8))
        k1 = int(draw({"int_set": kdom}, rng))
        k2 = int(draw({"int_set": kdom}, rng))
        while k2 == k1:
            k2 = int(draw({"int_set": kdom}, rng))
        k3 = int(draw({"int_set": kdom}, rng))
        while k3 in (k1, k2):
            k3 = int(draw({"int_set": kdom}, rng))
        n1, n2, n3 = k1 * k1 * a, k2 * k2 * a, k3 * k3 * a
        expr = f"sqrt({n1})-sqrt({n2})+sqrt({n3})"
        disp = f"√{n1} - √{n2} + √{n3}"
        return expr, disp

    if mode == "expand_roots":
        a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 15]}, rng))
        s = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        p = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        q = int(draw({"int_set": [n for n in range(-5, 6) if n != 0]}, rng))
        expr = f"sqrt({a})*(sqrt({a})+({s}))+(sqrt({a})+({p}))*(sqrt({a})+({q}))"
        st = f"√{a} - {-s}" if s < 0 else f"√{a} + {s}"
        pt = f"√{a} - {-p}" if p < 0 else f"√{a} + {p}"
        qt = f"√{a} - {-q}" if q < 0 else f"√{a} + {q}"
        disp = f"√{a}({st}) + ({pt})({qt})"
        return expr, disp

    if mode == "calculate_and_combine":
        # g3_l23 立式後の√計算（例: √2×√18+√50）。√a×√(a·m1²)=a·m1 の乗法と
        # √(a·m2²)=m2√a の加減が混在する形を構成する。
        a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 10]}, rng))
        m1 = int(draw({"int_set": list(range(2, 10))}, rng))
        m2_cands = [v for v in range(2, 10) if v != m1]
        m2 = int(draw({"int_set": m2_cands}, rng))
        sign = str(draw(["+", "-"], rng))
        n1, n2 = a * m1 * m1, a * m2 * m2
        expr = f"sqrt({a})*sqrt({n1}){sign}sqrt({n2})"
        disp = f"√{a} × √{n1} {sign} √{n2}"
        return expr, disp

    if mode == "rationalize_conjugate":
        a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 15]}, rng))
        b = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 15]}, rng))
        while b == a:
            b = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 15]}, rng))
        k = int(draw({"int_set": list(range(1, 10))}, rng))
        expr = f"{k}/(sqrt({a})-sqrt({b}))"
        disp = f"{k}/(√{a} - √{b})"
        return expr, disp

    raise ValueError(f"未知の mode: {mode!r}")


@register_recipe("math.simplify_radical", provides_concepts=_RADICAL_CONCEPTS)
def simplify_radical(ctx: CellContext, rng: Rng) -> MR:
    """根号を含む式を簡約する MR を組む（C3 g3_l14/l17〜l21.calculation）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    expr_str, given_disp = _radical_construct(mode, rng)

    solver = REGISTRY.solver("math.simplify_radical")
    sol = cast(Solution, solver(expr_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 答えは与式と数学的に等しい（簡約前後で値が変わらない）。sympy の堅牢なゼロ判定
    # `.equals(0)` を使う（`diff.evalf()` は記号的にゼロの式でゼロ確定のため精度を無限に上げ
    # ハングする既知の挙動があるため使わない。`.equals` は数値サンプリング併用で確実に止まる）。
    diff = sympy.sympify(expr_str) - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: {expr_str} と {sol.answer.display} が等しくない"
    )

    sub_question = SubQuestionMR(
        label="(1)",
        asked="simplified_expr",
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
        params={"expr_str": expr_str, "mode": mode},
        given={"expression": given_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.simplify_radical"),
    )


def _p_term_x(p: int) -> str:
    """-2px の表示（x² のうしろに続く1次項・符号込み）。例: 1->" - 2x" / -3->" + 6x"。p≠0。"""
    coef = -2 * p
    mag = abs(coef)
    body = "x" if mag == 1 else f"{mag}x"
    return f" + {body}" if coef > 0 else f" - {body}"


def _root_plus_int_disp(a: int, p: int) -> str:
    """√a+p / √a-p の表示（p≠0）。例: (3,1)->"√3 + 1" / (3,-1)->"√3 - 1"。"""
    return f"√{a} + {p}" if p > 0 else f"√{a} - {-p}"


@register_recipe(
    "math.evaluate_radical_substitution",
    provides_concepts=["radical.evaluate_expression_value", "radical.evaluate_symmetric_pair_value"],
)
def evaluate_radical_substitution(ctx: CellContext, rng: Rng) -> MR:
    """√を含む値を式に代入して式の値を求める MR を組む（C3 g3_l22.calculation Lv2/Lv3）。

    Lv2 (substitute_root_quadratic): x = p+√a（p は 0 でない整数・a は非平方の
    squarefree）を x²-2px に代入すると x²-2px = a-p² となり根号が恒等的に消える
    （構成側で1次係数を -2p に固定することで保証・a が非平方だから a-p²=0 に
    退化する余地もない＝有界リトライ不要）。

    Lv3 (substitute_conjugate_pair_sum_squares): 共役な組 x=√a+p, y=√a-p を
    x²+y² に代入すると x²+y² = 2a+2p² となり根号が恒等的に消える（p,a の符号に
    関わらず常に成立・a≥2 なので 2a+2p²=0 に退化する余地もない＝有界リトライ不要）。
    """
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "substitute_root_quadratic":
        return _evaluate_substitute_root_quadratic(ctx, rng, mode)
    if mode == "substitute_conjugate_pair_sum_squares":
        return _evaluate_substitute_conjugate_pair(ctx, rng, mode)
    raise ValueError(f"未知の mode: {mode!r}")


def _evaluate_substitute_root_quadratic(ctx: CellContext, rng: Rng, mode: str) -> MR:
    p = int(draw({"int_set": [n for n in range(-12, 13) if n != 0]}, rng))
    a = int(draw({"int_set": _SQUAREFREE}, rng))

    value_str = f"sqrt({a})+({p})"
    expr_str = f"x**2-2*({p})*x"
    given_expr_disp = f"x²{_p_term_x(p)}"
    given_value_disp = _root_plus_int_disp(a, p)

    solver = REGISTRY.solver("math.evaluate_radical_substitution")
    sol = cast(Solution, solver(expr_str, value_str, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 独立に構成値から再計算した値と、solver の答えが一致する（.equals で堅牢に
    # ゼロ判定・evalf はハングするため使わない）。
    x = sympy.Symbol("x")
    expected = sympy.expand(sympy.sympify(expr_str).subs(x, sympy.sympify(value_str)))
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: 構成値 {expected} と solver 再計算 {sol.answer.display} が等しくない"
    )
    # 答えは根号を含まない定数（自由変数なし）。a が非平方ゆえ a-p²=0 に退化しない。
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={"expr_str": expr_str, "value_str": value_str, "mode": mode},
        given={"expression": given_expr_disp, "input_value": given_value_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_radical_substitution"),
    )


def _evaluate_substitute_conjugate_pair(ctx: CellContext, rng: Rng, mode: str) -> MR:
    p = int(draw({"int_set": [n for n in range(-12, 13) if n != 0]}, rng))
    a = int(draw({"int_set": _SQUAREFREE}, rng))

    value_str_x = f"sqrt({a})+({p})"
    value_str_y = f"sqrt({a})-({p})"
    expr_str = "x**2+y**2"
    given_expr_disp = "x² + y²"
    given_value_disp = (
        f"x = {_root_plus_int_disp(a, p)}、y = {_root_plus_int_disp(a, -p)}"
    )

    solver = REGISTRY.solver("math.evaluate_radical_substitution")
    sol = cast(Solution, solver(expr_str, value_str_x, mode, value_str_y))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 独立に構成値から再計算した値と、solver の答えが一致する（.equals で堅牢に
    # ゼロ判定・evalf はハングするため使わない）。
    x, y = sympy.symbols("x y")
    expected = sympy.expand(
        sympy.sympify(expr_str).subs({x: sympy.sympify(value_str_x), y: sympy.sympify(value_str_y)})
    )
    diff = expected - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: 構成値 {expected} と solver 再計算 {sol.answer.display} が等しくない"
    )
    # 答えは根号を含まない定数（自由変数なし）。a≥2 かつ x²+y²=2a+2p²>0 ゆえ退化しない。
    assert not sympy.sympify(sol.answer.srepr).free_symbols

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
        params={
            "expr_str": expr_str,
            "value_str": value_str_x,
            "value_str_y": value_str_y,
            "mode": mode,
        },
        given={"expression": given_expr_disp, "input_value": given_value_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.evaluate_radical_substitution"),
    )


# 正方形の面積から1辺を求める場面（数を小さく保ったまま組み合わせを稼ぐ軸）。
_AREA_SCENES: list[tuple[str, str]] = [
    ("正方形", "cm"),
    ("正方形の紙", "cm"),
    ("正方形のタイル", "cm"),
    ("正方形の板", "cm"),
    ("正方形の花だん", "m"),
    ("正方形の土地", "m"),
]

_SIDE_FROM_AREA_CONCEPTS = ["radical.find_side_from_area"]


@register_recipe("math.find_side_from_area", provides_concepts=_SIDE_FROM_AREA_CONCEPTS)
def find_side_from_area(ctx: CellContext, rng: Rng) -> MR:
    """正方形の面積から1辺の長さを根号で表す MR を組む（C3 g3_l23.find_value Lv2）。

    answer-first: 平方因数を持たない a（squarefree・a>1）と整数 k から面積
    area=k²a を決める（1辺は k√a）。独立ソルバ math.simplify_radical
    （mode=find_side_from_area）が area だけから √area を a·k²/a の平方因数を
    見つけて簡約し直す（double-solve）。
    """
    # 面積に上限を置く。前は k を 1〜19、a を 59 まで独立に引いていたので
    # 「面積 19133cm²（=19²×53）→ 19√53」のように、素因数分解が中学の手に負えない
    # 問題が出ていた。狭めたぶんは**場面**の軸で稼ぐ（FIXES.md の原則1・2）。
    area_max = int(ctx.spec_level.params.get("area_max", 600))
    cands = [
        (a, k)
        for a in _SQUAREFREE
        for k in range(1, 20)
        if k * k * a <= area_max
    ]
    a, k = cands[int(draw({"int_set": list(range(len(cands)))}, rng))]
    area = k * k * a
    scene_index = int(draw({"int_set": list(range(len(_AREA_SCENES)))}, rng))
    scene, unit = _AREA_SCENES[scene_index]
    expr_str = f"sqrt({area})"
    condition = f"面積が {area}{unit}² の{scene}の1辺の長さを、根号を使って表せ"

    solver = REGISTRY.solver("math.simplify_radical")
    sol = cast(Solution, solver(expr_str, "find_side_from_area"))
    assert isinstance(sol.answer, SymbolicAnswer)
    diff = sympy.sympify(expr_str) - sympy.sympify(sol.answer.srepr)
    assert diff.equals(0), (
        f"double-solve 不一致: {expr_str} と {sol.answer.display} が等しくない"
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
        params={"expr_str": expr_str, "scene": scene},
        given={"condition": condition},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.find_side_from_area"),
    )


_COMPARE_RADICAL_CONCEPTS = ["radical.compare_magnitude"]


def _draw_compare_pair(rng: Rng) -> tuple[list[str], str]:
    """g3_l15.calculation Lv1: 2つの bare √ の大小比較（例: √5 と √8）。"""
    a = int(draw({"int_set": list(range(2, 100))}, rng))
    b_cands = [v for v in range(2, 100) if v != a]
    b = int(draw({"int_set": b_cands}, rng))
    exprs = [f"sqrt({a})", f"sqrt({b})"]
    disp = f"√{a} と √{b}"
    return exprs, disp


def _draw_compare_triplet(rng: Rng) -> tuple[list[str], str]:
    """g3_l15.calculation Lv2: 整数・bare √・係数つき√ の3値を小さい順に並べる。"""
    n = int(draw({"int_set": list(range(2, 10))}, rng))
    a = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 20]}, rng))
    b = int(draw({"int_set": [s for s in _SQUAREFREE if s <= 20 and s != a]}, rng))
    c = int(draw({"int_set": list(range(2, 5))}, rng))
    exprs = [str(n), f"sqrt({a})", f"{c}*sqrt({b})"]
    disp = f"{n}、√{a}、{c}√{b}"
    return exprs, disp


@register_recipe("math.compare_radical_values", provides_concepts=_COMPARE_RADICAL_CONCEPTS)
def compare_radical_values(ctx: CellContext, rng: Rng) -> MR:
    """根号を含む数の大小を比較・並べ替える MR を組む（C3 g3_l15.calculation Lv1/Lv2）。"""
    mode = cast(str, ctx.spec_level.params["mode"])
    if mode == "compare_pair":
        exprs, given_disp = _draw_compare_pair(rng)
    elif mode == "compare_triplet":
        exprs, given_disp = _draw_compare_triplet(rng)
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    solver = REGISTRY.solver("math.compare_radical_values")
    sol = cast(Solution, solver(exprs, mode))
    assert isinstance(sol.answer, SymbolicAnswer)
    # 恒真: 答え（昇順 Tuple）は構成した値の集合と一致し、実際に昇順になっている。
    ordered = sympy.sympify(sol.answer.srepr)
    assert set(sympy.sympify(e) for e in exprs) == set(ordered)
    assert all(ordered[i] < ordered[i + 1] for i in range(len(ordered) - 1)), (
        f"double-solve 不一致: {sol.answer.display} が昇順になっていない"
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
        params={"exprs": exprs, "mode": mode},
        given={"expression": given_disp},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.compare_radical_values"),
    )


__all__ = [
    "simplify_radical", "_SQUAREFREE", "evaluate_radical_substitution",
    "find_side_from_area", "compare_radical_values",
]
