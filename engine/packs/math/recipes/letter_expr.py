"""文字式（一次式の計算）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した与式は
独立ソルバ `math.evaluate_letter_expression` で再整理し、答えの一致を確認する（double-solve）。

C1（g1 数と式・文字式）の計算セルを1つの汎用 recipe に集約する（arithmetic.py の
`compute_signed_arithmetic` と同型）:
  `math.compute_letter_expression(ctx, rng)` が mode ごとに一次式の項・係数を引いて与式を
  組み立てる。mode は spec_level.params["mode"]（各 unit の各 level に一意）。level_sep は
  solver 側の mode 別 op 列で担保する。答えは自由変数 x を含む一次式。

G-Q5t 対策（式答えは display 全体一致で検査・§引継 13c-2-#1）: 答えが定数に退化しないよう
x 係数は構成で非零にし、さらに「答えの表示が与式中に部分文字列として現れる」漏洩
（例: 答え bare `12x` が被除数 `(12x - 9)` の一部と一致／答え `3x` が与式 `-3x` の一部と一致）を
有界リトライで排除する。narration には数字を書かない。
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

# 表示・sympy 文字列の整形ヘルパは polynomial recipe（式の計算）と共通。
from engine.packs.math.recipes.polynomial import (
    _domain_candidates,
    _fmt_expr_from_terms,
    _sympy_str_from_terms,
)


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


# 各 unit の各 level が宣言する concept をすべて列挙（R6: family の concept_tags は
# この集合の部分集合であること）。
_LETTER_EXPR_CONCEPTS = [
    "letter_expr.combine_linear",
    "letter_expr.add_sub_linear_paren",
    "letter_expr.distribute_linear",
    "letter_expr.distribute_divide_mixed",
]


def _draw_expr(mode: str, p: dict[str, object], rng: Rng) -> tuple[str, str]:
    """mode ごとに一次式を1つ引いて (sympy 文字列, 表示) を返す（answer-first の逆算）。

    リトライで再抽選されうるので RNG を都度消費してよい（golden は最終列で承認する）。
    """
    coeff_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["coeff_domain"])) if v != 0]
    const_cands = [v for v in _domain_candidates(cast("dict[str, object]", p["const_domain"])) if v != 0]

    if mode == "combine_linear":
        # 同類項をまとめて一次式を整理する（a1·x + b1 + a2·x + b2）。x 係数の和≠0 を保証。
        a1 = int(draw({"int_set": coeff_cands}, rng))
        a2 = int(draw({"int_set": [v for v in coeff_cands if v + a1 != 0]}, rng))
        b1 = int(draw({"int_set": const_cands}, rng))
        b2 = int(draw({"int_set": const_cands}, rng))
        terms = [(a1, "x"), (b1, ""), (a2, "x"), (b2, "")]
        return _sympy_str_from_terms(terms), _fmt_expr_from_terms(terms)

    if mode == "expand_paren_linear":
        # かっこを含む一次式の加減 (a1·x + b1) op (a2·x + b2)。答えの x 係数≠0 を保証。
        op = str(draw(["+", "-"], rng))
        a1 = int(draw({"int_set": coeff_cands}, rng))
        if op == "+":
            a2_cands = [v for v in coeff_cands if v + a1 != 0]
        else:
            a2_cands = [v for v in coeff_cands if a1 - v != 0]
        a2 = int(draw({"int_set": a2_cands}, rng))
        b1 = int(draw({"int_set": const_cands}, rng))
        b2 = int(draw({"int_set": const_cands}, rng))
        g1 = [(a1, "x"), (b1, "")]
        g2 = [(a2, "x"), (b2, "")]
        expr_str = f"({_sympy_str_from_terms(g1)}){op}({_sympy_str_from_terms(g2)})"
        given_display = f"({_fmt_expr_from_terms(g1)}) {op} ({_fmt_expr_from_terms(g2)})"
        return expr_str, given_display

    if mode == "distribute_linear":
        # 一次式に数を掛ける k(a·x + b)。k は ±1・0 を除く（分配が自明にならない）。負の k も含む。
        k = int(draw(p["multiplier_domain"], rng))
        a = int(draw({"int_set": coeff_cands}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        inner = [(a, "x"), (b, "")]
        expr_str = f"({k})*({_sympy_str_from_terms(inner)})"
        given_display = f"{k}({_fmt_expr_from_terms(inner)})"
        return expr_str, given_display

    if mode == "distribute_divide_linear":
        # 分配と分数係数の乗除混合 k(a·x + b) op (rx·m·x + ry·m) ÷ m。
        # answer-first: ÷m 後の係数 rx,ry と除数 m を先に決め、割り切れる被除数を逆算する。
        # 答え = k(a·x+b) op (rx·x + ry)。x 係数（k·a ± rx）≠0 を保証。
        op = str(draw(["+", "-"], rng))
        k = int(draw(p["multiplier_domain"], rng))
        a = int(draw({"int_set": coeff_cands}, rng))
        b = int(draw({"int_set": const_cands}, rng))
        m = int(draw(p["divisor_domain"], rng))
        rx_target = k * a
        if op == "+":
            rx_cands = [v for v in coeff_cands if rx_target + v != 0]
        else:
            rx_cands = [v for v in coeff_cands if rx_target - v != 0]
        rx = int(draw({"int_set": rx_cands}, rng))
        ry = int(draw({"int_set": const_cands}, rng))
        outer = [(a, "x"), (b, "")]
        divided = [(rx * m, "x"), (ry * m, "")]  # 割り切れる被除数
        expr_str = (
            f"({k})*({_sympy_str_from_terms(outer)})"
            f"{op}(({_sympy_str_from_terms(divided)}))/({m})"
        )
        given_display = (
            f"{k}({_fmt_expr_from_terms(outer)}) {op} "
            f"({_fmt_expr_from_terms(divided)}) ÷ {m}"
        )
        return expr_str, given_display

    raise ValueError(f"未知の mode: {mode!r}")


def _leaks(answer_display: str, given_display: str) -> bool:
    """答えの表示が与式中に部分文字列として現れるか（G-Q5t の disp∈norm_full を先取り）。

    正規化は空白除去で保守的に照合する（normalize_math_text は空白を単一化するのみだが、
    本チェックは空白差に依らず漏洩を検出したいので全空白を除去して比較する）。
    """
    return answer_display.replace(" ", "") in given_display.replace(" ", "")


@register_recipe("math.compute_letter_expression", provides_concepts=_LETTER_EXPR_CONCEPTS)
def compute_letter_expression(ctx: CellContext, rng: Rng) -> MR:
    """一次式の計算（加減・乗除）を構成して整理する（answer-first・calculation）。"""
    p = ctx.spec_level.params
    mode: str = cast(str, p["mode"])

    solver = REGISTRY.solver("math.evaluate_letter_expression")
    for _ in range(200):
        expr_str, given_display = _draw_expr(mode, cast("dict[str, object]", p), rng)
        sol = cast(Solution, solver(expr_str, mode))
        assert isinstance(sol.answer, SymbolicAnswer)
        simplified = sympy.sympify(sol.answer.srepr)
        # 答えは一次式（x を残す＝定数に退化していない）で、かつ与式に部分文字列として漏れない。
        if simplified.free_symbols and not _leaks(sol.answer.display, given_display):
            expected = sympy.expand(sympy.sympify(expr_str))
            assert sol.answer.srepr == sympy.srepr(expected), (
                f"double-solve 不一致: 構成 {expected} != solver 再計算 {sol.answer.srepr}"
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
                params={"expr_str": expr_str, "mode": mode, "given_disp": given_display},
                given={"expression": given_display},
                sub_questions=[sub_question],
                visual_plan=None,
                provenance=Provenance(recipe="math.compute_letter_expression"),
            )
    raise ValueError(f"非退化・非漏洩の一次式を構成できず（mode={mode!r}）")


__all__ = ["compute_letter_expression"]
