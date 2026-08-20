"""**解答図**を全部 PNG に起こす（問題図とは別の面）。

コーパスの図（`records/work/corpus/figs`）は `Problem.visual_svg` ＝**問題図**だけで、
`GraphAnswer.solution_svg_ref` ＝**解答図**は1枚も入っていない。
「グラフをかけ」「移した図形をかけ」のセルでは、問題図は空の方眼で、
**中身があるのは解答図のほう**である。つまり今まで見ていたのは、それらのセルの
「何も描いていない側」だけだった。

実行:
  .venv/bin/python records/work/dump_solution_figs.py <出力ディレクトリ>
"""
from __future__ import annotations

import sys
from pathlib import Path

import cairosvg

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, family_of, make_env


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "records/work/solution_figs")
    out.mkdir(parents=True, exist_ok=True)
    env = make_env()
    n_cells = 0
    written = 0
    for coord in capability_cells(env):
        n_cells += 1
        res = generate(
            cell_request(coord, 1),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        for sq in res.sub_questions:
            svg = getattr(sq.answer, "solution_svg_ref", "")
            if not svg:
                continue
            stem = f"{family_of(coord)}.Lv{coord.level}".replace("math.", "")
            cairosvg.svg2png(
                bytestring=svg.encode("utf-8"),
                write_to=str(out / f"{stem}.png"),
                output_width=520, background_color="white",
            )
            written += 1
    # **比べる相手の個数も出す。** 0 枚だったときに「解答図が無い」のか
    # 「走査が動いていない」のか、これが無いと分からない。
    print(f"セル {n_cells} を見て、解答図 {written} 枚を {out} に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
