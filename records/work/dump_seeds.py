"""同じ文型を**複数 seed**で並べて出す（引いた数が場面にありうるかを読むため）。

## なぜ要るか

逆翻訳（`bt_patterns.py`）は文型を数え上げて**代表1件**を読む方式。日本語の骨格は
それで読み切れるが、**引いた数が場面としてありうるか**は seed ごとに変わる。
2026-08-15 に見つけた重い欠陥は、ほとんどがこの層にあった。

```
「2人の委員を選ぶとき、起こりうる場合は全部で31通り」   nC2 に 31 は無い
「落ち始めてからの時間 x 秒と落ちる距離 y m」 y=13x²    自由落下は 4.9x²
「125人のうち、ある階級の度数が109人」                 1階級に87%は分布でない
```

どれも**文型は正しく、数だけが場面に対してありえない**。だから文型を1件読んでも
出てこない。

## 出し方

セル × seed を、セルごとにまとめて出す。読むのは「数が場面にありうるか」だけ。
日本語の骨格は昨日読んだので繰り返さない。

実行:
  .venv/bin/python records/work/dump_seeds.py [--seeds N] [--forms a,b]
"""
from __future__ import annotations

import sys
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, family_of, make_env

_OUT = Path("records/work/bt/seeds")


def main() -> int:
    seeds = 6
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    forms = None
    if "--forms" in sys.argv:
        forms = set(sys.argv[sys.argv.index("--forms") + 1].split(","))

    _OUT.mkdir(parents=True, exist_ok=True)
    env = make_env()
    # 単元の頭（g1/g2/g3/exam）ごとにファイルを分ける（分担して読めるように）。
    buckets: dict[str, list[str]] = {}
    n = 0
    for coord in capability_cells(env):
        if forms and coord.form not in forms:
            continue
        cell = f"{family_of(coord)}.Lv{coord.level}"
        lines = [f"## {cell}", ""]
        got = 0
        for s in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, s),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception as e:  # noqa: BLE001
                lines.append(f"  [{s}] 構成に失敗: {type(e).__name__}")
                continue
            if isinstance(res, Unsupported):
                continue
            body = res.problem_text.replace("\n", " ")
            # **答えは切り詰めない。** 60字で切っていたので、長い答え
            # （選択肢の列挙・区間ごとの式・「3秒後と9秒後」）が途中で終わって見え、
            # 読んだ側が「答えが欠けている」と誤って報告する事故が起きた。
            ans = "／".join(
                str(getattr(sq.answer, "display", getattr(sq.answer, "correct", "")))
                for sq in res.sub_questions
            )
            lines.append(f"  [{s}] {body}")
            lines.append(f"      → {ans}")
            got += 1
        if got:
            buckets.setdefault(coord.unit.split("_")[0], []).extend(lines + [""])
            n += 1
    for key, lines in buckets.items():
        p = _OUT / f"{key}.md"
        p.write_text(f"# {key} のセル × {seeds} seed\n\n" + "\n".join(lines), encoding="utf-8")
        print(f"  {p}  {len(lines)} 行")
    print(f"セル {n} 件 × {seeds} seed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
