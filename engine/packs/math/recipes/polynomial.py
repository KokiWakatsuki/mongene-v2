"""多項式（式の計算）まわりの recipe（構成的生成・answer-first。実装設計 §6.1）。

recipe は「答え（または綺麗な中核値）を先に決め、問題を逆算する」登録済み関数。
乱数は `engine.core.rng.draw` / `draw_many` 以外で解釈しない（H8・§4.3.1）。構成した
答えは独立ソルバ（`engine.packs.math.solvers.polynomial`）で再計算し一致を確認する。

C2（数と式）クラスタの初セル: g2_l2.calculation（同類項をまとめる）Lv1/Lv2。
`linear.py` は並行編集中のため触らず、本ファイルに独立ヘルパ（_fmt_term 等）を
新設する（linear.py からの import は可・編集は不可）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw

_COMBINE_LIKE_TERMS_CONCEPTS_LV1 = ["polynomial.combine_like_terms_basic"]
_COMBINE_LIKE_TERMS_CONCEPTS_LV2 = ["polynomial.combine_like_terms_mixed"]


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    """spec_level.concept_tags が非空ならそれを、無ければ spec_family.concepts_default を使う。"""
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _effective_cause_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.cause_tags)


def _fmt_term(coef: int, var: str, *, is_first: bool) -> str:
    """1つの項 (係数, 文字) を教材表記にする（例: (4,"a")->"4a"／(-1,"x")->"-x"／先頭以外は "+ "/"- " を前置）。"""
    mag = abs(coef)
    mag_s = "" if mag == 1 else str(mag)
    body = f"{mag_s}{var}" if var else str(mag)
    if is_first:
        return f"-{body}" if coef < 0 else body
    return f"- {body}" if coef < 0 else f"+ {body}"


def _fmt_expr_from_terms(terms: list[tuple[int, str]]) -> str:
    """項の並び [(係数,文字), ...] を与式の表示形にする（例: "5x + 3x - 2x"）。"""
    return " ".join(_fmt_term(c, v, is_first=(i == 0)) for i, (c, v) in enumerate(terms))


def _sympy_str_from_terms(terms: list[tuple[int, str]]) -> str:
    """項の並びを sympy.sympify に渡せる文字列にする（solver への独立入力）。"""
    parts = [f"({c})*{v}" if v else f"({c})" for c, v in terms]
    return "+".join(parts)


def _domain_candidates(domain: dict[str, object]) -> list[int]:
    """`int_range`/`int_set` ドメインの候補値を明示列挙する（exclude 適用済み）。

    候補を陽に持つのは `_draw_term_group` が「まだ引いていない最後の1項について、
    集約結果の絶対値が既存の項の絶対値と衝突しないか」を候補ごとに検査してから
    `draw({"int_set": 有効候補}, rng)` する必要があるため（値ベースの exclude だけでは
    「候補 v 自身の絶対値と結果の絶対値が一致する」自己言及的な条件を表現できない）。
    """
    vals: list[int]
    if "int_range" in domain:
        bounds = cast("list[int]", domain["int_range"])
        lo, hi = int(bounds[0]), int(bounds[1])
        vals = list(range(lo, hi + 1))
    elif "int_set" in domain:
        vals = [int(v) for v in cast("list[int]", domain["int_set"])]
    else:
        raise ValueError(f"未対応の coeff_domain: {domain!r}")
    excl = {int(v) for v in cast("list[int]", domain.get("exclude", []))}
    return [v for v in vals if v not in excl]


def _draw_term_group(rng: Rng, domain: dict[str, object], n: int) -> list[int]:
    """文字1種ぶんの項の係数を n 個、1つずつ `draw` する（answer-first の逆算）。

    退化を構造的に排除する（draw 以外で乱数を解釈しない・候補を絞ってから draw する
    だけで、乱数の解釈経路そのものは draw に一本化されている）:
      1. 途中の部分和が 0 になる＝まとめる前に一部の項だけで同類項が消える。
      2. 最終的な集約結果（答え）の絶対値が 0/1 になる、または既存のどの項・最後の
         項自身の絶対値とも一致する＝答えの式がそのまま与式中に部分文字列として
         現れる G-Q5t 漏洩（例: "6x - 3x" の答え "3x" が与式中の "3x" と衝突。
         実装時に seed 3/9/41 等で実際に発覚した）。
    """
    cands = _domain_candidates(domain)
    terms: list[int] = []
    running = 0
    for i in range(n):
        is_last = i == n - 1
        if is_last:
            valid = []
            for v in cands:
                new_total = v + running
                if abs(new_total) in (0, 1):
                    continue
                if any(abs(t) == abs(new_total) for t in terms):
                    continue
                if abs(v) == abs(new_total):  # 最後の項自身との自己衝突
                    continue
                valid.append(v)
        else:
            valid = [v for v in cands if (v + running) != 0]
        val = int(draw({"int_set": valid}, rng))
        terms.append(val)
        running += val
    return terms


# ---------------------------------------------------------------------------
# math.combine_like_terms（g2_l2.calculation Lv1/Lv2 用）— C2 クラスタ初セル
# 同類項をまとめる。answer-first: 文字ごとに項の係数群を先に決め（合計≠0を構成で保証）、
# 見かけの与式を組み立てる。独立ソルバ `math.simplify_polynomial` で式全体を再計算し一致を確認。
#   Lv1 "single_var" : 1種の文字・2〜3項          op列 [group_like_terms, add_coefficients]
#   Lv2 "mixed_vars" : 2種の文字混在・a,b交互に配置 op列 [identify_like_terms, group_like_terms,
#                       add_coefficients]（先頭に選別の1手を足す＝level_sep）
# ---------------------------------------------------------------------------
@register_recipe("math.combine_like_terms", provides_concepts=(
    _COMBINE_LIKE_TERMS_CONCEPTS_LV1 + _COMBINE_LIKE_TERMS_CONCEPTS_LV2
))
def combine_like_terms(ctx: CellContext, rng: Rng) -> MR:
    """同類項をまとめて式を簡単にする（answer-first・calculation）。

    Lv1（mode="single_var"）: 1種の文字 x の項を n 個（2〜3）選ぶ。
    Lv2（mode="mixed_vars"）: 文字 a の項 n_a 個・文字 b の項 n_b 個を a,b交互に配置する
    （選別＝同類項の識別が必須になる構造）。
    """
    p = ctx.spec_level.params
    mode: str = p["mode"]
    coeff_domain = p["coeff_domain"]

    if mode == "single_var":
        n = int(draw(p["term_count_domain"], rng))
        coeffs = _draw_term_group(rng, coeff_domain, n)
        terms = [(c, "x") for c in coeffs]
        signature_extra = {"n": n}
        steps_ops = ["group_like_terms", "add_coefficients"]
    elif mode == "mixed_vars":
        n_a = int(draw(p["term_count_domain"], rng))
        n_b = int(draw(p["term_count_domain"], rng))
        coeffs_a = _draw_term_group(rng, coeff_domain, n_a)
        coeffs_b = _draw_term_group(rng, coeff_domain, n_b)
        # a, b を交互に配置（片方が尽きたら残りを続けて並べる）＝units.generated.yaml の
        # 例「4a − 7b − 6a + 2b + 3a」と同型の見かけ。
        terms = []
        ia = ib = 0
        while ia < len(coeffs_a) or ib < len(coeffs_b):
            if ia < len(coeffs_a):
                terms.append((coeffs_a[ia], "a"))
                ia += 1
            if ib < len(coeffs_b):
                terms.append((coeffs_b[ib], "b"))
                ib += 1
        signature_extra = {"n_a": n_a, "n_b": n_b}
        steps_ops = ["identify_like_terms", "group_like_terms", "add_coefficients"]
    else:
        raise ValueError(f"未知の mode: {mode!r}")

    expr_str = _sympy_str_from_terms(terms)
    given_display = _fmt_expr_from_terms(terms)

    solver = REGISTRY.solver("math.simplify_polynomial")
    sol = cast(Solution, solver(expr_str))
    assert isinstance(sol.answer, SymbolicAnswer)

    expected = sympy.expand(sympy.sympify(expr_str))
    assert sol.answer.srepr == sympy.srepr(expected), (
        f"double-solve 不一致: recipe が構成した式 {expected} != solver 再計算 {sol.answer.srepr}"
    )

    # steps は level_sep のためレベルごとに op 列を作り直す（solver の2手は共通コアとして
    # そのまま流用し、Lv2 のみ「同類項を見分ける」1手を先頭に足す）。narration に数字は書かない。
    steps: list[Step] = []
    if mode == "mixed_vars":
        steps.append(
            Step(
                op="identify_like_terms",
                args=[],
                result_srepr="",
                result_display="文字の部分が同じ項どうしを見分ける",
                narration="式の中から、文字の部分が同じ項（同類項）の組を見分ける。",
            )
        )
    steps.extend(sol.steps)
    assert [s.op for s in steps] == steps_ops

    sub_question = SubQuestionMR(
        label="(1)",
        asked="simplified_expr",
        answer=sol.answer,
        steps=steps,
        concept_tags=_effective_concept_tags(ctx),
        cause_tags=_effective_cause_tags(ctx),
    )

    mr_params: dict[str, object] = {
        "mode": mode,
        "terms": [[str(c), v] for c, v in terms],
        **{k: str(v) for k, v in signature_extra.items()},
    }

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,  # pipeline が上書きする
        params=mr_params,
        given={"expression": given_display},
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.combine_like_terms"),
    )


__all__ = [
    "combine_like_terms",
]
