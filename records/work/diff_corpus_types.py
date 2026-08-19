"""2つの INDEX.md の型数をセルごとに突き合わせる（作業0 の効き方を見る）。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/diff_corpus_types.py 旧 新
"""
import re
import sys

_CELL = re.compile(r"^## (\S+)\s+— 型 (\d+) 個")


def counts(path: str) -> dict[str, int]:
    out = {}
    for line in open(path, encoding="utf-8"):
        m = _CELL.match(line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


old, new = counts(sys.argv[1]), counts(sys.argv[2])
print(f"セル 旧 {len(old)} / 新 {len(new)}")
print(f"型の合計 旧 {sum(old.values())} → 新 {sum(new.values())}")
missing = sorted(set(old) - set(new))
added = sorted(set(new) - set(old))
if missing:
    print(f"新にないセル {len(missing)}: {missing[:10]}")
if added:
    print(f"旧にないセル {len(added)}: {added[:10]}")
down = [(old[c] - new[c], c, old[c], new[c]) for c in old if c in new and new[c] < old[c]]
up = [(new[c] - old[c], c, old[c], new[c]) for c in old if c in new and new[c] > old[c]]
print(f"\n減ったセル {len(down)} / 増えたセル {len(up)} / 変わらないセル "
      f"{len(set(old) & set(new)) - len(down) - len(up)}")
print("\n減り方が大きいセル（上位20）:")
for d, c, o, n in sorted(down, reverse=True)[:20]:
    print(f"  -{d:3d}  {c}: {o} → {n}")
if up:
    print("\n★増えたセル（作業0 では増えてはいけない・出たら調べる）:")
    for d, c, o, n in sorted(up, reverse=True):
        print(f"  +{d:3d}  {c}: {o} → {n}")
