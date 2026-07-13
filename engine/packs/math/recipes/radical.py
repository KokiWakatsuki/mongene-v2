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
        c = int(draw({"int_set": list(range(1, 5))}, rng))
        a = int(draw({"int_set": list(range(2, 13))}, rng))
        b = int(draw({"int_set": list(range(2, 13))}, rng))
        d = int(draw({"int_set": list(range(2, 13))}, rng))
        expr = f"{c}*sqrt({a})*sqrt({b})/sqrt({d})"
        disp = f"{'' if c == 1 else c}√{a} × √{b} ÷ √{d}"
        return expr, disp

    if mode in ("simplify_root", "simplify_root_large"):
        krange = list(range(2, 6)) if mode == "simplify_root" else list(range(2, 10))
        c = int(draw({"int_set": list(range(1, 10))}, rng))
        k = int(draw({"int_set": krange}, rng))
        m = int(draw({"int_set": _SQUAREFREE}, rng))
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


__all__ = ["simplify_radical", "_SQUAREFREE"]
