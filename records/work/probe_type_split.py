"""作業0 の物差しを、セルを指定して実測する（build_corpus 全走の前の速い確認）。

判定は `build_corpus.measure_cell`（唯一の実装）を呼ぶ。ここには書かない。
実行例:
  .venv/bin/python records/work/probe_type_split.py \
      g2_l16:word_problem:2 exam_l5:word_problem:4
"""
import sys

from engine.eval._harness import make_env

sys.path.insert(0, "records/work")
from build_corpus import load_cells, measure_cell

env = make_env()
cells = {(u, f, lv): (cat, exp, fil) for u, f, lv, cat, exp, fil in load_cells()}

for arg in sys.argv[1:]:
    unit, form, lv_s = arg.split(":")
    level = int(lv_s)
    catalogs, expected, filler = cells[(unit, form, level)]
    m = measure_cell(unit, form, level, catalogs, expected, filler, env)
    print(f"{unit}.{form}.Lv{level}  文型 {len(m.types)}（期待 {m.expected}）"
          f"  ／ 語彙 {len(m.vocab)} 通り・数 {len(m.numbers)} 通り"
          f"  (seed {len(m.rows)}, 軸 {m.axes}, use_text={m.use_text},"
          f" 語彙のカタログ {m.demoted} 本)")
