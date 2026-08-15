"""INDEX.md から、指定した条件に合うセルの節だけを抜き出す。

実行例:
  PYTHONPATH=engine_core .venv/bin/python records/work/extract_cells.py word_problem > /tmp/wp.md
  ... extract_cells.py 'g2_l[0-9]+[.]knowledge'
"""
import re
import sys
from pathlib import Path

_SRC = Path("records/work/corpus/INDEX.md")
_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def main() -> None:
    pat = re.compile(sys.argv[1])
    lines = _SRC.read_text(encoding="utf-8").splitlines()
    keep = False
    out: list[str] = []
    for line in lines:
        m = _CELL_RE.match(line)
        if m:
            keep = bool(pat.search(m.group(1)))
        if keep:
            out.append(line)
    sys.stdout.write("\n".join(out))


if __name__ == "__main__":
    main()
