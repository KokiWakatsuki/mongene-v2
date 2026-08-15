"""構成カタログの図を PNG に起こして目視する。

**ゲートは図の内容の誤りを検出しない。** 二等辺三角形が上下逆さまだったことも、
交点のラベルが線に埋もれていたことも、図に起こして初めて分かった。構成を足したら
必ずこれを回して目で見ること。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/draw_construction.py <構成名> [<構成名>...]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.packs.math.geometry import (  # noqa: F401  登録の副作用
    constructions_circle,
    constructions_congruence,
    constructions_parallelogram,
    constructions_right_triangle,
    constructions_similarity,
)
from engine.packs.math.geometry.catalog import CONSTRUCTIONS
from engine.packs.math.visuals.geometry_figure import render_construction_svg

_OUT = Path("records/work")
_PARAMS = {"base": 3.6, "angle": 62, "offset": 2.4}


def main() -> int:
    names = sys.argv[1:] or sorted(CONSTRUCTIONS)
    svgs = []
    for name in names:
        con = CONSTRUCTIONS[name](_PARAMS)
        svg = render_construction_svg(
            {
                "coords": con.coords,
                "segments": con.segments,
                "circles": con.circles,
                "equal_groups": [
                    [f.args[0], f.args[1]]
                    for f in con.givens
                    if f.kind == "seg_eq" and f.args[0] != f.args[1]
                ],
            }
        )
        path = _OUT / f"fig_{name}.svg"
        path.write_text(svg)
        svgs.append(path)
        print(f"{name}: {path}")
    for path in svgs:
        png = path.with_suffix(".png")
        subprocess.run(["rsvg-convert", "-z", "1.6", "-o", str(png), str(path)], check=True)
        print(f"-> {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
