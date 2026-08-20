"""平行四辺形クラスタの構成を試し撃ちする（結論の候補・深さ・証明文を見る）。

実行:
  .venv/bin/python records/work/probe_pgram.py <構成名> <depth> <prefer> [exclude,...]
"""
from __future__ import annotations

import sys
import time

from engine.bootstrap import bootstrap

bootstrap()

from engine.packs.math.geometry.catalog import CONSTRUCTIONS, topics_of  # noqa: E402
from engine.packs.math.geometry.construct import figure_quality_problems  # noqa: E402
from engine.packs.math.geometry.deduce import saturate  # noqa: E402
from engine.packs.math.geometry.facts import fact_text  # noqa: E402
from engine.packs.math.geometry.naturalness import (  # noqa: E402
    accidental_coincidences,
    goal_candidates,
    select_goal,
)
from engine.packs.math.geometry.render_text import (  # noqa: E402
    build_proof_lines,
    compared_triangles,
    render_proof,
)
from engine.packs.math.geometry.rules import RULES  # noqa: E402

_PERTURBATIONS = (
    {"base": 0.8, "angle": 1.15, "offset": 1.25},
    {"base": 1.2, "angle": 0.85, "offset": 0.8},
)


def main() -> int:
    name = sys.argv[1]
    depth = int(sys.argv[2])
    prefer = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
    exclude = tuple(sys.argv[4].split(",")) if len(sys.argv) > 4 else ()
    params = {
        "base": float(sys.argv[5]) if len(sys.argv) > 5 else 3.6,
        "angle": float(sys.argv[6]) if len(sys.argv) > 6 else 62.0,
        "offset": float(sys.argv[7]) if len(sys.argv) > 7 else 2.4,
    }
    builder = CONSTRUCTIONS[name]
    con = builder(params)
    print(f"points={sorted(con.coords)}  quality={figure_quality_problems(con)}")
    rules = tuple(r for r in RULES if r.name not in exclude)
    t0 = time.time()
    ded = saturate(con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes())
    print(f"saturate {time.time() - t0:.2f}s  facts={len(ded.why)}")
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERTURBATIONS]
    print("accidental:", accidental_coincidences([con, *others], ded))
    by_depth: dict[int, list[str]] = {}
    for cand in goal_candidates(ded):
        by_depth.setdefault(cand.depth, []).append(f"{cand.fact.kind}:{fact_text(cand.fact)}")
    for d in sorted(by_depth):
        print(f"  depth{d}: {len(by_depth[d])} 件  {by_depth[d][:8]}")
    goal = select_goal(
        ded, level=2, allowed_topics=topics_of("parallelogram"), prefer=prefer, depth=depth
    )
    if goal is None:
        print("!! goal なし")
        return 1
    lines = build_proof_lines(ded, goal.fact)
    print(f"\n問題: {con.description}。このとき、{fact_text(goal.fact)} であることを証明せよ。")
    print(render_proof(lines, targets=compared_triangles(ded, goal.fact)))
    print("ops:", [line.op for line in lines])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
