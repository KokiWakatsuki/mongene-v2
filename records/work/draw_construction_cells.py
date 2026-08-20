"""作図セル（g1_l41〜l44 construction）の図を SVG/PNG に起こして目視する。

ゲートは図の中身の誤りを検出しない。作図の図では特に
  ・2つの弧が交わって見えるか（半径が小さいと交わらない）
  ・作図した線が弧の交点を通っているか
  ・点名が線に埋もれていないか
を目で見るしかない。

  .venv/bin/python records/work/draw_construction_cells.py [seed ...]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_OUT = Path("records/work/construction_figs")
_CELLS = [
    ("g1_l41", 1), ("g1_l41", 2),
    ("g1_l42", 1), ("g1_l42", 2),
    ("g1_l43", 1), ("g1_l43", 2),
    ("g1_l44", 2), ("g1_l44", 3), ("g1_l44", 4),
]


def main() -> int:
    seeds = [int(s) for s in sys.argv[1:]] or [1]
    bootstrap()
    env = make_env()
    _OUT.mkdir(parents=True, exist_ok=True)
    for unit, lv in _CELLS:
        for seed in seeds:
            req = GenerateRequest(
                subject="math", unit=unit, form="construction", level=lv, seed=seed
            )
            res = generate(
                req, curriculum=env.curriculum, families=env.families, registry=env.registry
            )
            if not hasattr(res, "problem_text"):
                print(f"!! {unit} Lv{lv} seed{seed}: {res}")
                continue
            print(f"--- {unit} Lv{lv} seed{seed}: {res.problem_text}")
            ans = res.sub_questions[0].answer
            for tag, svg in (("q", res.visual_svg), ("a", ans.solution_svg_ref)):
                stem = _OUT / f"{unit}_lv{lv}_s{seed}_{tag}"
                stem.with_suffix(".svg").write_text(svg, encoding="utf-8")
                subprocess.run(
                    ["rsvg-convert", "-z", "1.5", "-o",
                     str(stem.with_suffix(".png")), str(stem.with_suffix(".svg"))],
                    check=True,
                )
    print(f"\n=> {_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
