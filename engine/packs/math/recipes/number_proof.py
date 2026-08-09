"""文字式で数の性質を説明するセルの recipe（form: proof・g2_l7 / g2_l8 / g3_l13）。

**問題を手で書かない。** 命題は `solvers.number_proof` の「型＋パラメータ」で持ち、
式変形と「示すべき性質」は sympy に計算させる。この recipe がやるのは
  1. family が許した型の中から1つ引き、文字と軸の値を引く
  2. 組めたか（＝恒等式として成り立ち、数値代入でも成り立つか）を確かめる
  3. 問題文に出す「命題」と、誘導ありなら「書き出し」を組む
だけである。命題そのものはコード中のどこにも文字列として書かれていない
（`derive_goal` が展開した式から「11 の倍数」「奇数」を導く）。

**Lv 差は誘導の有無**（台帳の desc）。誘導あり（Lv2）は「どう文字でおくか」を
問題文が与えるので、説明は式を書き出すところから始まる。誘導なし（Lv3）は
文字のおき方と表し方を自分で構成する2行が先頭に付く。この差が
  - given のキー（Lv2 は premises+conclusion / Lv3 は conclusion のみ）
  - steps の op 列（4 手 / 6 手）
の両方に出る＝ fingerprint が変わる（level_sep の材料）。**op 列が同じだと
level_sep が落ちる**ので、ここを揃えてはいけない。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import (
    MR,
    CellContext,
    ProofAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.solvers.number_proof import (
    TEMPLATES,
    build_proposition,
    guided_premises,
)

_MAX_TRIES = 24

# **family が使う概念IDはすべてここに載せる。** 載せ忘れると lint R6 が落ち、
# check_cell は通るのに capabilities に出ない（台帳に載らない）——既知の罠。
_NUMBER_PROOF_CONCEPTS = [
    # g2_l7 偶数・奇数・連続する整数
    "polynomial.proof_consecutive_integers",
    "polynomial.proof_parity_operation",
    # g2_l8 2けたの自然数など（位取りの文字化）
    "polynomial.proof_two_digit_swap",
    "polynomial.proof_digit_sum_relation",
    # g3_l13 展開・因数分解を使う説明
    "polynomial.proof_expand_number_property",
    "polynomial.proof_factor_to_square",
]


def _draw_letters(pool: list[str], k: int, rng: Rng) -> tuple[str, ...]:
    """相異なる k 文字を引き、**辞書順に並べて**返す。

    並べ替えるのは見た目のためではない。sympy の既定の表示順が
    「同次数なら辞書順」なので、手で組んだ式（10a + b）と展開結果（11a + 11b）で
    文字の並びが食い違わないようにするために要る。
    """
    chosen: list[str] = []
    for _ in range(200):
        if len(chosen) >= k:
            break
        c = str(draw([x for x in pool if x not in chosen], rng))
        chosen.append(c)
    if len(chosen) < k:
        raise ValueError(f"letter_pool から {k} 文字を引けなかった: {pool!r}")
    return tuple(sorted(chosen))


@register_recipe("math.number_property_proof", provides_concepts=_NUMBER_PROOF_CONCEPTS)
def number_property_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """文字式による数の性質の説明（型＋パラメータを引いて命題を組む）。"""
    p = ctx.spec_level.params
    guided = bool(p.get("guided", False))
    pool = [str(x) for x in cast("list[str]", p["letter_pool"])]
    prop_set = [str(x) for x in cast("list[str]", p["proposition_set"])]

    for _ in range(_MAX_TRIES):
        prop_id = str(draw(prop_set, rng))
        tpl = TEMPLATES[prop_id]
        letters = _draw_letters(pool, tpl.n_letters, rng)
        numbers = {ax: int(draw(list(vals), rng)) for ax, vals in tpl.axes.items()}
        prop = build_proposition(prop_id, letters, numbers)
        if prop is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは型の定義が悪いとき
        raise ValueError(f"{prop_set}: 検証を通る命題を引けなかった")

    # 独立ソルバで説明をもう一度組み立てる（checker が呼ぶのと同じ経路）。
    solver = REGISTRY.solver("math.number_property_proof")
    sol = cast(
        Solution,
        solver(prop.prop_id, list(prop.letters), dict(prop.numbers), guided),
    )
    assert isinstance(sol.answer, ProofAnswer)
    expected_ops = (
        ("form_expression", "expand_expression", "rewrite_to_goal_form", "conclude_property")
        if guided
        else (
            "choose_letters", "represent_numbers", "form_expression",
            "expand_expression", "rewrite_to_goal_form", "conclude_property",
        )
    )
    assert tuple(s.op for s in sol.steps) == expected_ops, "op 列が Lv 宣言と食い違った"
    # **問題文の命題と、説明の結論が同じであること。** ここが崩れると「差が2である
    # 2つの整数…」と問うているのに説明が「差が6…」で始まる（実際に起きた）。
    # given は recipe の prop から、答えは solver の組み直しから来るので、両者を突き合わせる。
    assert f"したがって、{prop.statement}。" in sol.answer.lines[-1].claim, (
        "問題文に出す命題と、説明の結論が食い違っている"
    )

    given = {"conclusion": prop.statement}
    if guided:
        # 誘導あり: 「どう文字でおくか」と「この2数の和は……」までを問題文が与える。
        given["premises"] = guided_premises(prop)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="proof_text",
        answer=sol.answer,
        # 説明の各行がそのまま steps になる（採点粒度＝行）。空にすると op 列が消え、
        # Lv 間で fingerprint が同じになって level_sep が壊れる。
        steps=sol.steps,
        concept_tags=list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
        cause_tags=list(ctx.spec_level.cause_tags),
    )

    return MR(
        signature=ctx.spec_level.signature,
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        # checker が同じ命題を組み直せるだけの情報。**答え（説明文）は入れない。**
        params={
            "prop_id": prop.prop_id,
            "letters": list(prop.letters),
            "numbers": dict(prop.numbers),
            "guided": guided,
        },
        given=given,
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.number_property_proof"),
    )


__all__ = ["number_property_proof_recipe"]
