"""等積変形（g2_l50）の構成を PNG に起こして目視する。

`draw_construction.py` と同じことをするが、**その単元の定義域のパラメータ**で描く
（既定値で描くと、実際に出題される図と違う形を見て安心してしまう）。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/draw_area.py
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from engine.packs.math.geometry import constructions_area  # noqa: F401  登録の副作用
from engine.packs.math.geometry.catalog import CONSTRUCTIONS
from engine.packs.math.visuals.geometry_figure import render_construction_svg

_OUT = Path("records/work")
_CASES = {
    "trapezoid_diagonals": {"base": 3.4, "angle": 58, "offset": 1.8},
    "triangle_median": {"base": 4.6, "angle": 84, "offset": 1.0},
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
        path = _OUT / f"fig_area_{name}.svg"
        path.write_text(svg)
        png = path.with_suffix(".png")
        subprocess.run(["rsvg-convert", "-z", "1.8", "-o", str(png), str(path)], check=True)
        print(f"{name} -> {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
