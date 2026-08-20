"""関係ごとに、引かれた数の**実物の範囲**を数え上げる（G-SC5 の宣言を決める前に）。

★上下限は思いつきで書かない。**実物を数え上げてから決める**——語尾や単位で
同じ失敗をしている（文末770種を列挙してから決めた）。ここで出た範囲を見て、
「場面としてありえるか」を人が1回判断し、`RELATION_BOUNDS` に書く。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/measure_relation_numbers.py [--seeds N]
"""
from __future__ import annotations

import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env

sys.path.insert(0, "records/work")


def main() -> int:
    bootstrap()
    from build_corpus import load_cells  # noqa: PLC0415

    seeds = 60
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    env = make_env()
    seen: dict[tuple[str, str], list[float]] = {}
    cells: dict[str, set[str]] = {}
    for unit, form, level, _c, _e, _f in load_cells():
        if form != "word_problem":
            continue
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        for seed in range(1, seeds + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            kind = str(r.mr.params.get("scenario_kind", ""))
            numbers = r.mr.params.get("numbers")
            if not kind or not isinstance(numbers, dict):
                continue
            cells.setdefault(kind, set()).add(f"{unit}.Lv{level}")
            for name, value in numbers.items():
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    continue        # 文字（変数名）は数ではない
                # ★`setdefault(...).append(float(v))` と書くと、float が落ちたときに
                # 空の並びが残って min() で死ぬ（実際に踏んだ）。先に数にする。
                seen.setdefault((kind, name), []).append(num)
    print(f"関係 {len(cells)} 種 / (関係, 数) の組 {len(seen)} 通り / seed 1..{seeds}\n")
    for kind in sorted(cells):
        print(f"## {kind}  （セル: {', '.join(sorted(cells[kind]))}）")
        for (k, name), values in sorted(seen.items()):
            if k != kind:
                continue
            lo, hi = min(values), max(values)
            fmt = (lambda x: f"{x:.0f}") if float(hi).is_integer() else (lambda x: f"{x:g}")
            print(f"    {name:16s} {fmt(lo):>8s} 〜 {fmt(hi):>8s}   "
                  f"（{len(set(values))} 通り / {len(values)} 回）")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
