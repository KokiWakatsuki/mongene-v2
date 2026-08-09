"""コーパスを機械で走査して、質の疑わしい箇所を型ごとに数える。

読むだけでは規模が分からない。**同じ粗さが何セルに出ているか**を先に測ってから、
実物と突き合わせる。ここで拾うのは「疑い」であって、確定した欠陥ではない。

実行: PYTHONPATH=. .venv/bin/python scratchpad/scan_defects.py
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_SRC = Path("scratchpad/corpus/INDEX.md")

_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def load() -> list[tuple[str, str, str]]:
    """(セル, 問題文, 答え) の一覧。"""
    out = []
    cell = ""
    pending_cell = ""   # いま溜めている問題が属するセル（次のセルに入っても書き換えない）
    q: list[str] = []
    a: list[str] = []
    mode = None
    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cell = m.group(1)
            continue
        if line.startswith("**問題**"):
            if q:
                out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip()))
            pending_cell = cell
            q, a, mode = [], [], "q"
            continue
        if line.startswith("**問い**"):
            mode = None
            continue
        if line.startswith("**答え**"):
            a = [line.removeprefix("**答え**").strip()]
            mode = "a"
            continue
        if line.startswith("**解説**") or line.startswith("**ヒント**") or line.startswith("**図**"):
            mode = None
            continue
        if mode == "q":
            q.append(line)
        elif mode == "a":
            a.append(line)
    if q:
        out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip()))
    return out


_CHECKS: dict[str, callable] = {
    "答えが分母13以上の分数": lambda q, a: bool(
        re.search(r"-?\d+/(1[3-9]|[2-9]\d+)\b", a)
    ),
    "問題文に絶対値記号があるのに『絶対値を求めよ』": lambda q, a: (
        "絶対値を求め" in q and "|" in q
    ),
    "かなと語の間の半角スペース": lambda q, a: bool(
        re.search(r"[ぁ-んァ-ン一-龥] [ぁ-んァ-ン一-龥]", q)
    ),
    "『である』が二重": lambda q, a: bool(re.search(r"である\s*であること", q)),
    "小数と分数が混在": lambda q, a: bool(
        re.search(r"\d/\d", q) and re.search(r"\d\.\d", q)
    ),
    "答えが空": lambda q, a: not a.strip(),
    "問題文に英字の符号が残る": lambda q, a: bool(
        re.search(r"\b(choice|value|proof_text|draw_\w+|read_\w+)\b", q)
    ),
    "答えの分数が帯分数にすべき大きさ": lambda q, a: bool(
        re.search(r"-?(\d{3,})/(\d+)", a)
    ),
    # --- ここから 2026-08-10 追加（D-28 の7件のうち5件をこの2つが釣り上げた） ---
    # **存在しない道具**（D-13 の再発検査）。さいころは6面、硬貨は2面。
    # カードは教材の枚数（〜20枚）まで。1セル直しても同じ単元の別セルに残る。
    "存在しない面数の道具": lambda q, a: bool(
        re.search(r"1から([7-9]|[1-9]\d+)までの目が出る", q)
        or re.search(r"1から([2-9]\d+)までの番号", q)
    ),
    # **相対度数・割合は小数で答える**（D-19/D-24 の再発検査）。
    "相対度数・割合を分数で答えている": lambda q, a: bool(
        re.search(r"(相対度数|割合|確率を.{0,6}推定)", q) and re.search(r"\d+/\d+", a)
        and "確率を求め" not in q  # 確率そのものは分数で答えるのが作法
    ),
}


def main() -> None:
    rows = load()
    hits: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for cell, q, a in rows:
        for name, fn in _CHECKS.items():
            try:
                if fn(q, a):
                    hits[name].append((cell, q, a))
            except Exception:  # noqa: BLE001
                pass
    print(f"走査した問題 {len(rows)} 個\n")
    for name in _CHECKS:
        found = hits.get(name, [])
        cells = sorted({c for c, _, _ in found})
        print(f"■ {name}: {len(found)} 問 / {len(cells)} セル")
        for cell, q, a in found[:4]:
            one = q.replace("\n", " / ")[:78]
            print(f"    {cell}\n      Q {one}\n      A {a[:60]}")
        if len(cells) > 4:
            print(f"    … ほか {len(cells) - 4} セル")
        print()


if __name__ == "__main__":
    main()
