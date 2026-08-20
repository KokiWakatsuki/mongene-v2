"""family の定義域を**実測から決める**（当てずっぽうで書かないための道具）。

`check_cell` が rejects=0/120 を要求するのに対し、recipe の有界リトライは 24 回しか
引き直さない。つまり定義域の合格率が 9 割を切ると、120 本のどこかで必ず落ちる。
定義域は「たぶんこの辺」ではなく、**測って決める**しかない。

やること: 粗い格子で (base, angle, offset) の合格/不合格を測り、合格率が閾値を
超える最大の箱まで貪欲に縮めて、family にそのまま貼れる定義域を出す。

実行:
  .venv/bin/python records/work/fit_domain.py <構成名> <depth> \
      [--prefer seg_eq] [--topic parallelogram] [--exclude r1,r2]
"""
from __future__ import annotations

import argparse
import itertools

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


def _evaluate(builder, params, *, rules, allowed, depth, prefer):
    con = builder(params)
    ded = saturate(con.points, frozenset(con.facts), rules=rules, ray_classes=con.ray_classes())
    goal = select_goal(ded, level=2, allowed_topics=allowed, prefer=prefer, depth=depth)
    if goal is None:
        return False, "結論なし", None
    if prefer is not None and goal.fact.kind != prefer:
        return False, f"結論の型が違う（{goal.fact.kind}）", None
    problems = figure_quality_problems(con)
    if problems:
        return False, "図: " + problems[0][:36], None
    others = [builder({k: v * f.get(k, 1.0) for k, v in params.items()}) for f in _PERT]
    acc = accidental_coincidences([con, *others], ded)
    if acc:
        return False, "偶然: " + acc[0][:36], None
    return True, "", goal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("construction")
    ap.add_argument("depth", type=int)
    ap.add_argument("--prefer", default=None)
    ap.add_argument("--topic", default="parallelogram")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--base", default="24,50")
    ap.add_argument("--angle", default="30,95")
    ap.add_argument("--offset", default="6,32")
    args = ap.parse_args()

    builder = CONSTRUCTIONS[args.construction]
    excluded = {x for x in args.exclude.split(",") if x}
    rules = tuple(r for r in RULES if r.name not in excluded)
    allowed = topics_of(args.topic)

    b0, b1 = (int(x) for x in args.base.split(","))
    a0, a1 = (int(x) for x in args.angle.split(","))
    o0, o1 = (int(x) for x in args.offset.split(","))
    bases = list(range(b0, b1, 3))
    angles = list(range(a0, a1, 6))
    offsets = list(range(o0, o1, 3))

    mask: dict[tuple[int, int, int], bool] = {}
    why: dict[str, int] = {}
    sample = None
    for b, a, o in itertools.product(bases, angles, offsets):
        ok, reason, goal = _evaluate(
            builder,
            {"base": b / 10.0, "angle": a, "offset": o / 10.0},
            rules=rules, allowed=allowed, depth=args.depth, prefer=args.prefer,
        )
        mask[(b, a, o)] = ok
        if ok and sample is None:
            sample = (goal, {"base": b / 10.0, "angle": a, "offset": o / 10.0})
        if not ok:
            why[reason] = why.get(reason, 0) + 1

    total = len(mask)
    passed = sum(mask.values())
    print(f"{args.construction} depth={args.depth} prefer={args.prefer}: 粗格子 {passed}/{total}")
    for reason, n in sorted(why.items(), key=lambda x: -x[1])[:3]:
        print(f"    {n:4d}  {reason}")
    if not passed:
        return 1

    # 合格率が閾値を超えるまで、端の面を落としていく（失敗の多い面から）。
    axes = {"base": bases, "angle": angles, "offset": offsets}
    cur = {k: list(v) for k, v in axes.items()}

    def rate(box) -> float:
        pts = [mask[(b, a, o)] for b in box["base"] for a in box["angle"] for o in box["offset"]]
        return sum(pts) / len(pts) if pts else 0.0

    # 合格率が閾値を超えるまで縮め、そのあと**戻せるだけ戻す**（縮めすぎると
    # 変種が足りなくなり、今度は dup_rate ≤ 0.20 が落ちる。狭い箱は別の落ち方をする）。
    while rate(cur) < 0.93:
        best = None
        for key in cur:
            if len(cur[key]) <= 2:
                continue
            for end in (0, -1):
                trial = {k: list(v) for k, v in cur.items()}
                trial[key].pop(end)
                r = rate(trial)
                if best is None or r > best[0]:
                    best = (r, key, end)
        if best is None:
            break
        _, key, end = best
        cur[key].pop(end)

    grew = True
    while grew:
        grew = False
        for key, full in axes.items():
            for end in (0, -1):
                if len(cur[key]) == len(full):
                    continue
                i = full.index(cur[key][0]) - 1 if end == 0 else full.index(cur[key][-1]) + 1
                if not (0 <= i < len(full)):
                    continue
                trial = {k: list(v) for k, v in cur.items()}
                trial[key] = ([full[i]] + trial[key]) if end == 0 else (trial[key] + [full[i]])
                if rate(trial) >= 0.93:
                    cur = trial
                    grew = True

    volume = (
        (cur["base"][-1] - cur["base"][0] + 1)
        * (cur["angle"][-1] - cur["angle"][0] + 1)
        * (cur["offset"][-1] - cur["offset"][0] + 1)
    )
    print(f"    箱の中の整数の組: {volume} 通り（dup_rate ≤ 0.20 には 250 通りほど要る）")

    print(f"    → 箱 base={cur['base'][0]}-{cur['base'][-1]} "
          f"angle={cur['angle'][0]}-{cur['angle'][-1]} "
          f"offset={cur['offset'][0]}-{cur['offset'][-1]}  合格率 {rate(cur):.2f}")
    if sample:
        goal, params = sample
        lines = build_proof_lines(
            saturate(
                builder(params).points, frozenset(builder(params).facts), rules=rules,
                ray_classes=builder(params).ray_classes(),
            ),
            goal.fact,
        )
        print(f"    結論 {goal.fact.kind}{goal.fact.args}")
        print(f"    ops  {[line.op for line in lines]}")
    print("    family に貼る形:")
    print(f"      base_domain: {{int_range: [{cur['base'][0]}, {cur['base'][-1]}]}}")
    print(f"      angle_domain: {{int_range: [{cur['angle'][0]}, {cur['angle'][-1]}]}}")
    print(f"      offset_domain: {{int_range: [{cur['offset'][0]}, {cur['offset'][-1]}]}}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
