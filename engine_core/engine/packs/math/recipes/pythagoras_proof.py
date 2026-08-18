"""三平方の定理の証明／その逆による説明の recipe（form: proof・g3_l51 / g3_l52）。

**問題を手で書かない。** どちらの recipe も
  1. 型（どの図で分けるか／どの場面か）とパラメータ（文字・頂点の記号・3辺）を引く
  2. `solvers.pythagoras_proof` に組み立てさせる（面積の恒等式と数値検算を通ったものだけ返る）
  3. 問題文に出す「与えられたもの」と「示すこと」を、組み上がった証明から取り出す
だけをやる。a² + b² = c² を人が書き下す場面はどこにもない。

## g3_l51（定理の証明・`math.pythagoras_area_proof`）
**Lv 差は誘導の有無**（台帳の desc）。
  Lv3（guided=True）… 図の並べ方と内側の図形の記号を問題文が与える。証明は面積を
                       2通りに表すところから始まる6手。
  Lv4（guided=False）… 図も分け方も自分で立てる。「どの図にするか」「並べたら辺が
                       どう分かれるか」「内側は何の図形か」の3手が**先頭に付いて9手**。
op 列が 6 手と 9 手で変わる＝ fingerprint が変わる（level_sep の材料）。
**ここを揃えてはいけない。**

## g3_l52（定理の逆・`math.pythagoras_converse_proof`）
ピタゴラス数から3辺を引き、場面（三角形／四角形の対角線／運動場）に載せる。
台帳 Lv3 の example が四角形の対角線の型なので、その型を場面の1つとして持っている。

## dup_rate
面積証明   型5 × 文字の組 120（10文字から3つ・辞書順）× 記号の組 5 × 向き 2 = 6000
（誘導なしは記号を使わないので 1200）。逆   場面3 × 記号の組 6 × ピタゴラス数 43 ×
入れ替え 2 = 1548。閾 0.20 に要る 250 通りに対して十分広い。
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
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw
from engine.packs.math.visuals.quadrilateral_figure import (
    plain_triangle_svg,
    quadrilateral_with_one_diagonal_svg,
)
from engine.packs.math.visuals.similarity_figure import pythagoras_proof_svg
from engine.packs.math.solvers.pythagoras_proof import (
    AREA_PROOF_IDS,
    CONVERSE_NAME_SETS,
    TRIPLES,
    FigureNames,
    build_area_proof,
    build_converse_case,
)

# 辺につける文字。**3つ引いて辞書順に並べる**（見た目のためではなく、sympy の既定の
# 表示順が辞書順なので、手で組んだ式と展開結果で文字の並びが食い違わないようにする）。
_SIDE_LETTERS = ("a", "b", "c", "m", "n", "p", "q", "x", "y", "z")

# 頂点の記号（外側の四角形・内側の四角形）。**2つの組は文字が重ならないこと**
# （台形では内側の組の先頭1文字を、辺上にとる点の名前として使う）。
_FIGURE_NAME_SETS = (
    ("ABCD", "EFGH"),
    ("EFGH", "IJKL"),
    ("IJKL", "MNOP"),
    ("PQRS", "TUVW"),
    ("KLMN", "WXYZ"),
)

# 引き直しの上限。`build_area_proof` / `build_converse_case` は検証（恒等式・数値）に
# 落ちると None を返すので、有界回数だけ引き直す（使い切るのは型が壊れたとき）。
_MAX_TRIES = 200

# **family が使う概念IDはすべてここに載せる。** 載せ忘れると lint R6 が落ち、
# check_cell は通るのに capabilities に出ない（台帳に載らない）——既知の罠。
_AREA_CONCEPTS = [
    "pythagorean.prove_theorem_by_area",
    "pythagorean.construct_area_proof",
]
_CONVERSE_CONCEPTS = ["pythagorean_converse.explain_right_angle"]


def _draw_side_letters(rng: Rng) -> tuple[str, str, str]:
    """相異なる3文字を引いて辞書順に返す（直角をはさむ2辺・斜辺の順になる）。"""
    chosen: list[str] = []
    while len(chosen) < 3:
        chosen.append(str(draw([x for x in _SIDE_LETTERS if x not in chosen], rng)))
    a, b, c = sorted(chosen)
    return a, b, c


@register_recipe("math.pythagoras_area_proof", provides_concepts=_AREA_CONCEPTS)
def pythagoras_area_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """面積を2通りに表して三平方の定理を証明する（誘導あり Lv3／誘導なし Lv4）。"""
    p = ctx.spec_level.params
    guided = bool(p["guided"])
    proof_ids = [str(x) for x in cast("list[str]", p["proof_set"])]

    for _ in range(_MAX_TRIES):
        proof_id = str(draw(proof_ids, rng))
        letters = _draw_side_letters(rng)
        # 誘導なしでは図の記号を使わない（証明が図形を言葉で呼ぶ）。
        name_pair = (
            tuple(str(x) for x in cast("tuple[str, str]", draw(list(_FIGURE_NAME_SETS), rng)))
            if guided
            else None
        )
        flip = bool(draw({"int_range": [0, 1]}, rng))
        names = FigureNames(outer=name_pair[0], inner=name_pair[1]) if name_pair else None
        proof = build_area_proof(proof_id, letters, names, flip=flip)
        if proof is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは型が壊れたとき
        raise ValueError(f"{proof_ids}: 検証を通る面積証明を引けなかった（guided={guided}）")

    # 独立ソルバで筋道をもう一度組み立てる（checker が呼ぶのと同じ経路）。
    solver = REGISTRY.solver("math.pythagoras_area_proof")
    sol = cast(
        Solution,
        solver(proof.proof_id, list(proof.letters), list(name_pair) if name_pair else None,
               flip, guided),
    )
    assert isinstance(sol.answer, ProofAnswer)
    assert len(sol.steps) == (6 if guided else 9), "op 列の長さが Lv 宣言と食い違った"

    # **問題文に出す図と、params から組み直した図が同じであること。** given はここで
    # 作った proof から、答えは params 経由の組み直しから来るので、両者がずれると
    # 「問題文と模範解答が別の図」になる。G-Q1 は両方とも組み直し側を見るので
    # 捕まえられない。だから生成側で閉じる。
    rebuilt = build_area_proof(proof.proof_id, proof.letters, names, flip=flip)
    assert rebuilt is not None, "params から面積証明を組み直せない"
    assert rebuilt.guided_setup == proof.guided_setup, "問題文に出す図と、組み直した図が食い違っている"

    if guided:
        # 誘導あり: 並べ方も、内側の図形の記号も問題文が与える（答えが使う記号を
        # すべて問題文の側で名づけておく）。
        premises = proof.guided_setup
    else:
        # 誘導なし: 与えるのは「どの辺をどの文字で呼ぶか」だけ。
        a, b, c = proof.letters
        premises = f"直角をはさむ2辺の長さが {a}、{b}、斜辺の長さが {c} である直角三角形"

    # ★**この配置は図でしか伝わらない。** 「合同な直角三角形4つを、斜辺がそれぞれ
    # 1辺になるように並べて…内側にできる四角形は1辺 q-a の正方形になる」を、
    # 頭の中だけで組み立てるのは中学生には無理がある（点検でも「図がなければ
    # 読解できない」と挙がった 13 問）。
    figure_svg = pythagoras_proof_svg(
        proof.proof_id, proof.letters,
        name_pair[0] if name_pair else None,
        name_pair[1] if name_pair else None,
    )
    fig_labels = [*proof.letters]
    if name_pair:
        fig_labels += [*name_pair[0], *name_pair[1]]

    sub_question = SubQuestionMR(
        label="(1)",
        asked="proof_text",
        answer=sol.answer,
        # 証明の各行がそのまま steps になる（採点粒度＝行）。空にすると op 列が消え、
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
        # checker が同じ図を組み直せるだけの情報。**答えは入れない。**
        params={
            "proof_id": proof.proof_id,
            "letters": list(proof.letters),
            "names": list(name_pair) if name_pair else None,
            "flip": flip,
            "guided": guided,
        },
        given={"premises": premises, "conclusion": proof.conclusion_display},
        context_slots={"figure_svg": figure_svg},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=fig_labels,
            elements=[VisualElement(kind="square", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.pythagoras_area_proof"),
    )


def _converse_figure(case: object, names: str) -> tuple[str, list[str]]:
    """三平方の定理の逆の場面の図と、図に出る文字。

    場面は3種類（四角形＋対角線／三角形／実生活の3点）で、四角形だけ頂点が4つ。
    長さは問題文にあるものをそのまま書き入れる（本文から拾う——場面の型ごとに
    値の持ち方が違うので、ここでは名前と長さの対だけを取り出す）。
    """
    import re as _re

    premises = str(getattr(case, "premises", ""))
    pairs = _re.findall(r"([A-Z]{2})\s*=\s*(\d+)\s*(cm|m)", premises)
    labels = [f"{v}{u}" for _, v, u in pairs]
    if len(names) >= 4:
        quad = names[:4]
        seg = [[p[0], p[1], f"{v}{u}"] for p, v, u in pairs]
        return quadrilateral_with_one_diagonal_svg(quad, seg), [*quad, *labels]
    tri = names[:3]
    seg = [[p[0], p[1], f"{v}{u}"] for p, v, u in pairs]
    return plain_triangle_svg(tri, seg), [*tri, *labels]


@register_recipe("math.pythagoras_converse_proof", provides_concepts=_CONVERSE_CONCEPTS)
def pythagoras_converse_proof_recipe(ctx: CellContext, rng: Rng) -> MR:
    """三平方の定理の逆を用いて、ある角が直角であることを説明する（g3_l52 Lv3）。"""
    p = ctx.spec_level.params
    contexts = [str(x) for x in cast("list[str]", p["context_set"])]

    for _ in range(_MAX_TRIES):
        context = str(draw(contexts, rng))
        names = str(draw(list(CONVERSE_NAME_SETS), rng))
        triple_index = int(draw({"int_range": [0, len(TRIPLES) - 1]}, rng))
        swap = bool(draw({"int_range": [0, 1]}, rng))
        case = build_converse_case(context, names, triple_index, swap, 0)
        if case is not None:
            break
    else:  # pragma: no cover - 有界リトライを使い切るのは生成器が壊れたとき
        raise ValueError(f"{contexts}: 検証を通る3辺を引けなかった")

    solver = REGISTRY.solver("math.pythagoras_converse_proof")
    sol = cast(Solution, solver(context, names, triple_index, swap))
    assert isinstance(sol.answer, ProofAnswer)
    assert len(sol.steps) == 5, "op 列の長さが宣言と食い違った"

    rebuilt = build_converse_case(context, names, triple_index, swap, 0)
    assert rebuilt is not None, "params から場面を組み直せない"
    assert rebuilt.premises == case.premises, "問題文に出す場面と、組み直した場面が食い違っている"

    # ★**直角の印は描かないし、直角に見える形にも描かない。** これは
    # 「∠PQR が直角であること」を**示す**問題で、図に直角を描いたら結論を
    # 図に書いたことになる。3辺（と対角線）の長さだけを書き入れる。
    figure_svg, fig_labels = _converse_figure(case, names)

    sub_question = SubQuestionMR(
        label="(1)",
        asked="proof_text",
        answer=sol.answer,
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
        params={
            "context": context,
            "names": names,
            "triple_index": triple_index,
            "swap": swap,
        },
        context_slots={"figure_svg": figure_svg},
        given={"premises": case.premises, "conclusion": case.conclusion},
        sub_questions=[sub_question],
        visual_plan=VisualPlan(
            style="figure", labels=fig_labels,
            elements=[VisualElement(kind="triangle", attrs={"role": "given"})],
        ),
        provenance=Provenance(recipe="math.pythagoras_converse_proof"),
    )


__all__ = ["pythagoras_area_proof_recipe", "pythagoras_converse_proof_recipe"]
