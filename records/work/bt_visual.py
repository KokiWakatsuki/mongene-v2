"""図が要る問題の逆翻訳（G-BT）— **図を PNG にして読み手に渡す**。

## なぜ保留されていたか

逆翻訳は「問題文だけを読んで解き、エンジンの答えと突き合わせる」ゲートで、
日本語と数式の食い違いを見る唯一の面である。ところが**図がないと解けない問題**
（箱ひげ図から読み取る・グラフの交点・立体の見取図）は、問題文だけ渡しても
解きようがないので 41 問が保留のままだった。

読み手（Claude 自身）は画像を読めるので、図を PNG に起こして問題文と並べれば
そのまま通せる。ここはその準備をする道具。

## 出すもの

  records/work/bt/visual/<セル>_s<seed>.png   図（問題図。模範解答図は出さない）
  records/work/bt/visual.md                   問題文と図のファイル名の一覧

**答えは出さない。** 読み手が図と本文だけから解き、`bt_check.py` が突き合わせる。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/bt_visual.py [--seeds N]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, family_of, make_env

_OUT = Path("records/work/bt/visual")
_PY = "/Users/koki/workspace/mongene-v2/.venv/bin/python"


def main() -> int:
    seeds = 1
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])
    _OUT.mkdir(parents=True, exist_ok=True)
    env = make_env()
    lines = ["# 図が要る問題の逆翻訳（図と本文だけを読んで答える）", ""]
    n = 0
    for coord in capability_cells(env):
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception:  # noqa: BLE001
                continue
            if isinstance(res, Unsupported) or not res.visual_svg:
                continue
            cell = f"{family_of(coord)}.Lv{coord.level}"
            stem = f"{cell.replace('.', '_')}_s{seed}"
            svg = _OUT / f"{stem}.svg"
            svg.write_text(res.visual_svg, encoding="utf-8")
            subprocess.run(
                [_PY, "-c",
                 f"import cairosvg;cairosvg.svg2png(url='{svg}',"
                 f"write_to='{_OUT}/{stem}.png',output_width=460)"],
                check=False,
            )
            lines += [f"## {cell}#{seed}", "", f"![図]({stem}.png)", "",
                      res.problem_text, ""]
            for sq in res.sub_questions:
                lines.append(f"（問い） {sq.prompt_text}")
            lines.append("")
            n += 1
    Path("records/work/bt/visual.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"図つきの問題 {n} 件 → records/work/bt/visual.md（図は {_OUT}/）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
