"""解説の**構成**を、実物と私たちで比べる。

## 実物の解説はどう書かれているか（2系統で共通していたもの）

```
佐賀県教委の学習プリント          005net（塾・解説サイト）
  ① x＋５＝１１                    6x = 8 +5x
  両辺から ５ をひいて，            6x -5x = 8 +5x -5x
  x＋５－５＝１１－５               　　右辺の+5xをなくすため 両辺に-5xする
  x＝６                            x = 8
  【ポイント】左辺を x だけに
  するために両辺に７をたすといいよ。
```

系統が違うのに同じ形をしている。共通しているのは3つ:

  1. **なぜその手をやるのかを書く**（「左辺を x だけにするために」「+5x をなくすため」）
  2. **両辺を操作した式をそのまま見せる**（`x＋５－５＝１１－５` の1行を省かない）
  3. **実際にやった操作を名指しする**（「５ をひいて」。「ひくか、たすか」とは書かない）

私たちの解説:

```
まず、等式の性質を使い、両辺から同じ数をひく（または加える）。（x = -2 - 5）
次に、両辺を計算して、解を求める。（x = -7）
```

3つとも無い。とくに **「（または加える）」は、その問題で何をしたのかを言っていない**。

## 数え方

  目的率     … 「〜ため」「〜ように」で手の**目的**を述べている解説の割合
  ぼかし率   … 「または」「など」「〜たり」で操作をぼかしている解説の割合

**教委・塾・教科書の解説だけを見る。** 採点の手引や正答例は「採点者のための文書」で
教材の解説ではない（前に系統を取り違えて単位の書き方を測り間違えた）。

実行:
  PYTHONPATH=records/work .venv/bin/python records/work/ref_explanations.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "records/work")
from scan_explanations import load  # noqa: E402

_REF = Path("records/work/ref")

# 解説が載っている実物だけ（索引ページ・問題のみのファイル・採点文書は除く）。
_REAL = ["kyoiku_saga_h23_eq", "kyoiku_saga_h24_prob", "kyoiku_asahikawa",
         "kyoiku_tokushima", "kyoiku_tokushima_step",
         "juku_005net_yoten", "juku_sukyo_kaisetsu", "juku_ways_kaisetsu",
         "juku_benesse_kaisetsu"]

# 手の**目的**を述べる言い方。「〜するため」「〜するように」「〜したいので」。
_PURPOSE = re.compile(r"(ために|ため，|ため、|ため\b|ためです|ように[しす]|よう[にに]する|"
                      r"したいので|なくすため|だけにする|そろえる|そろえて)")
# 操作をぼかす言い方。どちらをやったのか読み手に分からない。
_HEDGE = re.compile(r"(または|あるいは|など)")


def _sentences(t: str) -> list[str]:
    return [s for s in re.split(r"[。\n]", t) if len(s.strip()) >= 6]


def main() -> int:
    print("=== 実物 ===")
    print(f"{'出典':<28}{'文':>7}{'目的率':>8}{'ぼかし率':>9}")
    tot = pur = hed = 0
    for name in _REAL:
        p = _REF / f"{name}.txt"
        if not p.exists():
            continue
        ss = _sentences(re.sub(r"[ 　]+", "", p.read_text(encoding="utf-8")))
        if len(ss) < 20:
            continue
        a = sum(1 for s in ss if _PURPOSE.search(s))
        b = sum(1 for s in ss if _HEDGE.search(s))
        tot, pur, hed = tot + len(ss), pur + a, hed + b
        print(f"{name[:27]:<28}{len(ss):>7}{a/len(ss):>7.1%}{b/len(ss):>8.1%}")
    print(f"{'実物 合計':<28}{tot:>7}{pur/tot:>7.1%}{hed/tot:>8.1%}\n")

    rows = load()
    exps = [e for _, _, _, e, _ in rows if e.strip()]
    ss = [s for e in exps for s in _sentences(e)]
    a = sum(1 for s in ss if _PURPOSE.search(s))
    b = sum(1 for s in ss if _HEDGE.search(s))
    print("=== 私たち ===")
    print(f"{'コーパス全体':<28}{len(ss):>7}{a/len(ss):>7.1%}{b/len(ss):>8.1%}")

    hedged = Counter(s.strip() for s in ss if _HEDGE.search(s))
    print("\n=== ぼかしている解説の文（多い順・上位12）===")
    for s, n in hedged.most_common(12):
        print(f"  {n:>4}回  {s[:76]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
