"""仮定と結論の証明・反例による否定の recipe（form: proof・g2_l38）。

**問題を手で書かない。** 命題は `solvers.conditional_proof` の「型＋パラメータ」で持ち、
真偽の判定と反例の探索はコードがやる。この recipe がやるのは
  1. family が許した型の中から1つ引き、文字と軸の値を引く
  2. そのレベルが要る真偽（Lv2 は正しい命題だけ／Lv3 は正しい命題も正しくない命題も）
     に合うまで、有界回数だけ引き直す
  3. 問題文に出す「命題」と、誘導ありなら「〜とおいて」を組む
だけである。

**Lv 差は誘導の有無と、真偽の判断が先に来るかどうか**（台帳の desc）。
  Lv2（mode=prove）… 文字のおき方を問題文が与える。証明は仮定を式で書くところから
                      始まる4手（state_hypothesis → … → conclude_property）。
  Lv3（mode=judge） … 誘導なし。**真偽の判断が先頭に付いて5手**になり、正しければ
                      証明、正しくなければ反例1つで閉じる。
この差が given のキー（Lv2 は premises+conclusion / Lv3 は conclusion のみ）と
steps の op 列の両方に出る＝ fingerprint が変わる（level_sep の材料）。
**op 列が同じだと level_sep が落ちる**ので、ここを揃えてはいけない。

逆に Lv3 の**中**では、正しい命題の枝と正しくない命題の枝が**同じ op 列**を通る。
同一 signature で op 列が揺れると fp が seed ごとに変わって G-FP が落ちるためで、
「判断 → 表し方を決める → 結論の数を作る → 結論を確かめる → 結論づける」という
共通の骨格に、証明と反例の両方を載せてある。
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
from engine.packs.math.solvers.conditional_proof import (
    TEMPLATES,
    build_proposition,
    guided_premises,
)

# 引き直しの上限。真の命題は軸の直積の1割ほどしかないので、期待回数（十数回）に対して
# 十分に大きくとる（使い切るのは軸の設計が壊れたとき）。
_MAX_TRIES = 400

# **family が使う概念IDはすべてここに載せる。** 載せ忘れると lint R6 が落ち、
# check_cell は通るのに capabilities に出ない（台帳に載らない）——既知の罠。
_CONDITIONAL_PROOF_CONCEPTS = [
    "proof_logic.prove_conditional_statement",
    "proof_logic.judge_truth_by_counterexample",
]


def _draw_letters(pool: list[str], n_subject: int, n_aux: int, rng: Rng) -> tuple[str, ...]:
    """相異なる文字を引き、命題文に出る文字と「整数とおく」文字に分けて返す。

    それぞれの組の中では**辞書順に並べる**。見た目のためではなく、sympy の既定の
    表示順が「同次数なら辞書順」なので、手で組んだ表し方（m = 2s、n = 2t + 1）と
    展開結果（2s + 2t + 1）で文字の並びが食い違わないようにするために要る。
    """
    chosen: list[str] = []
    for _ in range(200):
        if len(chosen) >= n_subject + n_aux:
            break
        chosen.append(str(draw([x for x in pool if x not in chosen], rng)))
    if len(chosen) < n_subject + n_aux:
        raise ValueError(f"letter_pool から {n_subject + n_aux} 文字を引けなかった: {pool!r}")
    subjects = sorted(chosen[:n_subject])
    aux = sorted(chosen[n_subject:])
    return (*subjects, *aux)


@register_recipe(
    "math.conditional_statement_proof", provides_concepts=_CONDITIONAL_PROOF_CONCEPTS
)
def conditional_statement_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """仮定と結論の証明／反例による否定（型＋パラメータを引いて命題を組む）。"""
    p = ctx.spec_level.params
    mode = str(p["mode"])
    pool = [str(x) for x in cast("list[str]", p["letter_pool"])]
    prop_set = [str(x) for x in cast("list[str]", p["proposition_set"])]

    # Lv2 は「正しい命題を証明する」だけ。Lv3 は真偽の判断が問いなので、正しい命題と
    # 正しくない命題の**両方**が出るようにする。**引き直しの外で1回だけ決める**のが要点で、
    # ループの中で引くと「軸の直積の中で正しい命題は1割ほどしかない」ぶんだけ偽に偏る
    # （中で引いた実装では 20 問中 19 問が偽になった）。
    want_true = True if mode == "prove" else bool(draw({"int_range": [0, 1]}, rng))

    for _ in range(_MAX_TRIES):
        prop_id = str(draw(prop_set, rng))
        tpl = TEMPLATES[prop_id]
        letters = _draw_letters(pool, tpl.n_subject, tpl.n_aux, rng)
        numbers = {ax: int(draw(list(vals), rng)) for ax, vals in tpl.axes.items()}
        prop = build_proposition(prop_id, letters, numbers, want_true=want_true)
        if prop is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは軸の設計が悪いとき
        raise ValueError(f"{prop_set}: 検証を通る命題を引けなかった（mode={mode}）")

    # 独立ソルバで筋道をもう一度組み立てる（checker が呼ぶのと同じ経路）。
    solver = REGISTRY.solver("math.conditional_statement_proof")
    sol = cast(
        Solution, solver(prop.prop_id, list(prop.letters), dict(prop.numbers), mode)
    )
    assert isinstance(sol.answer, ProofAnswer)
    expected_ops = (
        ("state_hypothesis", "form_conclusion_expression", "rewrite_to_goal_form",
         "conclude_property")
        if mode == "prove"
        else ("judge_truth", "set_representation", "form_conclusion_expression",
              "test_conclusion", "conclude_judgement")
    )
    assert tuple(s.op for s in sol.steps) == expected_ops, "op 列が Lv 宣言と食い違った"

    # **問題文に出す命題と、params から組み直した命題が同じであること。** given は
    # ここで作った prop から、答えは params 経由の組み直しから来るので、両者が
    # ずれると「問題文と模範解答が別の命題」になる（number_proof で実際に起きた）。
    # G-Q1 は両方とも組み直し側を見るので捕まえられない。だから生成側で閉じる。
    rebuilt = build_proposition(prop.prop_id, prop.letters, prop.numbers)
    assert rebuilt is not None, "params から命題を組み直せない"
    assert rebuilt.statement == prop.statement, "問題文に出す命題と、組み直した命題が食い違っている"
    assert rebuilt.is_true == prop.is_true, "params から組み直すと真偽が変わる"

    given = {"conclusion": prop.statement}
    if mode == "prove":
        # 誘導あり: 「何をどう文字でおくか」を問題文が与える。
        given["premises"] = guided_premises(prop)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="proof_text",
        answer=sol.answer,
        # 証明（反例）の各行がそのまま steps になる（採点粒度＝行）。空にすると
        # op 列が消え、Lv 間で fingerprint が同じになって level_sep が壊れる。
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
        # checker が同じ命題を組み直せるだけの情報。**答えも真偽も入れない**
        # （真偽まで params に書くと、checker は判定をやり直さずに写すだけになる）。
        params={
            "prop_id": prop.prop_id,
            "letters": list(prop.letters),
            "numbers": dict(prop.numbers),
            "mode": mode,
        },
        given=given,
        sub_questions=[sub_question],
        visual_plan=None,
        provenance=Provenance(recipe="math.conditional_statement_proof"),
    )


__all__ = ["conditional_statement_proof_recipe"]
