"""「明らかに違う問題」が全部で何個あるかを実測する。

## 型の数え方
同一セルの中では op 列（fp）は一定なので、fp では型を数えられない。かといって
params をそのまま鍵にすると、`eq_str` のような**問題の実体**まで型として数えてしまう
（最初の測定はこれで 219 セルが「24 seed で 24 型」になった）。

そこで2つの信号を組み合わせる:
  1. **値の種類が少ないパラメータ**だけを型の軸とみなす。N seed 引いて値の種類が
     `_AXIS_MAX` 以下のものが軸（proof_id・mode・context など）。係数や式は
     seed ごとに違う値になるので自然に落ちる。
  2. **ヒントの列**（＝解く筋道の言葉）。パラメータに出ない型の違いを拾う
     （g2_l38 Lv3 の「証明する枝」と「反例を出す枝」など）。

実行: .venv/bin/python records/work/count_types.py [seeds]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from engine.eval._harness import build_mr, capability_cells, make_env

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
_AXIS_MAX = 12  # これ以下の種類しか取らない params だけを型の軸とする


def _dump(v: object) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)


def main() -> None:
    env = make_env()
    cells = capability_cells(env)
    per_cell: dict[str, dict[str, int]] = {}   # cell -> {型鍵: 代表seed}
    axes_of: dict[str, list[str]] = {}

    for coord in cells:
        name = f"{coord.unit}.{coord.form}.Lv{coord.level}"
        rows: list[tuple[int, dict, tuple]] = []
        for seed in range(1, SEEDS + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            params = dict(r.mr.params)
            # 解く筋道の言葉（params に出ない型の違いを拾う）。
            narration = tuple(
                s.narration for sq in r.mr.sub_questions for s in (sq.steps or ())
            )
            rows.append((seed, params, narration))
        if not rows:
            per_cell[name] = {}
            continue

        # 値の種類が少ない params だけを軸にする
        values: dict[str, set[str]] = defaultdict(set)
        for _, params, _ in rows:
            for k, v in params.items():
                values[k].add(_dump(v))
        axes = sorted(k for k, s in values.items() if len(s) <= _AXIS_MAX)
        axes_of[name] = axes

        seen: dict[str, int] = {}
        for seed, params, hints in rows:
            key = _dump([[a, params.get(a)] for a in axes] + [list(hints)])
            if key not in seen:
                seen[key] = seed
        per_cell[name] = seen

    total_types = sum(len(v) for v in per_cell.values())
    dist: dict[int, int] = defaultdict(int)
    for v in per_cell.values():
        dist[len(v)] += 1

    print(f"セル 630 / **明らかに違う問題 {total_types} 個**（{SEEDS} seed で観測）")
    print("\n--- 1セルあたりの型の数 ---")
    for n in sorted(dist):
        print(f"  型 {n:3d} 個: {dist[n]:4d} セル")
    print("\n--- 型が多いセル 上位25 ---")
    for name, seen in sorted(per_cell.items(), key=lambda kv: -len(kv[1]))[:25]:
        print(f"  {len(seen):3d}  {name}   軸={axes_of.get(name)}")

    with open("records/work/types.json", "w", encoding="utf-8") as fh:
        json.dump(per_cell, fh, ensure_ascii=False, indent=1)
    print("\n型ごとの代表 seed を records/work/types.json に書いた。")


if __name__ == "__main__":
    main()
