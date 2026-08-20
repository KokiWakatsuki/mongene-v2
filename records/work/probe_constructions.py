"""構成カタログが**実際に何を出せるか**を実測する（family を書く前に回す）。

family の params（construction / proof_depth / prefer / 定義域）を当てずっぽうで書くと、
「質のフィルタを1つも通らないのに台帳には載る」セルができる（g2_l50 Lv3 で実際に起きた）。
先にここで、構成ごとに

  ・パラメータの箱のうち何割が質のフィルタを通るか
  ・通ったとき、深さ×prefer の組で何が結論に選ばれるか（op 列つき）

を出しておけば、family は実測を写すだけになる。

実行:
  .venv/bin/python records/work/probe_constructions.py [構成名 ...]
"""
from __future__ import annotations

import sys
from collections import defaultdict

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
from engine.packs.math.geometry.naturalness import accidental_coincidences, select_goal
from engine.packs.math.geometry.render_text import build_proof_lines
from engine.packs.math.geometry.rules import RULES

_PERT = (
    {"base": 0.8, "angle": 1.15, "offset": 1.25},
    {"base": 1.2, "angle": 0.85, "offset": 0.8},
)

# 構成名 → その単元クラスタの topic_set（module の並びに合わせる）。
_TOPIC_BY_PREFIX = {
    "circle_": "circle",
    "pgram_": "parallelogram",
    "quad_": "parallelogram",
    "similar_": "similarity",
    "ratio_": "similarity",
    "midline_": "similarity",
    "trapezoid_": "area",
    "triangle_median": "area",
}
_DEFAULT_TOPIC = "right_triangle"

_PREFERS = (
    None,
    "tri_cong",
    "seg_eq",
    "ang_eq",
    "parallel",
    "parallelogram",
    "rectangle",
    "rhombus",
    "square",
    "tri_sim",
    "ratio_eq",
    "tri_area_eq",
    "right_angle",
)

_GRID = [
    {"base": b / 10.0, "angle": a, "offset": o / 10.0}
    for b in (28, 34, 40, 46)
    for a in (40, 55, 70, 85)
    for o in (10, 18, 26)
]


def _topic_of(name: str) -> str:
    for prefix, topic in _TOPIC_BY_PREFIX.items():
        if name.startswith(prefix):
            return topic
    return _DEFAULT_TOPIC


def probe(name: str, *, excluded: frozenset[str] = frozenset(), topic: str = "") -> None:
    builder = CONSTRUCTIONS[name]
    topic = topic or _topic_of(name)
    allowed = topics_of(topic)
    rules = tuple(r for r in RULES if r.name not in excluded)
    good = 0
    reject: defaultdict[str, int] = defaultdict(int)
    hits: defaultdict[tuple[int, str | None], list] = defaultdict(list)
    for params in _GRID:
        con = builder(params)
        ded = saturate(
            con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes()
        )
        problems = figure_quality_problems(con)
        if problems:
            reject["図: " + problems[0][:40]] += 1
            continue
        others = [
            builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERT
        ]
        acc = accidental_coincidences([con, *others], ded)
        if acc:
            reject["偶然: " + acc[0][:40]] += 1
            continue
        good += 1
        for depth in (1, 2, 3, 4):
            for prefer in _PREFERS:
                goal = select_goal(
                    ded, level=2, allowed_topics=allowed, prefer=prefer, depth=depth
                )
                if goal is None or (prefer is not None and goal.fact.kind != prefer):
                    continue
                lines = build_proof_lines(ded, goal.fact)
                hits[(depth, prefer)].append((goal.fact, tuple(line.op for line in lines)))

    print(f"\n### {name}  [topic_set={topic}]  質のフィルタ通過 {good}/{len(_GRID)}")
    for why, n in sorted(reject.items(), key=lambda x: -x[1])[:2]:
        print(f"    落ちた理由 {n:3d}: {why}")
    if not good:
        return
    for (depth, prefer), got in sorted(hits.items(), key=lambda x: (x[0][0], str(x[0][1]))):
        if prefer is None:
            continue
        fact, ops = got[0]
        print(
            f"    depth={depth} prefer={prefer:<14} {len(got):3d}/{good}  "
            f"{fact.kind}{fact.args}  ops={list(ops)}"
        )


def main() -> int:
    argv = list(sys.argv[1:])
    excluded: set[str] = set()
    topic = ""
    names: list[str] = []
    for a in argv:
        if a.startswith("--exclude="):
            excluded |= {x for x in a.split("=", 1)[1].split(",") if x}
        elif a.startswith("--topic="):
            topic = a.split("=", 1)[1]
        else:
            names.append(a)
    for name in names or sorted(CONSTRUCTIONS):
        probe(name, excluded=frozenset(excluded), topic=topic)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
