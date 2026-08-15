"""直角三角形クラスタの構成を推論器にかけて、深さごとの結論候補を見る作業用スクリプト。

  PYTHONPATH=engine_core .venv/bin/python records/work/probe_rt.py <構成名> [depth] [prefer] [exclude,...]
"""
from __future__ import annotations

import sys

from engine.packs.math.geometry import (  # noqa: F401  登録の副作用
    constructions_area,
    constructions_circle,
    constructions_congruence,
    constructions_parallelogram,
    constructions_right_triangle,
    constructions_similarity,
)
from engine.packs.math.geometry.catalog import CONSTRUCTIONS
from engine.packs.math.geometry.construct import figure_quality_problems
from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import fact_text
from engine.packs.math.geometry.naturalness import (
    accidental_coincidences,
    goal_candidates,
    select_goal,
)
from engine.packs.math.geometry.render_text import (
    build_proof_lines,
    compared_triangles,
    render_proof,
)
from engine.packs.math.geometry.rules import RULES

_PERTURBATIONS = (
    {"base": 0.8, "angle": 1.15, "offset": 1.25},
    {"base": 1.2, "angle": 0.85, "offset": 0.8},
)


def main() -> int:
    name = sys.argv[1]
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else None
    prefer = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    exclude = tuple(sys.argv[4].split(",")) if len(sys.argv) > 4 else ()
    params = {
        "base": float(sys.argv[5]) if len(sys.argv) > 5 else 3.6,
        "angle": float(sys.argv[6]) if len(sys.argv) > 6 else 66.0,
        "offset": float(sys.argv[7]) if len(sys.argv) > 7 else 2.4,
    }
    builder = CONSTRUCTIONS[name]
    con = builder(params)
    print("params:", params)
    print("points:", con.coords)
    print("figure_quality:", figure_quality_problems(con))
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERTURBATIONS]
    rules = tuple(r for r in RULES if r.name not in exclude)
    ded = saturate(con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes())
    print("accidental:", accidental_coincidences([con, *others], ded))
    print("givens:")
    for f in sorted(con.facts, key=str):
        print("   ", fact_text(f))
    for c in sorted(goal_candidates(ded), key=lambda c: (c.depth, c.fact.kind, c.fact.args)):
        if depth is not None and c.depth != depth:
            continue
        print(f"  d{c.depth} {c.fact.kind:10s} {fact_text(c.fact):32s} {c.rule_names}")
    goal = select_goal(
        ded,
        level=2,
        allowed_topics=frozenset(
            {
                "congruence", "congruence_property", "isosceles", "midpoint", "angle",
                "parallel", "right_triangle", "equilateral",
            }
        ),
        prefer=prefer,
        depth=depth,
    )
    print("\nselected:", goal and fact_text(goal.fact), goal and goal.rule_names)
    if goal is not None:
        lines = build_proof_lines(ded, goal.fact)
        print(render_proof(lines, targets=compared_triangles(ded, goal.fact)))
        print("ops:", [ln.op for ln in lines])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
