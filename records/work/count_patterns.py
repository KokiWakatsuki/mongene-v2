"""各セルが何「型」の問題を作れるかを実測する。

同一セルの中では op 列（fp）は一定なので、fp では型を数えられない。
**離散パラメータ（文字列・真偽値）の組**を型の代理とする——recipe が
「どの構成／どの命題の型／どの場面を引いたか」はここに載るのに対し、
数値パラメータは同じ型の中の見た目だけを変えるからである。
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

from engine.eval._harness import build_mr, capability_cells, make_env

SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 24


def pattern_key(params: dict) -> str:
    """離散パラメータだけを取り出した鍵（＝型の代理）。"""
    out = {}
    for k, v in sorted(params.items()):
        if isinstance(v, bool) or isinstance(v, str):
            out[k] = v
        elif isinstance(v, list) and v and all(isinstance(x, str) for x in v):
            # 文字の並び（letters など）は「同じ型の見た目違い」なので長さだけ見る
            out[k] = f"<{len(v)} strs>"
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


def main() -> None:
    env = make_env()
    cells = capability_cells(env)
    per_cell: dict[str, set[str]] = {}
    examples: dict[str, dict[str, int]] = defaultdict(dict)
    for coord in cells:
        name = f"{coord.unit}.{coord.form}.Lv{coord.level}"
        keys: set[str] = set()
        for seed in range(1, SEEDS + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            k = pattern_key(r.mr.params)
            if k not in keys:
                examples[name][k] = seed  # その型が最初に出た seed
            keys.add(k)
        per_cell[name] = keys

    total_cells = len(per_cell)
    total_patterns = sum(len(v) for v in per_cell.values())
    dist: dict[int, int] = defaultdict(int)
    for v in per_cell.values():
        dist[len(v)] += 1

    print(f"セル数 {total_cells} / 型の総数 {total_patterns}（{SEEDS} seed で観測）")
    print("\n--- 1セルあたりの型の数の分布 ---")
    for n in sorted(dist):
        print(f"  型 {n:2d} 個: {dist[n]:4d} セル")
    print("\n--- 型が多いセル 上位20 ---")
    for name, keys in sorted(per_cell.items(), key=lambda kv: -len(kv[1]))[:20]:
        print(f"  {len(keys):3d}  {name}")

    with open("records/work/patterns.json", "w", encoding="utf-8") as fh:
        json.dump(
            {name: examples[name] for name in sorted(per_cell)},
            fh,
            ensure_ascii=False,
            indent=1,
        )
    print("\n代表 seed を records/work/patterns.json に書いた。")


if __name__ == "__main__":
    main()
