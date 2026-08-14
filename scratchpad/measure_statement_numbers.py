"""問題文に出る数を**単位ごとに**測る（上限を決める前の数え上げ）。

`answer_size` は答えだけを測る。問題文の数は「20000個」（標本調査）・「9780」
（有効数字）のように大きくて正しいものがあるので、一律の上限は置けない。
しかし**単位を見れば話が変わる**——「1辺 59cm の正方形」「対角線 333cm の長方形」は、
数そのものではなく「その単位でその大きさはありえない」という欠陥である。

そこで数を**直後の単位ごとに**集めて分布を出す。上限はこの実測から決める。

実行:
  PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/measure_statement_numbers.py
"""
from __future__ import annotations

import re
from collections import defaultdict

from scan_explanations import load

# 数 + 単位。単位は長いものから並べる（cm² を cm と読み違えない）。
_UNITS = (
    "cm²|cm³|cm|mm|km|m²|m³|m|kg|g|mL|L|円|個|人|本|枚|冊|台|匹|羽|袋|箱|"
    "度|°|%|秒|分間|分|時間|時|回|問|点|km/h|m/分"
)
_NUM_UNIT = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNITS})")


def main() -> None:
    # 単位 -> [(値, セル, 問題文の一部)]
    by_unit: dict[str, list[tuple[float, str, str]]] = defaultdict(list)
    for cell, q, _a, _e, _h in load():
        for value, unit in _NUM_UNIT.findall(q):
            by_unit[unit].append((float(value), cell, q.replace("\n", " ")[:70]))

    print(f"{'単位':<6} {'件数':>5} {'最大':>9} {'99%':>8} {'中央':>7}  最大の実物")
    for unit in sorted(by_unit, key=lambda u: -max(v for v, _, _ in by_unit[u])):
        rows = sorted(by_unit[unit], reverse=True)
        vals = [v for v, _, _ in rows]
        p99 = vals[len(vals) // 100] if len(vals) >= 100 else vals[0]
        med = vals[len(vals) // 2]
        top_v, top_cell, top_q = rows[0]
        print(f"{unit:<6} {len(rows):>5} {top_v:>9.0f} {p99:>8.0f} {med:>7.0f}  {top_cell}")
        print(f"{'':>31}  {top_q}")


if __name__ == "__main__":
    main()
