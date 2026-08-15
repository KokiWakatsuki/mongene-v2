"""問題文に出てくる**数の丸さ**を、実物と私たちで比べる。

## なぜ測るか

逆翻訳で未読の form（knowledge/calculation/proof/graph_table/construction）を
読み始めたら、数学は正しいのに**数が教材の数に見えない**ものが並んだ。

```
1本 79 円の品物を x 本買ったときの代金
y = 208x のように、x の値が2倍、3倍になると…
「値上がり 449円」を +449円 と表すことにするとき、「値下がり 457円」を…
数 19 について、数直線上でそれに対応する点と原点とのきょり
```

市販品は 80円・100円・y=3x・500円 のように**丸い数**を使う。79 や 208 や 449 は
数学的には何の問題もないが、教材の文にはまず出ない。
どのゲートもここを見ていない（答えは正しい・日本語も正しい・重複もしない）。

「不自然に見える」で止めないために、実物と並べて数える。

## 数え方

問題文の中の整数を拾い、**丸さ**を2つの尺度で見る:

  末尾0率     … 10 の倍数の割合（80円・500円・20cm）
  常用数率    … 教材が繰り返し使う数の割合
                （1〜12・15・20・24・25・30・36・40・45・50・60・72・90・100…）

**1桁の数は除く。** どちらの側も 1〜9 が大半を占めて差が消える（式の係数・小問番号）。
丸さが問題になるのは2桁以上の数。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/ref_numbers.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

_REF = Path("records/work/ref")
_BT = Path("records/work/bt")

_INT = re.compile(r"(?<![\d.])(\d{2,4})(?![\d.])")

# 教材が繰り返し使う数（約数が多い・単位のきりがよい）。
_COMMON = {10, 11, 12, 14, 15, 16, 18, 20, 21, 24, 25, 27, 28, 30, 32, 35, 36, 40, 42,
           45, 48, 50, 54, 56, 60, 63, 64, 70, 72, 75, 80, 81, 84, 90, 96, 100, 120,
           125, 144, 150, 180, 200, 240, 250, 300, 360, 400, 500, 600, 800, 1000}


def measure(text: str) -> dict:
    nums = [int(m) for m in _INT.findall(re.sub(r"[ 　]+", "", text))]
    # 年号・調査年（20xx・平成/令和の年）は教材の数ではないので落とす。
    nums = [n for n in nums if not (1900 <= n <= 2100)]
    if not nums:
        return {"個数": 0}
    tail0 = sum(1 for n in nums if n % 10 == 0)
    common = sum(1 for n in nums if n in _COMMON)
    return {
        "個数": len(nums),
        "末尾0率": tail0 / len(nums),
        "常用数率": common / len(nums),
        "よく出る数": Counter(nums).most_common(8),
    }


def _ours() -> str:
    """私たちの問題文（逆翻訳の入力＝全 form の文型代表）。"""
    parts = []
    for p in sorted(_BT.glob("problems*.md")):
        # 見出し行（`## g1_l1.knowledge.Lv1#1`）は本文ではないので落とす。
        parts += [ln for ln in p.read_text(encoding="utf-8").splitlines()
                  if not ln.startswith(("#", "**", "式でも"))]
    return "\n".join(parts)


def main() -> int:
    rows: list[tuple[str, dict]] = []
    for p in sorted(_REF.glob("*.txt")):
        # 解説・正答例は「採点のための文書」で教材の文ではない（前に系統を取り違えて
        # 単位の書き方を測り間違えた）。問題そのものだけを見る。
        if any(k in p.stem for k in ("kaisetsu", "seitou", "tebiki", "sentaku", "list", "units")):
            continue
        m = measure(p.read_text(encoding="utf-8"))
        if m["個数"] >= 30:
            rows.append((p.stem, m))
    ours = measure(_ours())

    print(f"{'出典':<28}{'個数':>7}{'末尾0率':>9}{'常用数率':>10}")
    for name, m in rows:
        print(f"{name[:27]:<28}{m['個数']:>7}{m['末尾0率']:>8.0%}{m['常用数率']:>9.0%}")
    n = sum(m["個数"] for _, m in rows)
    t0 = sum(m["末尾0率"] * m["個数"] for _, m in rows) / n
    cm = sum(m["常用数率"] * m["個数"] for _, m in rows) / n
    print(f"\n{'実物 合計':<28}{n:>7}{t0:>8.0%}{cm:>9.0%}")
    print(f"{'私たち':<28}{ours['個数']:>7}{ours['末尾0率']:>8.0%}{ours['常用数率']:>9.0%}")
    print(f"\n私たちによく出る数: {ours['よく出る数']}")

    (_REF / "numbers.json").write_text(
        json.dumps({"実物": dict(rows), "私たち": ours}, ensure_ascii=False, indent=1,
                   default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
