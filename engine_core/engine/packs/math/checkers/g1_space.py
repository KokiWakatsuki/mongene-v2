"""C8 g1 空間図形クラスタ（g1_l47/l48 の knowledge Lv2）の double_solve checker（§4.1）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に
残った「問題を定義する値」だけから独立ソルバで解き直す。1レベルに複数 mode がある
セルは params["mode"] で dispatch する（op 列は mode 間で共通＝G-FP 安定）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.judge_polyhedron_claim.double_solve")
def double_solve_judge_polyhedron_claim(mr: MR) -> Solution:
    mode = mr.params["mode"]
    if mode == "element_count":
        solver = REGISTRY.solver("math.judge_polyhedron_element_count")
        return cast(
            Solution,
            solver(
                mr.params["n"],
                mr.params["solid_type"],
                mr.params["quantity"],
                mr.params["candidate"],
            ),
        )
    solver = REGISTRY.solver("math.judge_regular_polyhedron_condition")
    return cast(Solution, solver(mr.params["shape_sides"], mr.params["count_at_vertex"]))


@register_checker("math.judge_solid_position.double_solve")
def double_solve_judge_solid_position(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.judge_solid_position_relation")
    return cast(
        Solution,
        solver(mr.params["labels"], mr.params["mode"], mr.params["first"], mr.params["second"]),
    )
