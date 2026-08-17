"""**点名を伏せると同じ文になる問題**を、セルの中で探す。

## なぜ要るか

`dup_key` は params のハッシュで、params には点名（labels/slots）が入っている。
点名を入れたのは dup_rate を下げるためだったが、その結果
**数値も場面も完全に同じで、頂点名だけ違う問題を別物として数えている**。
生徒から見れば同じ問題が2回出る。

ここでは出来上がった本文で測る（params ではなく**実物**で見る）。
大文字1文字（点名）と、その並び（ABC・∠DEF）を伏せて突き合わせる。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/scan_same_but_names.py [コーパスのディレクトリ]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

_CELL = re.compile(r"^## (\S+)\s+— 型")
_TYPE = re.compile(r"^### 型\d+")
_UPPER = re.compile(r"[A-Z]")


def _mask(text: str) -> str:
    """大文字（点名）を伏せる。数値と日本語はそのまま残す。"""
    return _UPPER.sub("＊", text)


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "records/work/corpus")
    lines = (root / "INDEX.md").read_text(encoding="utf-8").splitlines()

    cell = ""
    in_problem = False
    buf: list[str] = []
    per_cell: dict[str, list[str]] = defaultdict(list)
    # **図があるセルは別に数える。** 作図のセルは本文に数が1つも無く、違いは
    # まるごと図（線分の向き・長さ）が持っている。本文が同じことは重複ではない。
    has_fig: dict[str, bool] = defaultdict(bool)
    cur_has_fig = False

    def flush() -> None:
        if cell and buf:
            per_cell[cell].append(" ".join(s.strip() for s in buf if s.strip()))
            if cur_has_fig:
                has_fig[cell] = True

    for line in lines:
        m = _CELL.match(line)
        if m:
            flush(); buf.clear()
            cell = m.group(1)
            in_problem = False
            continue
        if _TYPE.match(line):
            flush(); buf.clear()
            in_problem = False
            continue
        if line.startswith("**図**"):
            cur_has_fig = "（図なし）" not in line
            continue
        if line.startswith("**問題**"):
            in_problem = True
            continue
        if line.startswith("**") and in_problem:
            in_problem = False
            continue
        if in_problem:
            buf.append(line)
    flush()

    n_types = sum(len(v) for v in per_cell.values())
    hits: list[tuple[str, int, str]] = []
    for c, texts in per_cell.items():
        seen: dict[str, int] = defaultdict(int)
        for t in texts:
            if not _UPPER.search(t):
                continue  # 点名を持たない問題は対象外
            seen[_mask(t)] += 1
        for masked, n in seen.items():
            if n >= 2:
                hits.append((c, n, masked[:100]))

    no_fig = [h for h in hits if not has_fig[h[0]]]
    with_fig = [h for h in hits if has_fig[h[0]]]

    # **比べる相手の個数を出す。** 0 件が「無い」のか「読めていない」のかを分ける。
    print(f"読んだセル {len(per_cell)}／型 {n_types}\n")
    print(
        f"■ 図が無く、点名を伏せると同じ＝**本当の重複**: "
        f"{sum(n for _, n, _ in no_fig)} 問 / {len(no_fig)} 組"
    )
    print(
        f"□ 図があるセル（違いを図が持っているので重複ではない）: "
        f"{sum(n for _, n, _ in with_fig)} 問 / {len(with_fig)} 組\n"
    )
    for c, n, masked in sorted(no_fig, key=lambda r: -r[1]):
        print(f"  {c}  {n}問")
        print(f"    {masked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
