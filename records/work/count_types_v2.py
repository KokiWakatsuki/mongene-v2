"""型の数を数え直す（989 は過大だった）。

前回は「解く筋道の言葉（narration）」も型の鍵に混ぜた。ところが narration には
**数値と語彙がそのまま入る**セルがある:

    「8%の食塩水を x g、14%の食塩水を y g とおく。」   ← 濃度が入る
    「かきの個数を x、ぶどうの個数を y とおく。」        ← 果物名が入る

これらは中身の差し替えなのに、seed ごとに別の型として数えられてしまった
（g2_l18 は 38型と出ていたが、数字を伏せると **1型**）。

そこで鍵を作る前に
  1. 数字を `#` に伏せる
  2. その cell の `*_candidates` に並んでいる語彙を `@` に伏せる
をやってから数える。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/count_types_v2.py
"""
from __future__ import annotations

import json
import re
from collections import defaultdict

from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import build_mr, make_env

import sys
sys.path.insert(0, "records/work")
from build_corpus import load_cells, match_axis_keys  # noqa: E402

_SEEDS = 60


def vocab_of(params_spec: dict) -> list[str]:
    """`*_candidates` に並ぶ語彙（中身の差し替え）。"""
    out: list[str] = []
    for k, v in params_spec.items():
        if not isinstance(v, list):
            continue
        if k.endswith("_candidates") or k.endswith("_pool"):
            out += [str(x) for x in v if isinstance(x, str) and len(str(x)) > 1]
    return sorted(out, key=len, reverse=True)


def mask(text: str, vocab: list[str]) -> str:
    for w in vocab:
        text = text.replace(w, "@")
    return re.sub(r"\d+", "#", text)


def main() -> None:
    env = make_env()
    import yaml
    import glob
    spec_of: dict[str, dict] = {}
    for path in sorted(glob.glob("engine_core/engine/curriculum/math/families/*.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit, form = doc["family"].removeprefix("math.").rsplit(".", 1)
        for lv, spec in (doc.get("levels") or {}).items():
            spec_of[f"{unit}.{form}.Lv{lv}"] = spec.get("params") or {}

    total = 0
    per: dict[str, int] = {}
    for unit, form, level, catalogs, expected in load_cells():
        cell = f"{unit}.{form}.Lv{level}"
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        vocab = vocab_of(spec_of.get(cell, {}))
        rows = []
        for seed in range(1, _SEEDS + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            nar = tuple(
                mask(s.narration, vocab)
                for sq in r.mr.sub_questions for s in (sq.steps or ())
            )
            rows.append((seed, dict(r.mr.params), nar))
        if not rows:
            per[cell] = 0
            continue
        axes = match_axis_keys([p for _, p, _ in rows], catalogs)
        use_text = len(axes) < len(catalogs)
        seen = set()
        for seed, params, nar in rows:
            parts = [[a, params.get(a)] for a in axes] + [list(nar)]
            if use_text:
                res = generate(
                    GenerateRequest(subject="math", unit=unit, form=form,
                                    level=level, seed=seed),
                    curriculum=env.curriculum, families=env.families,
                    registry=env.registry,
                )
                if isinstance(res, Unsupported):
                    continue
                parts.append(mask(res.problem_text, vocab))
            seen.add(json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str))
        per[cell] = len(seen)
        total += len(seen)

    dist: dict[int, int] = defaultdict(int)
    for v in per.values():
        dist[v] += 1
    print(f"セル 630 / **構造として違う問題 {total}**（数字と語彙を伏せて数え直し）")
    print("\n1セルあたりの型の数")
    for n in sorted(dist):
        print(f"   型 {n:3d} 個: {dist[n]:4d} セル")
    print("\n型が多いセル 上位12")
    for cell, n in sorted(per.items(), key=lambda kv: -kv[1])[:12]:
        print(f"   {n:3d}  {cell}")


if __name__ == "__main__":
    main()
