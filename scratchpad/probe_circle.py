"""円クラスタの構成から何が導けるかを実測する（作業用）。

  PYTHONPATH=. .venv/bin/python scratchpad/probe_circle.py <構成名> [depth] [exclude,...]
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
from engine.packs.math.geometry.catalog import CONSTRUCTIONS, topics_of
from engine.packs.math.geometry.construct import figure_quality_problems
from engine.packs.math.geometry.deduce import saturate
from engine.packs.math.geometry.facts import fact_text
from engine.packs.math.geometry.naturalness import accidental_coincidences, goal_candidates
from engine.packs.math.geometry.rules import RULES

_PARAMS = {"base": 3.6, "angle": 62, "offset": 2.4}
_PERT = ({"base": 0.8, "angle": 1.15, "offset": 1.25}, {"base": 1.2, "angle": 0.85, "offset": 0.8})


def main() -> int:
    name = sys.argv[1]
    want_depth = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] != "-" else None
    excl = tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ()
    topic_set = sys.argv[4] if len(sys.argv) > 4 else "circle"
    params = dict(_PARAMS)
    if len(sys.argv) > 5:
        for kv in sys.argv[5].split(","):
            k, v = kv.split("=")
            params[k] = float(v)
    builder = CONSTRUCTIONS[name]
    con = builder(params)
    print("points:", sorted(con.coords))
    print("desc:", con.description)
    print("givens:", [fact_text(f) for f in con.givens])
    print("facts:")
    for f in sorted(con.facts):
        print("   ", f.kind, f.args)
    print("figure_quality:", figure_quality_problems(con))
    rules = tuple(r for r in RULES if r.name not in excl)
    ded = saturate(con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes())
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERT]
    print("accidental:", accidental_coincidences([con, *others], ded)[:6])
    allowed = topics_of(topic_set)
    cands = goal_candidates(ded)
    for c in sorted(cands, key=lambda c: (c.depth, c.fact.kind, c.fact.args)):
        if want_depth is not None and c.depth != want_depth:
            continue
        ok = "OK " if c.topics <= allowed else "out"
        print(f"  d={c.depth} {ok} {c.fact.kind:12s} {fact_text(c.fact):40s} {c.rule_names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
