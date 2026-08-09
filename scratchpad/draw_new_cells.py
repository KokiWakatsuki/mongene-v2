"""今回開いたセルの図を、**その family の定義域のパラメータで** PNG に起こす。

ゲートは図の内容の誤りを検出しない。二等辺三角形が上下逆さまだったことも、交点の
ラベルが線に埋もれていたことも、図に起こして初めて分かった。

実行:
  PYTHONPATH=. .venv/bin/python scratchpad/draw_new_cells.py
"""
from __future__ import annotations

import subprocess
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

_OUT = Path("scratchpad")
_CASES = {
    "pgram_definition_diagonal": {"base": 4.2, "angle": 81, "offset": 2.7},
    "pgram_diagonals_crossing": {"base": 4.0, "angle": 55, "offset": 2.6},
    "quad_bisecting_diagonals": {"base": 4.0, "angle": 55, "offset": 2.6},
    "quad_one_parallel_and_angle": {"base": 4.2, "angle": 81, "offset": 2.7},
    "pgram_equal_diagonals": {"base": 3.8, "angle": 60, "offset": 2.2},
    "pgram_isosceles_diagonal": {"base": 3.6, "angle": 75, "offset": 1.8},
    "bisector_perp_feet": {"base": 3.6, "angle": 69, "offset": 1.8},
    "bisector_perp_base": {"base": 3.6, "angle": 75, "offset": 1.8},
    "isosceles_two_altitudes": {"base": 3.9, "angle": 66, "offset": 2.5},
    "similar_hourglass": {"base": 3.6, "angle": 51, "offset": 2.1},
    "ratio_hourglass": {"base": 3.6, "angle": 51, "offset": 2.1},
    "circle_two_chords": {"base": 3.6, "angle": 84, "offset": 0.9},
    "circle_diameter_chords": {"base": 3.6, "angle": 72, "offset": 1.8},
    "circle_thales_isosceles": {"base": 3.6, "angle": 84, "offset": 1.8},
}


def main() -> int:
    for name, params in _CASES.items():
        con = CONSTRUCTIONS[name](params)
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
        path = _OUT / f"fig_new_{name}.svg"
        path.write_text(svg)
        subprocess.run(
            ["rsvg-convert", "-z", "1.5", "-o", str(path.with_suffix(".png")), str(path)],
            check=True,
        )
        print(f"{name} -> {path.with_suffix('.png')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
