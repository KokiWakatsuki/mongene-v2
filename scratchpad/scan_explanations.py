"""コーパスの**解説とヒント**を走査する。

`scan_defects.py` は問題文と答えしか見ていない（解説・ヒントの行に来たら
`mode = None` にして捨てている）。過去のセッションで解説から出た欠陥
（D-25 の生の sympy `Eq(5*x + y, 45)`・D-17 の中身のないヒント）は、
どれも別の作業のついでに人が気づいたもので、**面として走査されたことがない**。

ここは 1,466 型ぶんある。実行:
    PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/scan_explanations.py
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_SRC = Path("scratchpad/corpus/INDEX.md")
_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def load() -> list[tuple[str, str, str, str, str]]:
    """(セル, 問題文, 答え, 解説, ヒント) の一覧。"""
    out: list[tuple[str, str, str, str, str]] = []
    cell = pending = ""
    buf: dict[str, list[str]] = {"q": [], "a": [], "e": [], "h": []}
    mode: str | None = None

    def flush() -> None:
        if buf["q"]:
            out.append((
                pending,
                "\n".join(buf["q"]).strip(),
                "\n".join(buf["a"]).strip(),
                "\n".join(buf["e"]).strip(),
                "\n".join(buf["h"]).strip(),
            ))

    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cell = m.group(1)
            continue
        if line.startswith("**問題**"):
            flush()
            pending = cell
            buf = {"q": [], "a": [], "e": [], "h": []}
            mode = "q"
            continue
        for marker, key in (("**答え**", "a"), ("**解説**", "e"), ("**ヒント**", "h")):
            if line.startswith(marker):
                buf[key] = [line.removeprefix(marker).strip()]
                mode = key
                break
        else:
            # 節の切れ目。ここで止めないと `### 型1 `kind=...`` のような
            # 見出しを解説に取り込んでしまう（実際に偽陽性2件を出した）。
            if line.startswith(("**問い**", "**図**", "---", "#")):
                mode = None
                continue
            if mode:
                buf[mode].append(line)
            continue
    flush()
    return out


def _answer_parts(a: str) -> list[str]:
    """答えを小問ごとに割り、「(1) 」のような番号を外す。

    複数小問の答えは `(1) +2300円 ／ (2) -1300円`。番号つきのまま解説を探すと
    全部「出てこない」になる。
    """
    parts = []
    for chunk in re.split(r"[／/、]", a):
        t = re.sub(r"^\(\d+\)\s*", "", chunk.strip()).strip()
        if t:
            parts.append(t)
    return parts


# 1手ぶん = 「…（指示の文）。（結果）」
_STEP_RE = re.compile(r"([^。\n]*)。（([^（）]*)）")


def _overlap(a: str, b: str) -> float:
    """b の文字が a にどれだけ含まれるか（0〜1）。順序は見ない粗い尺度。"""
    if not b:
        return 0.0
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    common = sum(min(cb[ch], ca[ch]) for ch in cb)
    return common / len(b)


def _restated_steps(e: str) -> list[str]:
    """括弧の中が、直前の指示文の言い直しになっている手。

    括弧には**その手で得たもの**（値・図形・式）が入るのが設計。指示文と
    ほぼ同じ文字でできているなら、読んでも新しいことが1つも増えない。
    規則そのものを述べている括弧（「共通の符号をそのままつけ…」など）は
    指示文と語が違うので、この尺度では落ちない。
    """
    out = []
    for m in _STEP_RE.finditer(e):
        instruction, result = m.group(1).strip(), m.group(2).strip()
        # 「まず、」「次に、」「最後に、」は指示文の飾りなので外す
        instruction = re.sub(r"^(まず|次に|最後に)、", "", instruction)
        if len(result) >= 6 and _overlap(instruction, result) >= 0.9:
            out.append(result)
    return out



# q, a, e（解説）, h（ヒント）を受け取る
_CHECKS: dict[str, object] = {
    # D-25 の再発検査。sympy の内部表現が日本語の解説に混ざる。
    "解説に生の sympy が出ている": lambda q, a, e, h: bool(
        re.search(r"\b(Eq|Rational|Symbol|Integer|Float|Pow|Mul|Add|sqrt|Abs)\s*\(", e + h)
    ),
    # Python のリスト・辞書・タプルがそのまま出ている。
    "解説に Python の値が出ている": lambda q, a, e, h: bool(
        re.search(r"\[\s*'|\"\s*\]|\{\s*'|None\b|True\b|False\b", e + h)
    ),
    "解説が空": lambda q, a, e, h: not e.strip(),
    "ヒントが空": lambda q, a, e, h: not h.strip(),
    # D-17（中身のないヒント）の解説版。
    # 解説の各手は「〜する。（結果）」の形で、括弧には**その手で得たもの**が入る。
    # 括弧の中が指示の言い直し（動詞で終わる）だと、読んでも何も分からない。
    #   悪い: まず、…かを読み取る。（どちらの向きを…かを読み取る）
    #   良い: まず、点Cを中心に弧をかく。（点Cを中心とする弧）
    "解説の括弧が指示の言い直し": lambda q, a, e, h: bool(_restated_steps(e)),
    # 語と助詞の間の半角スペース（D-3 の解説側）。
    "解説にかなと語の間の半角スペース": lambda q, a, e, h: bool(
        re.search(r"[ぁ-んァ-ヶ一-龥] [をがはにでとへのも]", e + h)
    ),
    "解説に英字の変数名が残る": lambda q, a, e, h: bool(
        re.search(r"\b(lhs|rhs|expr|val|tmp|res|ans|obj|params?|kind)\b", e + h)
    ),
    "解説の分母が13以上": lambda q, a, e, h: bool(
        re.search(r"-?\d+/(1[3-9]|[2-9]\d+)\b", e)
    ),
    "解説が1文しかない": lambda q, a, e, h: bool(
        e.strip() and e.count("。") <= 1 and len(e) < 24
    ),
}


def main() -> None:
    rows = load()
    hits: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for cell, q, a, e, h in rows:
        for name, fn in _CHECKS.items():
            try:
                if fn(q, a, e, h):  # type: ignore[operator]
                    hits[name].append((cell, q, a, e))
            except Exception:  # noqa: BLE001
                pass
    print(f"走査した問題 {len(rows)} 個（解説つき {sum(1 for r in rows if r[3])} 個）\n")
    for name in _CHECKS:
        found = hits.get(name, [])
        cells = sorted({c for c, _, _, _ in found})
        print(f"■ {name}: {len(found)} 問 / {len(cells)} セル")
        for cell, q, a, e in found[:4]:
            print(f"    {cell}")
            print(f"      Q {q.replace(chr(10), ' / ')[:76]}")
            print(f"      A {a[:56]}")
            print(f"      解説 {e.replace(chr(10), ' / ')[:76]}")
        if len(cells) > 4:
            print(f"    … ほか {len(cells) - 4} セル")
        print()


if __name__ == "__main__":
    main()
