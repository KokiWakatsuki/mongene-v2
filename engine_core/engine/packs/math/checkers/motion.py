"""動点まわりの double_solve checker（G-Q1 が呼ぶ・実装設計 §6.2・統合 §4.1）。"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.solve_moving_point_area.double_solve")
def double_solve_solve_moving_point_area(mr: MR) -> Solution:
    p = mr.params
    solver = REGISTRY.solver("math.solve_moving_point_area")
    return cast(Solution, solver(p["s"], p["v"], p["t"], p["mode"]))


@register_checker("math.draw_area_time_graph_segment.double_solve")
def double_solve_draw_area_time_graph_segment(mr: MR) -> Solution:
    # 問題パラメータ（a,b・変域端 seg_x_lo/seg_x_hi・開閉 closed_lo/closed_hi）だけから
    # 端点特徴を再計算する（g2_l23.graph_table の draw_segment と同じ solver を再利用）。
    p = mr.params
    solver = REGISTRY.solver("math.draw_segment_features")
    return cast(Solution, solver(
        sympy.sympify(p["a"]), sympy.sympify(p["b"]),
        sympy.sympify(p["seg_x_lo"]), sympy.sympify(p["seg_x_hi"]),
        bool(p["closed_lo"]), bool(p["closed_hi"]),
    ))


@register_checker("math.word_problem_moving_points_area.double_solve")
def double_solve_word_problem_moving_points_area(mr: MR) -> list[Solution]:
    """小問と同順の list[Solution]（(1)=面積の式・(2)=時刻）を返す（G-Q1 の多段規約）。

    渡すのは `numbers`＝**本文に出ている数値だけ**（速さ・与えられた面積）。
    答えの時刻も面積の式も params に無いので、解き直しが答えの読み直しにならない。
    1辺は面積の式にも時刻にも効かない（P・Q が辺の上にいる間の話）ので渡さない。
    """
    n = mr.params["numbers"]
    return [
        cast(Solution, REGISTRY.solver("math.express_moving_points_area")(n["speed"])),
        cast(
            Solution,
            REGISTRY.solver("math.solve_moving_points_area_time")(n["speed"], n["area"]),
        ),
    ]


@register_checker("math.word_problem_moving_point_all_times.double_solve")
def double_solve_word_problem_moving_point_all_times(mr: MR) -> Solution:
    n = mr.params["numbers"]
    solver = REGISTRY.solver("math.solve_moving_point_area_all_times")
    return cast(Solution, solver(n["side"], n["speed"], n["area"]))


@register_checker("math.word_problem_area_graph_and_times.double_solve")
def double_solve_word_problem_area_graph_and_times(mr: MR) -> list[Solution]:
    """小問と同順の list[Solution]（(1)=グラフの折れ点・(2)=時刻）を返す。

    渡すのは `numbers`＝本文に出ている数値（1辺・速さ・面積）だけ。折れ点の座標も
    答えの時刻も params に無いので、解き直しが答えの読み直しにならない。
    """
    n = mr.params["numbers"]
    return [
        cast(
            Solution,
            REGISTRY.solver("math.draw_three_interval_area_graph_features")(
                n["side"], n["speed"]
            ),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.solve_moving_point_area_all_times")(
                n["side"], n["speed"], n["area"]
            ),
        ),
    ]


@register_checker("math.word_problem_single_interval_area.double_solve")
def double_solve_word_problem_single_interval_area(mr: MR) -> list[Solution]:
    """(1)=面積の式・(2)=時刻。渡すのは本文に出ている 1辺・速さ・面積だけ。"""
    n = mr.params["numbers"]
    side, speed = sympy.Integer(int(n["side"])), sympy.Integer(int(n["speed"]))
    return [
        cast(Solution, REGISTRY.solver("math.express_single_interval_area")(side, speed)),
        cast(
            Solution,
            REGISTRY.solver("math.solve_time_from_area")(
                sympy.Rational(side * speed, 2), n["area"]
            ),
        ),
    ]


@register_checker("math.word_problem_interval_exprs_and_graph.double_solve")
def double_solve_word_problem_interval_exprs_and_graph(mr: MR) -> list[Solution]:
    """(1)=区間ごとの式・(2)=グラフの折れ点。"""
    n = mr.params["numbers"]
    return [
        cast(
            Solution,
            REGISTRY.solver("math.express_three_interval_area_exprs")(n["side"], n["speed"]),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.draw_three_interval_area_graph_features")(
                n["side"], n["speed"]
            ),
        ),
    ]


@register_checker("math.word_problem_max_area_and_times.double_solve")
def double_solve_word_problem_max_area_and_times(mr: MR) -> Solution:
    """本文の (面積, 縦の変域) だけから、式と横の変域を独立に組み直す。

    recipe と同じ solver を、**recipe と違う順で**呼ぶ（変域の端が入れかわることを
    checker の側でも独立に確かめる）。
    """
    n = mr.params["numbers"]
    area, lo, hi = int(n["area"]), int(n["lo"]), int(n["hi"])
    ends = []
    for side in (hi, lo):  # 縦が大きいほうから＝横は小さいほうから
        sol = cast(
            Solution,
            REGISTRY.solver("math.evaluate_inverse_proportion")(area, side, "forward"),
        )
        assert isinstance(sol.answer, SymbolicAnswer)
        ends.append(sympy.sympify(sol.answer.srepr))
    y_lo, y_hi = ends
    expr = sympy.Integer(area) / sympy.Symbol("x")
    return Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(sympy.Tuple(expr, y_lo, y_hi)),
            display=(
                f"y = {area}/x、"
                f"横は {sympy.sstr(y_lo)}cm 以上 {sympy.sstr(y_hi)}cm 以下"
            ),
        ),
        steps=[],
    )


@register_checker("math.draw_three_interval_area_graph.double_solve")
def double_solve_draw_three_interval_area_graph(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.draw_three_interval_area_graph_features")(p["side"], p["speed"]),
    )


# ---------------------------------------------------------------------------
# exam_l3（入試融合・動点と面積変化）— C13
# ---------------------------------------------------------------------------
@register_checker("math.exam_interval_area_and_value.double_solve")
def double_solve_exam_interval_area_and_value(mr: MR) -> Solution:
    """本文に出ている 1辺・速さ・時刻だけから、区間の式と面積を解き直す。"""
    n = mr.params["numbers"]
    return cast(
        Solution,
        REGISTRY.solver("math.express_interval_area_and_value")(
            n["side"], n["speed"], n["time"]
        ),
    )


@register_checker("math.exam_area_all_times.double_solve")
def double_solve_exam_area_all_times(mr: MR) -> Solution:
    n = mr.params["numbers"]
    return cast(
        Solution,
        REGISTRY.solver("math.solve_moving_point_area_all_times")(
            n["side"], n["speed"], n["area"]
        ),
    )


@register_checker("math.exam_read_area_graph.double_solve")
def double_solve_exam_read_area_graph(mr: MR) -> Solution:
    """読み取りの正解を、図ではなく場面のパラメータから解き直す。"""
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.read_area_graph_values")(p["side"], p["speed"], p["read_time"]),
    )


@register_checker("math.exam_word_problem_three_intervals.double_solve")
def double_solve_exam_word_problem_three_intervals(mr: MR) -> list[Solution]:
    """(1)=はじめの区間の式・(2)=一定の区間の式・(3)=時刻すべて。"""
    n = mr.params["numbers"]
    return [
        cast(
            Solution,
            REGISTRY.solver("math.express_single_interval_area")(n["side"], n["speed"]),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.express_constant_interval_area")(n["side"], n["speed"]),
        ),
        cast(
            Solution,
            REGISTRY.solver("math.solve_moving_point_area_all_times")(
                n["side"], n["speed"], n["area"]
            ),
        ),
    ]


@register_checker("math.exam_word_problem_quarter_area.double_solve")
def double_solve_exam_word_problem_quarter_area(mr: MR) -> Solution:
    """求める面積は本文に無いので、1辺から s²/4 を組み直してから解く。"""
    n = mr.params["numbers"]
    side = sympy.Integer(int(n["side"]))
    return cast(
        Solution,
        REGISTRY.solver("math.solve_moving_point_area_all_times")(
            side, n["speed"], sympy.Rational(side**2, 4)
        ),
    )


__all__ = [
    "double_solve_solve_moving_point_area",
    "double_solve_word_problem_area_graph_and_times",
    "double_solve_word_problem_single_interval_area",
    "double_solve_word_problem_interval_exprs_and_graph",
    "double_solve_word_problem_max_area_and_times",
    "double_solve_draw_three_interval_area_graph",
    "double_solve_draw_area_time_graph_segment",
    "double_solve_word_problem_moving_points_area",
    "double_solve_word_problem_moving_point_all_times",
    "double_solve_exam_interval_area_and_value",
    "double_solve_exam_area_all_times",
    "double_solve_exam_read_area_graph",
    "double_solve_exam_word_problem_three_intervals",
    "double_solve_exam_word_problem_quarter_area",
]
