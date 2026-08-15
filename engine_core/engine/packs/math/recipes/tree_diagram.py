"""樹形図に整理するセルの recipe（Phase E 端物・g2_l52 / g2_l53 の graph_table Lv1）。

2セルの違いは**もとに戻すかどうか**だけ:
  - g2_l52（硬貨）: 2枚を同時に投げる＝毎回 表/裏 の2通り（replace=True）
  - g2_l53（玉）  : 1個ずつ続けて取り出す＝1回目に取った玉は2回目に無い（replace=False）
この1点が樹形図の枝の分かれ方そのものなので、scenario_kind ではなく params の
`with_replacement` で素直に分ける。

問題図は題材の絵（硬貨／玉）だけで、樹形図は描かない（それが答え）。
"""
from __future__ import annotations

from typing import Any, cast

from engine.core.contracts import (
    MR,
    CellContext,
    GraphAnswer,
    Provenance,
    Solution,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many
from engine.packs.math.visuals.tree_diagram import render_tree_diagram_svg

_TREE_CONCEPTS = ["counting.tree_diagram_coins", "counting.tree_diagram_draws"]


def _draw_distinct(candidates: list[Any], rng: Rng, k: int) -> list[str]:
    idxs = draw_many({"int_range": [0, len(candidates) - 1], "distinct": ["value"]}, rng, k=k)
    return [str(candidates[int(i)]) for i in idxs]


def _draw_from(candidates: list[Any], rng: Rng) -> str:
    return str(candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))])


@register_recipe("math.tree_diagram", provides_concepts=_TREE_CONCEPTS)
def tree_diagram_recipe(ctx: CellContext, rng: Rng) -> MR:
    """起こりうる場合を樹形図に整理する（g2_l52 / g2_l53 の graph_table Lv1・answer-first）。"""
    p = ctx.spec_level.params
    with_replacement = bool(p["with_replacement"])
    draws = int(p["draws"])

    if with_replacement:
        # 硬貨: 表と裏の2通りが毎回起こる。金種と人名は答えに効かない surface
        # （場合の数は枚数だけで決まる）だが、これが無いと組合せ数が足りず dup が通らない。
        faces = [str(v) for v in p["face_names"]]
        kinds = _draw_distinct(list(p["coin_candidates"]), rng, draws)
        person = _draw_from(list(p["person_candidates"]), rng)
        items = faces
        subject_labels = kinds
        subject_caption = f"{person}さんが同時に投げる硬貨"
        statement = (
            f"{person}さんが{'と'.join(kinds)}の{draws}枚の硬貨を同時に投げる。"
            f"表と裏の出方として起こりうる場合を、すべて樹形図に表せ"
        )
        params_extra: dict[str, Any] = {"coin_kinds": kinds, "person": person}
    else:
        # 玉: 1個ずつ続けて取り出す（もとに戻さない）。
        colors = _draw_distinct(list(p["color_candidates"]), rng, int(p["item_count"]))
        # 入れ物|品物|助数詞（カードは「枚」・玉は「個」——助数詞がずれると日本語が壊れる）。
        container, item, counter = _draw_from(list(p["container_candidates"]), rng).split("|")
        items = colors
        subject_labels = colors
        subject_caption = f"{container}の中に入っている{item}"
        statement = (
            f"{container}の中に、"
            + "、".join(f"{c}い{item}が1{counter}" for c in colors)
            + f"入っている。この{container}から{item}を1{counter}ずつ続けて{draws}{counter}"
            "取り出すとき、"
            "取り出し方として起こりうる場合を、すべて樹形図に表せ"
        )
        params_extra = {"colors": colors, "container": container, "item": item,
                        "counter": counter}

    sol = cast(
        Solution, REGISTRY.solver("math.tree_diagram_outcomes")(items, draws, with_replacement)
    )
    assert isinstance(sol.answer, GraphAnswer)
    paths = [f.display.replace("、", "-") for f in sol.answer.features if f.kind == "outcome"]

    params: dict[str, Any] = {
        "items": list(items),
        "draws": draws,
        "with_replacement": with_replacement,
        "paths": paths,
        "subject_labels": subject_labels,
        "subject_caption": subject_caption,
        **params_extra,
    }
    answer = GraphAnswer(
        features=sol.answer.features,
        solution_svg_ref=render_tree_diagram_svg(params),
    )
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0, params=params,
        given={"condition": statement},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="draw_tree_diagram", answer=answer, steps=sol.steps,
                concept_tags=list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=VisualPlan(
            style="plane",
            labels=[*subject_labels, subject_caption],
            # 問題図は題材の絵まで（樹形図は答えなので描かない）。
            elements=[VisualElement(kind="subject_given", attrs={})],
        ),
        provenance=Provenance(recipe="math.tree_diagram"),
    )
