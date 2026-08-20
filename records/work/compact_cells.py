"""INDEX.md から、指定したセルの「問題」と「答え」だけを1問1ブロックで抜き出す。

解説・ヒントを落として密度を上げる（精読の1周目用）。

実行: .venv/bin/python records/work/compact_cells.py word_problem
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_SRC = Path("records/work/corpus/INDEX.md")
_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def main() -> None:
    pat = re.compile(sys.argv[1])
    cell = ""
    keep = False
    mode = None
    q: list[str] = []
    a = ""
    out: list[str] = []

    def flush() -> None:
        if q:
            body = " / ".join(x for x in (s.strip() for s in q) if x)
            out.append(f"[{cell}] {body}\n    → {a}")

    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            if keep:
                flush()
            q, a, mode = [], "", None
            cell = m.group(1)
            keep = bool(pat.search(cell))
            continue
        if not keep:
            continue
        if line.startswith("**問題**"):
            flush()
            q, a, mode = [], "", "q"
            continue
        if line.startswith("**答え**"):
            a = line.removeprefix("**答え**").strip()
            mode = None
            continue
        if line.startswith("**") or line.startswith("---") or line.startswith("### "):
            mode = None
            continue
        if mode == "q":
            q.append(line)
    if keep:
        flush()
    sys.stdout.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
