"""構成×パラメータ定義域の当たり率と、選ばれる結論の分布を測る（作業用）。

  .venv/bin/python records/work/sweep_circle.py <構成名> <depth> <prefer|-> \
      <base_lo,base_hi> <angle_lo,angle_hi> <offset_lo,offset_hi> [topic_set] [exclude,...]
"""
from __future__ import annotations

import random
import sys
from collections import Counter

from engine.packs.math.geometry import (  # noqa: F401
    constructions_area,
    constructions_circle,
    constructions_congruence,
    constructions_parallelogram,
    constructions_right_triangle,
    constructions_similarity,
)
from engine.packs.math.geometry.facts import fact_text
from engine.packs.math.recipes.geometry_proof import build_problem


def main() -> int:
    name, depth_s, prefer_s = sys.argv[1], sys.argv[2], sys.argv[3]
    b = [int(x) for x in sys.argv[4].split(",")]
    a = [int(x) for x in sys.argv[5].split(",")]
    o = [int(x) for x in sys.argv[6].split(",")]
    topic_set = sys.argv[7] if len(sys.argv) > 7 else "circle"
    excl = tuple(sys.argv[8].split(",")) if len(sys.argv) > 8 and sys.argv[8] else ()
    depth = None if depth_s == "-" else int(depth_s)
    prefer = None if prefer_s == "-" else prefer_s

    rng = random.Random(7)
    ok = 0
    goals: Counter[str] = Counter()
    ops: Counter[tuple] = Counter()
    n = 300
    for _ in range(n):
        params = {
            "base": rng.randint(*b) / 10.0,
            "angle": rng.randint(*a),
            "offset": rng.randint(*o) / 10.0,
        }
        try:
            built = build_problem(
                name, params, level=2, topic_set=topic_set,
                exclude_rules=excl, depth=depth, prefer=prefer,
            )
        except Exception as e:  # noqa: BLE001
            goals[f"ERR {e}"] += 1
            continue
        if built is None:
            continue
        ok += 1
        con, ded, goal, lines = built
        goals[fact_text(goal.fact)] += 1
        ops[tuple(line.op for line in lines)] += 1
    print(f"{name} depth={depth} prefer={prefer}: ok {ok}/{n} = {ok/n:.0%}")
    for g, k in goals.most_common(12):
        print(f"   {k:4d}  {g}")
    print("op 列:")
    for op, k in ops.most_common(6):
        print(f"   {k:4d}  {list(op)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
