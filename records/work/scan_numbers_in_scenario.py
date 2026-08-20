"""**立式に渡している数が、場面文に本当に書いてあるか**を見る。

## なぜこれを見るか

文章題の recipe は全部この約束で書かれている（docstring に明記されている）:

> `params["numbers"]` は場面文が読者に見せている数値そのもので、答えは入っていない。

この約束が守られていれば、生徒は本文だけを読んで立式できる。破れていると
**本文に書いていない数で立式している**＝生徒には解けない問題になる。

**この約束は一度も検査されていない。** double-solve（G-Q1）は
「numbers → 立式 → 解」を二重化するだけで、numbers が本文に出ているかは見ない。
逆翻訳（G-BT）は人が読むので見つかるが、読める量に限りがある。
ここは機械で全数見る。

## 数え方と、出ても欠陥とは限らないもの

場面文（`given.scenario`）と小問文の中に、その数字が現れるかを見る。
現れないものには**正当な理由がある場合がある**:

  - 立式の途中で導く数（連比の和 r1+r2+r3 は本文に無い＝読者がたす数）
  - 単位をまたぐ数（本文「1時間30分」に対し numbers は 90）
  - 1 や 2 のような、場面ではなく式の形から来る数

だから**この走査は欠陥を出すのではなく、読む先を絞る**。出たものを1件ずつ見て、
理由のあるものは recipe 側に「本文に出さない数」と宣言させる（`derived_numbers`）。

実行: .venv/bin/python records/work/scan_numbers_in_scenario.py [--seeds N]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from engine.eval._harness import build_mr, capability_cells, family_of, make_env

_DIGITS = re.compile(r"\d+")


def _texts(mr) -> str:  # noqa: ANN001 - MR
    """読者が目にする文字すべて（場面文・変数の設定・小問文・題材）。"""
    parts = [str(v) for v in (mr.given or {}).values()]
    parts += [str(v) for v in (mr.context_slots or {}).values()]
    return " ".join(parts)


def main() -> int:
    seeds = 3
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    # 場面 → 本文に出ていなかった数量名（seed をまたいで毎回出るものだけが本物）
    missing: dict[tuple[str, str], set[str]] = defaultdict(set)
    always: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    seen: dict[tuple[str, str], int] = defaultdict(int)
    n_cells = 0

    for coord in capability_cells(env):
        for seed in range(1, seeds + 1):
            try:
                res = build_mr(coord, seed, env)
            except Exception:  # noqa: BLE001
                continue
            mr = getattr(res, "mr", None)
            if mr is None or not isinstance(mr.params.get("numbers"), dict):
                continue
            n_cells += 1
            key = (family_of(coord), str(mr.params.get("scenario_kind", "-")))
            seen[key] += 1
            text = _texts(mr)
            in_text = set(_DIGITS.findall(text))
            for name, value in mr.params["numbers"].items():
                digits = _DIGITS.findall(str(value))
                if digits and not all(d in in_text for d in digits):
                    missing[key].add(name)
                    always[key][name] += 1

    print(f"numbers を持つ MR {n_cells} 件 / 場面 {len(seen)} 種\n")
    hard = [(k, {n: c for n, c in always[k].items() if c == seen[k]}) for k in sorted(missing)]
    hard = [(k, v) for k, v in hard if v]
    print(f"=== 全 seed で本文に出ていない数量（{len(hard)} 場面）===")
    for (fam, kind), names in hard:
        print(f"  {fam:<34} {kind:<24} {','.join(sorted(names))}")
    soft = [(k, sorted(missing[k] - set(dict(hard).get(k, {})))) for k in sorted(missing)]
    soft = [(k, v) for k, v in soft if v]
    if soft:
        print(f"\n=== 一部の seed だけ出ていない（{len(soft)} 場面・抽選で桁が変わる等）===")
        for (fam, kind), names in soft:
            print(f"  {fam:<34} {kind:<24} {','.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
