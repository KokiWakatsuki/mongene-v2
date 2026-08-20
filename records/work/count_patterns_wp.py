"""word_problem の**文型**を数える（式と場面の切り離しの物差し）。

型の数え方そのものは `build_corpus.measure_cell` が持っている。**ここには判定を
書かない**——同じ規約を2か所に書くと、片方を直しても数字が変わらない
（頂点名から `I` を外す作業で4か所に散っていて、1か所直しても消えなかった）。

作業0 の前は、この道具だけが「構成フラグだけ」を見て文型を数えていて、本体
（build_corpus）は語彙違いを別の型として数えていた（g2_l16.word_problem.Lv2 が
49型／文型は1つ）。作業0 で本体側に語彙の伏せ字を入れ、この道具は本体を呼ぶだけに
なった。

実行: .venv/bin/python records/work/count_patterns_wp.py
"""
import sys

from engine.eval._harness import make_env

sys.path.insert(0, "records/work")
from build_corpus import load_cells, measure_cell

env = make_env()
rows = []
for unit, form, level, catalogs, expected, filler_words in load_cells():
    if form != "word_problem":
        continue
    m = measure_cell(unit, form, level, catalogs, expected, filler_words, env)
    rows.append((f"{unit}.Lv{level}", len(m.types), len(m.vocab), len(m.numbers),
                 len(m.rows)))

total_pat = sum(n for _, n, _, _, _ in rows)
print(f"word_problem のセル {len(rows)} / 文型の総数 {total_pat}")
print(f"文型が1つしかないセル: {sum(1 for _, n, _, _, _ in rows if n == 1)}")
print(f"文型が2つ以上あるセル: {sum(1 for _, n, _, _, _ in rows if n >= 2)}")
print(f"（型として数えない）語彙 {sum(v for _, _, v, _, _ in rows)} 通り"
      f"・数 {sum(x for _, _, _, x, _ in rows)} 通り")
print("\n文型が多いセル:")
for k, n, v, x, s in sorted(rows, key=lambda r: -r[1])[:10]:
    print(f"  {k}: {n} 文型（語彙 {v}・数 {x} / {s} seed）")
