"""dup が閾を超えるセルで、**どの軸が動いていて、どの軸が止まっているか**を出す。

## なぜ要るか

`dup_key` から表層（点名・人名）を外したら 73 セルが閾を超えた。
点名で閾を通していたセルが露出したということで、**そのセルが実際に持っている
相異な問題の数**がここで初めて見える。

1セットずつ勘で定義域を広げると「正348角形」が生まれる。先に

  - 動いている軸（seed ごとに値が変わる params）
  - 止まっている軸（全 seed で同じ＝そのセルの固定要素）
  - 相異な値の数

を出し、「増やせる軸があるのか、本当に1変数の題材なのか」を分けてから手を入れる。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/analyze_dup_axes.py <セル名...> [--seeds N]
  PYTHONPATH=engine_core .venv/bin/python records/work/analyze_dup_axes.py --over <dup一覧のファイル>
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

from engine.core.contracts import Unsupported
from engine.core.signature import dup_key
from engine.eval._harness import build_mr, capability_cells, family_of, make_env

_ROW = re.compile(r"✗\s+(\S+)\s+dup_rate=([\d.]+)")


def _norm(v: object) -> str:
    return json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)[:60]


def main() -> int:
    seeds = 100
    argv = list(sys.argv[1:])
    if "--seeds" in argv:
        i = argv.index("--seeds")
        seeds = int(argv[i + 1])
        del argv[i : i + 2]

    if argv and argv[0] == "--over":
        text = open(argv[1], encoding="utf-8").read()
        wanted = {m.group(1): float(m.group(2)) for m in _ROW.finditer(text)}
    else:
        wanted = dict.fromkeys(argv, 0.0)

    env = make_env()
    looked = 0
    for coord in capability_cells(env):
        name = f"{family_of(coord)}.Lv{coord.level}".replace("math.", "")
        if name not in wanted:
            continue
        looked += 1
        values: dict[str, set[str]] = defaultdict(set)
        keys_seen: set[str] = set()
        dups: set[str] = set()
        built = 0
        for seed in range(1, seeds + 1):
            try:
                r = build_mr(coord, seed, env)
            except Exception:  # noqa: BLE001
                continue
            mr = getattr(r, "mr", r)
            if isinstance(mr, Unsupported):
                continue
            built += 1
            dups.add(dup_key(mr))
            for k, v in mr.params.items():
                keys_seen.add(k)
                values[k].add(_norm(v))
        moving = {k: len(values[k]) for k in keys_seen if len(values[k]) > 1}
        fixed = sorted(k for k in keys_seen if len(values[k]) == 1)
        print(f"■ {name}  dup={wanted[name]}  相異 {len(dups)}/{built}")
        if moving:
            for k, n in sorted(moving.items(), key=lambda kv: -kv[1]):
                print(f"    動 {k:26} {n:4} 通り  例 {sorted(values[k])[0][:52]}")
        else:
            print("    動いている軸なし（この署名では params が全 seed 同一）")
        if fixed:
            print(f"    固定 {', '.join(fixed[:12])}")
        print()

    # **比べる相手の個数を出す。** 指定名の綴り違いで 0 件になったのを見逃さない。
    print(f"指定 {len(wanted)} セル／見つかって測れたのは {looked} セル")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
