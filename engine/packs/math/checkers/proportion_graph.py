"""比例・反比例の **グラフ**（graph_table）double_solve checker（G-Q1 が呼ぶ・§6.2）。

G-Q1 は `f"{mr.provenance.recipe}.double_solve"` で checker を引き、MR の params に残った
「問題を定義する値」だけから独立ソルバで解き直す（recipe の内部状態は見ない）。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.read_coordinate_on_plane.double_solve")
def double_solve_read_coordinate_on_plane(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_coordinate_components")
    return cast(Solution, solver(mr.params["x0"], mr.params["y0"]))


@register_checker("math.reflect_point_on_plane.double_solve")
def double_solve_reflect_point_on_plane(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.reflect_point_pair")
    return cast(Solution, solver(mr.params["x0"], mr.params["y0"]))


@register_checker("math.read_proportion_graph_value.double_solve")
def double_solve_read_proportion_graph_value(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_value_on_proportion_graph")
    return cast(Solution, solver(mr.params["a"], mr.params["x0"]))


@register_checker("math.draw_proportion_graph.double_solve")
def double_solve_draw_proportion_graph(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.draw_proportion_graph_features")
    return cast(Solution, solver(mr.params["a"], mr.params["p"], mr.params["q"]))


@register_checker("math.compare_proportion_graphs.double_solve")
def double_solve_compare_proportion_graphs(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.compare_proportion_graphs")
    return cast(Solution, solver(mr.params["a1"], mr.params["a2"], mr.params["a3"]))


@register_checker("math.read_lattice_point_on_proportion_graph.double_solve")
def double_solve_read_lattice_point_on_proportion_graph(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_lattice_point_on_proportion")
    return cast(Solution, solver(mr.params["a"], mr.params["x0"]))


@register_checker("math.read_hyperbola_graph_value.double_solve")
def double_solve_read_hyperbola_graph_value(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_value_on_hyperbola_graph")
    return cast(Solution, solver(mr.params["a"], mr.params["x0"]))


@register_checker("math.draw_hyperbola_from_table.double_solve")
def double_solve_draw_hyperbola_from_table(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.draw_hyperbola_features")
    return cast(Solution, solver(mr.params["a"], mr.params["xs"]))


@register_checker("math.compare_hyperbolas.double_solve")
def double_solve_compare_hyperbolas(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.compare_hyperbolas")
    return cast(Solution, solver(mr.params["a1"], mr.params["a2"], mr.params["a3"]))


@register_checker("math.read_lattice_point_on_hyperbola_graph.double_solve")
def double_solve_read_lattice_point_on_hyperbola_graph(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_lattice_point_on_hyperbola")
    return cast(Solution, solver(mr.params["a"], mr.params["x0"]))


@register_checker("math.graph_situation_proportion.double_solve")
def double_solve_graph_situation_proportion(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_situation_value_from_graph")
    return cast(Solution, solver(mr.params["a"], mr.params["x_q"]))


@register_checker("math.graph_two_plans_crossover.double_solve")
def double_solve_graph_two_plans_crossover(mr: MR) -> Solution:
    solver = REGISTRY.solver("math.read_plan_crossover_from_graph")
    return cast(Solution, solver(mr.params["pa"], mr.params["pb"], mr.params["fixed"]))


__all__: list[str] = []
