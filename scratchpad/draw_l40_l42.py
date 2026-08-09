"""g2_l40/l41/l42 の新しい構成を PNG に起こして目視する。

ゲートもテストも**図の内容の誤り**は検出しない（点の並び違い・線が枠外・ラベル消失）。
この一連でも目視だけで見つけたバグが4件ある。だから図は必ず起こして見る。

実行: PYTHONPATH=. .venv/bin/python scratchpad/draw_l40_l42.py
"""
from __future__ import annotations

from pathlib import Path

import cairosvg

from engine.packs.math.geometry import (  # noqa: F401  登録の副作用
    constructions_congruence,
    constructions_right_triangle,
)
from engine.packs.math.recipes.geometry_proof import build_problem
from engine.packs.math.geometry.facts import fact_text
from engine.packs.math.visuals.geometry_figure import render_construction_svg

_CASES = (
    ("kite_diagonals", "congruence", 4, {"base": 3.2, "angle": 74, "offset": 3.6}),
    ("isosceles_equal_segments", "congruence", 3, {"base": 3.4, "angle": 62, "offset": 3.0}),
    ("equal_altitudes", "right_triangle", 3, {"base": 3.6, "angle": 78, "offset": 2.8}),
)


def main() -> int:
    out = Path("scratchpad/figs_l40_l42")
    out.mkdir(exist_ok=True)
    for kind, topic, depth, params in _CASES:
        built = build_problem(kind, params, level=4, topic_set=topic, depth=depth, prefer="seg_eq")
        if built is None:
            print(f"[NG] {kind}: 質のフィルタを通らなかった {params}")
            continue
        con, _ded, goal, lines = built
        print(f"[OK] {kind}: {con.description or ''} / 結論 {fact_text(goal.fact)}")
        for line in lines:
            print(f"    {line.claim}  （{line.reason}）")
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
        png = out / f"{kind}.png"
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(png), scale=2.0)
        print(f"    -> {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
