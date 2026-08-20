"""解説を**そのまま**（切り詰めずに）form ごとのファイルに書き出す。

読ませるための道具。過去に `dump_seeds.py` が答えを 60 字で打ち切っていて
「答えが欠けている」の誤報告が3件出たので、**ここでは一切切らない**
（末尾に総文字数を出して、削っていないことを読み手が確かめられるようにする）。

実行:
  PYTHONPATH=records/work .venv/bin/python \
      records/work/dump_explanation_slices.py <出力ディレクトリ>
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

from scan_explanations import load

# 読む単位。1ファイルが大きくなりすぎない範囲で、似た解説がまとまるように束ねる。
_GROUPS: dict[str, tuple[str, ...]] = {
    "calculation": ("calculation",),
    "find_value": ("find_value",),
    "word_problem": ("word_problem",),
    "graph_construction": ("graph_table", "construction"),
    "knowledge_proof": ("knowledge", "proof"),
}


def main() -> int:
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    by_form: dict[str, list] = defaultdict(list)
    for cell, q, a, e, h in load():
        form = cell.split(".")[1] if "." in cell else "?"
        by_form[form].append((cell, q, a, e, h))

    for name, forms in _GROUPS.items():
        rows = [r for f in forms for r in by_form.get(f, [])]
        # 単元順（g1 → g2 → g3 → exam）に並べる。読むときに難易度順になる。
        rows.sort(key=lambda r: r[0])
        buf = [f"# {name}: {len(rows)} 問\n"]
        for cell, q, a, e, h in rows:
            buf.append(f"\n## {cell}")
            buf.append(f"**問題** {q}")
            buf.append(f"**答え** {a}")
            buf.append(f"**解説** {e}")
            buf.append(f"**ヒント** {h}")
        text = "\n".join(buf)
        path = out_dir / f"{name}.md"
        path.write_text(text, encoding="utf-8")
        print(f"{path}  {len(rows):>4} 問  {len(text):>8} 字（切り詰めなし）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
