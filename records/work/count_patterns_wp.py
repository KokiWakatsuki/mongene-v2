"""型を「語彙と数を除いた構成」で数え直す（＝文型の数）。

いまの型の数え方（build_corpus）は narration の数値だけを伏せている。
語彙（品物名・人名・場面の名詞）は params の slots に入っていて、これが型として
数えられている。ユーザーの定義では語彙違いは同じ問題なので、slots も伏せて数える。
"""
import json
import re
import sys
from engine.core.contracts import Coordinate
from engine.eval._harness import build_mr, make_env
sys.path.insert(0, "records/work")
from build_corpus import load_cells

env = make_env()
_FLAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def structure_key(params) -> str:
    """文型の骨格＝**構成フラグだけ**（数値でも語彙でもないもの）。

    ★はじめは「surface らしい鍵の名前」を並べて除いていたが、`item_a`（語彙）や
    `line_cost`（係数の並び）を取りこぼし、seed の数だけ文型があることになった
    （100セルすべて 30 種＝走査が動いていない証拠）。鍵の名前で選ばず、**値の型**で
    選ぶ: 真偽値と、ASCII の識別子らしい文字列（mode・variant・method・
    scenario_kind など）だけを残す。数・数の並び・日本語（語彙）は落とす。
    """
    out = {}
    for k, v in params.items():
        if isinstance(v, bool):
            out[k] = v
        elif isinstance(v, str) and _FLAG_RE.match(v):
            out[k] = v
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


rows = []
for unit, form, level, _c, _e in load_cells():
    if form != "word_problem":
        continue
    keys, ok = set(), 0
    for seed in range(1, 31):
        r = build_mr(Coordinate(subject="math", unit=unit, form=form, level=level), seed, env)
        if not r.ok or r.mr is None:
            continue
        ok += 1
        keys.add(structure_key(r.mr.params))
    rows.append((f"{unit}.Lv{level}", len(keys), ok))

total_pat = sum(n for _, n, _ in rows)
print(f"word_problem のセル {len(rows)} / 文型の総数 {total_pat}")
print(f"文型が1つしかないセル: {sum(1 for _, n, _ in rows if n == 1)}")
print(f"文型が2つ以上あるセル: {sum(1 for _, n, _ in rows if n >= 2)}")
print("\n文型が多いセル:")
for k, n, _ in sorted(rows, key=lambda r: -r[1])[:8]:
    print(f"  {k}: {n} 文型")
