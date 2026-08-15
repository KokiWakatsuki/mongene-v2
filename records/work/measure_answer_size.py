"""答えの大きさ（分母・分子・根号の中）の分布を、コーパスの全型で測る。

`scan_big_numbers.py` は「問題文に出る最大の数」を並べるだけで**合否の基準を持って
いない**（道具の説明自身が「数が大きいこと自体は欠陥ではない」と書いている）。
ゲートにする前に、**上限をどこに置くと何セルが引っかかるか**を先に数えるための道具。

測るのは答えだけ。問題文の数は、標本調査の「20000個」・有効数字の「9780」のように
大きくて正しいものがあるので基準にならない。答えの分母・分子・根号の中は、
「教材として書き写せる形か」に直に効く。

実行:
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/measure_answer_size.py
"""
from __future__ import annotations

from collections import defaultdict

from engine.eval.answer_size import answer_magnitudes
from scan_explanations import load


def main() -> None:
    rows = load()
    # セル -> (分母, 分子, 根号の中) の最大
    worst: dict[str, tuple[int, int, int, str]] = {}
    for cell, _q, a, _e, _h in rows:
        m = answer_magnitudes(a)
        cur = worst.get(cell, (0, 0, 0, ""))
        cand = (
            max(cur[0], m.denominator),
            max(cur[1], m.numerator),
            max(cur[2], m.radicand),
        )
        sample = a if cand != cur[:3] else cur[3]
        worst[cell] = (*cand, sample)

    for label, idx in (("分母", 0), ("分子", 1), ("根号の中", 2)):
        ranked = sorted(worst.items(), key=lambda kv: -kv[1][idx])
        print(f"\n=== {label}の大きい順（上位25セル） ===")
        for cell, vals in ranked[:25]:
            if vals[idx] == 0:
                break
            print(f"  {vals[idx]:>7}  {cell}")
            print(f"           A: {vals[3][:70]}")

        print(f"  -- {label} の分布 --")
        buckets = [(1, 12), (13, 20), (21, 50), (51, 100), (101, 1000), (1001, 10**18)]
        for lo, hi in buckets:
            cells = [c for c, v in worst.items() if lo <= v[idx] <= hi]
            print(f"    {lo}〜{hi if hi < 10**18 else ''}: {len(cells)} セル")

    # 単元ごとにまとめて、上限を超えるのがどの単元に偏るかを見る
    print("\n=== 分母13以上のセルを単元別に ===")
    by_unit: dict[str, list[str]] = defaultdict(list)
    for cell, v in worst.items():
        if v[0] >= 13:
            by_unit[cell.split(".")[0]].append(f"{cell}(分母{v[0]})")
    for unit in sorted(by_unit):
        print(f"  {unit}: {' '.join(sorted(by_unit[unit]))}")


if __name__ == "__main__":
    main()
