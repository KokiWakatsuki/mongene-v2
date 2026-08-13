"""scan_defects の当たりを、セル単位で全部（マッチ箇所つきで）並べる。

走査の要約だけでは「どのセルが本物か」を選べない。**マッチした文字列そのもの**を
出して、偽陽性と本物を人が分けられるようにする。

実行: PYTHONPATH=. .venv/bin/python scratchpad/scan_detail.py <検査名の一部>
"""
from __future__ import annotations

import re
import sys

from scan_defects import _CHECKS, load  # type: ignore[import-not-found]

_SPACE = re.compile(r"[ぁ-んァ-ン一-龥] [ぁ-んァ-ン一-龥]")


def main() -> None:
    key = sys.argv[1]
    names = [n for n in _CHECKS if key in n]
    rows = load()
    for name in names:
        fn = _CHECKS[name]
        seen: dict[str, tuple[str, str]] = {}
        for cell, q, a in rows:
            if fn(q, a) and cell not in seen:
                seen[cell] = (q, a)
        print(f"■ {name}: {len(seen)} セル")
        for cell, (q, a) in sorted(seen.items()):
            m = _SPACE.search(q)
            extra = f"  ⟨{q[max(0, m.start() - 8):m.end() + 8]}⟩" if m else ""
            print(f"  {cell}{extra}")
            print(f"      Q {q.replace(chr(10), ' / ')[:100]}")
            print(f"      A {a[:70]}")
        print()


if __name__ == "__main__":
    main()
