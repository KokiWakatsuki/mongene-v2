"""場面の抽選が「数 → 語彙」の順か「語彙 → 数」の順かを、コードから読み取る。

作業1 は**生成物を1文字も変えない**のが条件で、それは RNG の消費順が変わらないことと
同じである。層に割るときに順番を保てるかを先に測る。

判定は関数の本体に現れる呼び出しの順。語彙を引く呼び出しと数を引く呼び出しを分ける
（`_draw_priced_item` は**語彙と数を1回で引く**＝分けられない。別に数える）。

実行: .venv/bin/python records/work/scan_scene_draw_order.py
"""
import re
from collections import Counter

from engine_paths import RECIPES_DIR  # エンジンの場所は1か所で解決する

_DIR = RECIPES_DIR
_TARGETS = [
    "word_problem_linear.py", "word_problem_system.py",
    "word_problem_proportion_frequency.py", "word_problem_quadratic.py",
    "word_problem_expression.py",
]
# 語彙を引く呼び出し（品名・人名・場所・場面文のトークン）
_VOCAB = re.compile(r"_draw_pair_token|_draw_distinct\(|_draw_index\(|_draw_tokens|"
                    r"draw\(list\(p\[|draw\(\[")
# 語彙と数を1回で引く（分けられない）
_COUPLED = re.compile(r"_draw_priced_item")
# 数を引く呼び出し
_NUM = re.compile(r"draw(?:_many)?\(\s*p\[|draw(?:_many)?\(\{")

rows = []
for name in _TARGETS:
    src = (_DIR / name).read_text(encoding="utf-8")
    # 関数単位に切る
    parts = re.split(r"\ndef ", src)
    for part in parts:
        head = part.split("(", 1)[0]
        if not head.startswith("_scene_"):
            continue
        body = part
        seq: list[str] = []
        for line in body.splitlines():
            if _COUPLED.search(line):
                seq.append("両")
            elif _VOCAB.search(line):
                seq.append("語")
            elif _NUM.search(line):
                seq.append("数")
        order = "".join(seq)
        if "両" in order:
            kind = "分けられない（語彙と数を1回で引く）"
        elif not order.strip("数") and order:
            kind = "語彙を引かない"
        elif order.lstrip("数").rstrip("語") == "" and order:
            kind = "数 → 語彙"
        elif order.lstrip("語").rstrip("数") == "" and order:
            kind = "語彙 → 数"
        else:
            kind = "入り混じる"
        rows.append((name, head, order or "(引かない)", kind))

for name in _TARGETS:
    sub = [r for r in rows if r[0] == name]
    print(f"\n## {name}  （場面 {len(sub)}）")
    for _n, fn, order, kind in sub:
        print(f"  {fn:44s} {order:16s} {kind}")

print("\n--- まとめ ---")
c = Counter(r[3] for r in rows)
for k, v in c.most_common():
    print(f"  {k}: {v}")
