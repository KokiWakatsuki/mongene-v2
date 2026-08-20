"""場面に出る語と助数詞・単位の**実物の組**を数え上げる（G-SC4 の宣言を決める前に）。

★語尾・単位は列挙せず思いつきで決めると外す（文末770種を数え上げてから決めた）。
ここで出た組を見て、「対になっているか」を人が1回判断し、宣言に書く。

実行: .venv/bin/python records/work/measure_scene_words.py [--seeds N]
"""
from __future__ import annotations

import sys
from collections import defaultdict

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
    counters: dict[str, set[str]] = defaultdict(set)      # 助数詞 → 一緒に出た語
    units: dict[str, set[str]] = defaultdict(set)         # answer_unit → 一緒の counter
    slot_names: dict[str, set[str]] = defaultdict(set)    # slots の鍵 → 値
    aru_iru: dict[str, set[str]] = defaultdict(set)       # 「がいる」「がある」の直前
    for unit_, form, level, _c, _e, _f in load_cells():
        if form != "word_problem":
            continue
        coord = Coordinate(subject="math", unit=unit_, form=form, level=level)
        for seed in range(1, seeds + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            slots = r.mr.params.get("slots")
            if isinstance(slots, dict):
                for k, v in slots.items():
                    slot_names[k].add(str(v))
                counter = str(slots.get("counter", ""))
                if counter:
                    for k, v in slots.items():
                        if k != "counter":
                            counters[counter].add(str(v))
            au = r.mr.params.get("answer_unit")
            aus = r.mr.params.get("answer_units")
            for u in ([au] if au else []) + list(aus or []):
                if isinstance(slots, dict):
                    units[str(u)].add(str(slots.get("counter", "(counter なし)")))
            text = " ".join(str(v) for v in r.mr.given.values())
            for marker in ("がいる", "がある", "がいます", "があります"):
                idx = text.find(marker)
                while idx > 0:
                    aru_iru[marker].add(text[max(0, idx - 6):idx])
                    idx = text.find(marker, idx + 1)
    print(f"seed 1..{seeds}\n")
    print("## slots の鍵 → 出た値")
    for k in sorted(slot_names):
        vals = sorted(slot_names[k])
        print(f"  {k:14s} ({len(vals):3d}) {'、'.join(vals[:12])}"
              + (" …" if len(vals) > 12 else ""))
    print("\n## 助数詞 → 同じ場面に出た語")
    for c in sorted(counters):
        vals = sorted(counters[c])
        print(f"  {c:6s} ({len(vals):3d}) {'、'.join(vals[:14])}"
              + (" …" if len(vals) > 14 else ""))
    print("\n## 答えの単位 → 同じ場面の counter")
    for u in sorted(units):
        print(f"  {u:6s} → {'、'.join(sorted(units[u]))}")
    print("\n## 「がいる／がある」の直前")
    for m in sorted(aru_iru):
        print(f"  {m}: {'、'.join(sorted(aru_iru[m])[:10])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
