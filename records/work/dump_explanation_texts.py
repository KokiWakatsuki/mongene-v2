"""解説の日本語を**読むため**に、文型ごとに束ねて出す。

5回目までの走査（`scan_explanations.py`）は機械の8検査だけで、**解説の日本語そのものは
読まれていない**。1,466型ぶんを素で読むと、同じ文型が何百回も出てくる（解説は solver の
narration から作られるので、セルが違っても文型は同じ）。

そこで**数と記号を伏せた文型**でまとめ、代表1件と出現数だけを出す。文型を読み切れば
日本語は読み切ったことになる。多い順に並べるので、上から読むと影響の大きい順になる。

実行:
  PYTHONPATH=records/work .venv/bin/python records/work/dump_explanation_texts.py [--min N]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict

from scan_explanations import load

# 数・式・記号を伏せる。文型だけを残す。
_MASKS = (
    (re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?"), "#"),
    (re.compile(r"[A-Za-z]"), "@"),
    (re.compile(r"[#@]+"), "N"),
)

_STEP_RE = re.compile(r"([^。\n]*)。（([^（）]*)）")


def skeleton(s: str) -> str:
    for pat, rep in _MASKS:
        s = pat.sub(rep, s)
    return s.strip()


def main() -> None:
    min_n = 1
    if "--min" in sys.argv:
        min_n = int(sys.argv[sys.argv.index("--min") + 1])

    # 文型 -> (件数, 代表セル, 代表の実物)
    groups: dict[str, list] = defaultdict(lambda: [0, "", ""])
    for cell, _q, _a, e, _h in load():
        for m in _STEP_RE.finditer(e):
            instruction = m.group(1).strip()
            key = skeleton(instruction)
            g = groups[key]
            g[0] += 1
            if not g[1]:
                g[1], g[2] = cell, instruction
        # 括弧の形になっていない行（1文の解説など）も拾う
        for line in e.splitlines():
            if line.strip() and "（" not in line:
                key = skeleton(line)
                g = groups[key]
                g[0] += 1
                if not g[1]:
                    g[1], g[2] = cell, line.strip()

    ranked = sorted(groups.items(), key=lambda kv: -kv[1][0])
    shown = [(k, v) for k, v in ranked if v[0] >= min_n]
    print(f"# 解説の文型 {len(ranked)} 種（出現 {sum(v[0] for _, v in ranked)} 手）"
          f" / {len(shown)} 種を表示\n")
    for _key, (n, cell, sample) in shown:
        print(f"[{n:>4}] {cell}")
        print(f"       {sample}")


if __name__ == "__main__":
    main()
