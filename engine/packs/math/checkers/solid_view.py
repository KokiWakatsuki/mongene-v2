"""回転体の double_solve checker（G-Q1 が呼ぶ・§6.2）。

3セル（g1_l49.graph_table Lv1/Lv2/Lv3）を1つの checker が賄う。recipe が
`math.solid_of_revolution` 1つに集約されているので checker 名も1つで足りる。

独立性: params が持つのは**問題図と本文が与えているもの**（元の平面図形の種類・
軸にする辺の長さ・もう一方の辺の長さ）だけで、答え（できる立体の名前・底面の半径・
高さ・切り口の形）は入っていない。checker はそこから solver を呼び直す。
返す Solution は params の `view` ではなく MR の signature ではなく——
**mode を params から読まず、solver を mode ごとに選ぶ**ために、
recipe が params に残した `axis_len`/`other_len`/`shape` と、
level の signature ではなく family spec の mode を使う必要があるが、
mode は spec_level.params にあり MR には無い。そこで asked と答えの型から
一意に決まる形にしてある（read_solid=名前／draw_solid かつ features の先頭が
solid_name なら見取図／section_shape なら断面）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, GraphAnswer, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solid_of_revolution.double_solve")
def double_solve_solid_of_revolution(mr: MR) -> Solution:
    p = mr.params
    shape = str(p["shape"])
    axis_len, other_len = int(p["axis_len"]), int(p["other_len"])
    sq = mr.sub_questions[0]
    if sq.asked == "read_solid":
        return cast(Solution, REGISTRY.solver("math.solid_of_revolution_name")(shape))
    answer = sq.answer
    assert isinstance(answer, GraphAnswer)
    kinds = [f.kind for f in answer.features]
    if "section_shape" in kinds:
        return cast(
            Solution,
            REGISTRY.solver("math.solid_of_revolution_section")(shape, axis_len, other_len),
        )
    return cast(
        Solution,
        REGISTRY.solver("math.solid_of_revolution_sketch")(shape, axis_len, other_len),
    )


@register_checker("math.solid_projection.double_solve")
def double_solve_solid_projection(mr: MR) -> Solution:
    """投影図の3セル。params が持つのは立体の種類と寸法だけで、答え（立体の名前・
    立面図/平面図の形）は入っていない。checker は対応表を引き直して解き直す。
    """
    from engine.packs.math.solvers.solid_view import projection_shapes

    p = mr.params
    kind = str(p["solid_kind"])
    elev, plan = projection_shapes(kind)
    sq = mr.sub_questions[0]
    if sq.asked == "read_solid":
        return cast(Solution, REGISTRY.solver("math.solid_from_projection")(elev, plan))
    answer = sq.answer
    assert isinstance(answer, GraphAnswer)
    if "solid_name" in [f.kind for f in answer.features]:
        return cast(Solution, REGISTRY.solver("math.complete_projection")(plan, elev))
    return cast(
        Solution,
        REGISTRY.solver("math.projection_views_of_solid")(
            kind, p["base_len"], p["solid_height"]
        ),
    )


__all__ = ["double_solve_solid_of_revolution", "double_solve_solid_projection"]
