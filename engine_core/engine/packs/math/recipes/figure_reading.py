"""図の中の要素を記号で答えるセルの recipe（Phase E 端物・graph_table Lv1 の3セル）。

solver（`solvers/figure_reading.py`）と図（`visuals/plane_figure.py`）を共有する3セル
（g1_l37 / g2_l32 / g2_l44）をここにまとめる。どれも
  given = condition（図が何を表しているかの文）／asked = read_figure_element
  visual = required（問題図は「読む対象」そのもの＝答えの印は描かない）
という同じ骨格で、違うのは図の中身と選ぶ対象だけ。

**答えを図に描かない**のがこの form の要点。距離を表す線分に印をつけたり、平行の
矢羽根を描いたりすると、読み取る前に答えが見えてしまう（`visuals/plane_figure.py`
の docstring に描かないものを明記してある）。
"""
from __future__ import annotations

from typing import Any, cast

from engine.core.contracts import (
    MR,
    CellContext,
    Provenance,
    Solution,
    SubQuestionMR,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY, register_recipe
from engine.core.rng import Rng, draw, draw_many

# ★**I と O は入れない**（1・0 と紛らわしいので実物の教材でも頂点名に使わない）。
# 他の描き手（`letter_expr._FIGURE_LETTERS`）は既にそうなっていたが、ここだけ
# 素のアルファベットを使っていて「立方体DEFG-HIJK」「正四面体GHIJ」が出ていた。
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _effective_concept_tags(ctx: CellContext) -> list[str]:
    return list(ctx.spec_level.concept_tags or ctx.spec_family.concepts_default)


def _draw_distinct_letters(rng: Rng, k: int) -> list[str]:
    idxs = draw_many({"int_range": [0, len(_ALPHABET) - 1], "distinct": ["value"]}, rng, k=k)
    return [_ALPHABET[int(i)] for i in idxs]


def _draw_from(candidates: list[Any], rng: Rng) -> Any:
    return candidates[int(draw({"int_range": [0, len(candidates) - 1]}, rng))]


def _mr(
    ctx: CellContext,
    *,
    params: dict[str, Any],
    statement: str,
    sol: Solution,
    labels: list[str],
    element_kind: str,
    recipe: str,
) -> MR:
    return MR(
        signature=ctx.spec_level.signature, family=ctx.family, level=ctx.level,
        purpose=ctx.purpose, seed=0, params=params,
        # graph_table の given 語彙は "figure_spec" を持たない（あれは find_value 側）。
        # 図の説明は既存の "condition" に載せる（g3_l55 の断面セルと同じ）。
        given={"condition": statement},
        sub_questions=[
            SubQuestionMR(
                label="(1)", asked="read_figure_element", answer=sol.answer, steps=sol.steps,
                concept_tags=_effective_concept_tags(ctx),
                cause_tags=list(ctx.spec_level.cause_tags),
            )
        ],
        visual_plan=VisualPlan(
            style="plane",
            labels=labels,
            elements=[VisualElement(kind=element_kind, attrs={})],
        ),
        provenance=Provenance(recipe=recipe),
    )


# ---------------------------------------------------------------------------
# g1_l37.graph_table Lv1: 点と直線の距離を表す線分はどれか
# ---------------------------------------------------------------------------
_DISTANCE_SEGMENT_CONCEPTS = ["line_angle_terms.read_point_line_distance"]


@register_recipe("math.identify_distance_segment", provides_concepts=_DISTANCE_SEGMENT_CONCEPTS)
def identify_distance_segment_recipe(ctx: CellContext, rng: Rng) -> MR:
    """点Pと直線ℓ・垂線の足H・直線上の2点を描き、距離を表す線分を選ばせる。"""
    p = ctx.spec_level.params
    point_p, foot, left, right = _draw_distinct_letters(rng, 4)
    line_name = str(_draw_from([str(v) for v in p["line_name_candidates"]], rng))
    foot_ratio = int(draw(p["foot_percent_domain"], rng)) / 100.0
    height = int(draw(p["height_domain"], rng))

    sol = cast(
        Solution, REGISTRY.solver("math.identify_distance_segment")(point_p, foot, left, right)
    )
    statement = (
        f"点{point_p}と直線{line_name}をかいた図がある。点{point_p}から直線{line_name}へ"
        f"垂線を引いたときの垂線の足を{foot}とし、直線{line_name}上に点{left}、点{right}を"
        f"とった。図の中で「点{point_p}と直線{line_name}との距離」を表している線分はどれか答えよ"
    )
    params = {
        "line_name": line_name, "point_p": point_p, "point_foot": foot,
        "point_left": left, "point_right": right,
        "foot_ratio": foot_ratio, "height": height,
    }
    return _mr(
        ctx, params=params, statement=statement, sol=sol,
        labels=[line_name, point_p, foot, left, right],
        element_kind="point_and_line", recipe="math.identify_distance_segment",
    )


# ---------------------------------------------------------------------------
# g2_l32.graph_table Lv1: 平行な直線を図で識別する
# ---------------------------------------------------------------------------
_PARALLEL_IDENTIFY_CONCEPTS = ["parallel_lines.identify_parallel_from_figure"]


@register_recipe("math.identify_parallel_line", provides_concepts=_PARALLEL_IDENTIFY_CONCEPTS)
def identify_parallel_line_recipe(ctx: CellContext, rng: Rng) -> MR:
    """横断線となす角を書いた直線を並べ、基準の直線と平行なものを選ばせる。

    正解の1本だけ基準と同じ角にし、他は**すべて異なる角**にする（同じ角が2本あると
    答えが定まらない）。角は構成の段階で相異を保証する。
    """
    p = ctx.spec_level.params
    n_candidates = int(draw(p["candidate_count_domain"], rng))
    base_angle = int(draw(p["angle_domain"], rng))
    lo, hi = (int(v) for v in p["angle_range"])
    pool = [a for a in range(lo, hi + 1) if a != base_angle]
    others = [int(v) for v in draw_many({"int_set": pool, "distinct": ["value"]}, rng, k=n_candidates - 1)]
    answer_pos = int(draw({"int_range": [0, n_candidates - 1]}, rng))
    angles = others[:answer_pos] + [base_angle] + others[answer_pos:]

    names = [str(v) for v in p["line_name_candidates"]][:n_candidates]
    base_name = str(p["base_name"])
    transversal = str(p["transversal_name"])

    sol = cast(Solution, REGISTRY.solver("math.identify_parallel_line")(base_angle, names, angles))
    statement = (
        f"直線{transversal}が、直線{base_name}と直線{'、直線'.join(names)}のそれぞれと"
        f"交わっている図がある。図には、それぞれの直線が直線{transversal}となす角の"
        f"大きさが書きこまれている。直線{'〜直線'.join([names[0], names[-1]])}のうち、"
        f"直線{base_name}と平行であるものを記号で答えよ"
    )
    params = {
        "transversal_name": transversal, "base_name": base_name, "base_angle": base_angle,
        "names": names, "angles": angles,
    }
    return _mr(
        ctx, params=params, statement=statement, sol=sol,
        labels=[transversal, base_name, *names, *[f"{a}°" for a in [base_angle, *angles]]],
        element_kind="parallel_candidates", recipe="math.identify_parallel_line",
    )


# ---------------------------------------------------------------------------
# g2_l44.graph_table Lv1: 斜辺・直角をはさむ2辺を記号で示す
# ---------------------------------------------------------------------------
_RIGHT_TRIANGLE_SIDES_CONCEPTS = ["right_triangle_congruence.read_hypotenuse_and_legs"]


@register_recipe(
    "math.identify_right_triangle_sides", provides_concepts=_RIGHT_TRIANGLE_SIDES_CONCEPTS
)
def identify_right_triangle_sides_recipe(ctx: CellContext, rng: Rng) -> MR:
    """直角三角形を描き、斜辺と直角をはさむ2辺を記号で答えさせる。"""
    p = ctx.spec_level.params
    start = int(draw({"int_range": [0, len(_ALPHABET) - 3]}, rng))
    labels = list(_ALPHABET[start : start + 3])
    right_index = int(draw({"int_range": [0, 2]}, rng))
    leg_a = int(draw(p["leg_px_domain"], rng))
    leg_b = int(draw(p["leg_px_domain"], rng))

    sol = cast(
        Solution, REGISTRY.solver("math.identify_right_triangle_sides")(labels, right_index)
    )
    name = "".join(labels)
    statement = (
        f"図の直角三角形{name}（∠{labels[right_index]}=90°）について、"
        "斜辺にあたる辺と、直角をはさむ2辺を記号を用いて示せ"
    )
    params = {
        "vertex_labels": labels, "right_angle_index": right_index,
        "leg_a_px": leg_a, "leg_b_px": leg_b,
    }
    return _mr(
        ctx, params=params, statement=statement, sol=sol, labels=list(labels),
        element_kind="right_triangle", recipe="math.identify_right_triangle_sides",
    )
