"""証明の図に、**仮定の記号**が描かれているかを見る。

## なぜ見るか

実物の証明の図は、仮定を必ず記号で示す。

  AB＝AC        → 2辺に等しい印（/ // ///）
  DE∥BC        → 2直線に平行の印（▷ ▷▷）
  AD⊥BC        → 交点に直角の印（□）
  O は AD の中点 → AO と OD に等しい印

記号が無いと、生徒は本文と図を何度も往復しないと図が読めない。
座標の照合（`check_figure_matches_givens.py`）は「点の位置が仮定と合っているか」を
見るが、**印が描かれているかは見ない**。ここはその面。

★**目視で判断しない。** 回転した正三角形は、目には不等辺三角形に見える
（実際 g2_l43 の図を「正三角形に描けていない」と読み違えた。測ったら3辺とも
303.1 で正しかった）。図のことは必ず座標と要素で数える。

実行: .venv/bin/python records/work/scan_figure_marks.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_FIGS = Path("records/work/corpus/figs")
_INDEX = Path("records/work/corpus/INDEX.md")

# 図の中の記号。**実装を読んでから決める**（当てずっぽうの正規表現は 0件を出す）。
# 証明の図 40 枚に出てくる要素は line・circle・text・rect の4つだけで、
# 図形の線は stroke-width 1.6、印は 1.2 で引かれている。
#   等長の印 … stroke-width 1.2 の短い線
#   直角の印 … **描く手段が無い**（□ を描く polyline / path が1つも無い）
#   平行の印 … **描く手段が無い**
_TICK = re.compile(r'<line[^>]*stroke-width="1\.2"')
_RIGHT = re.compile(r'<(?:polyline|path)[^>]*|<rect[^>]*width="(?:[1-9]|1[0-9])\.')
_PARA = re.compile(r'<(?:polyline|polygon|marker)[^>]*')

# 本文が述べている仮定
_H_EQ = re.compile(r"([A-Z]{2})\s*[＝=]\s*([A-Z]{2})")
_H_PARA = re.compile(r"([A-Z]{2})\s*∥\s*([A-Z]{2})")
_H_PERP = re.compile(r"([A-Z]{2})\s*⊥\s*([A-Z]{2})")
_H_MID = re.compile(r"中点")

_CELL = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def _problems() -> dict[str, str]:
    """セル → 問題文（最初の型のもの）。"""
    out: dict[str, str] = {}
    cell = ""
    grab = False
    buf: list[str] = []
    for ln in _INDEX.read_text(encoding="utf-8").splitlines():
        m = _CELL.match(ln)
        if m:
            if cell and cell not in out:
                out[cell] = " ".join(buf)
            cell, buf, grab = m.group(1), [], False
        elif ln.startswith("**問題**"):
            grab = True
        elif ln.startswith("**") and grab:
            grab = False
        elif grab and ln.strip():
            buf.append(ln.strip())
    if cell and cell not in out:
        out[cell] = " ".join(buf)
    return out


def main() -> int:
    probs = _problems()
    rows: list[tuple[str, list[str], int, int, int]] = []
    for svg_path in sorted(_FIGS.glob("*_proof_*.svg")):
        stem = svg_path.stem
        # g2_l43_proof_Lv2_1 → g2_l43.proof.Lv2
        # **非貪欲の `(.+?)` だと `g2` までしか取れず、突き合わせが全部外れる**
        # （最初にそう書いて「仮定の印が足りない 0 枚」＝合格に見えた）。
        m = re.match(r"((?:exam|g[123])_l\d+)_(\w+?)_(Lv\d+)_\d+$", stem)
        if not m:
            continue
        cell = f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        # **仮定だけを見る。** 「このとき、AB＝CD であることを証明せよ」の AB＝CD は
        # 結論であって仮定ではない。ここを分けずに数えると、印を足す直し方が
        # **答えを図に漏らす**ことになる（幾何的リーク規則）。
        text = re.split(r"このとき|ことを証明|ことを説明", probs.get(cell, ""))[0]
        want: list[str] = []
        if _H_EQ.search(text) or _H_MID.search(text):
            want.append("等長")
        if _H_PARA.search(text):
            want.append("平行")
        if _H_PERP.search(text) or "90°" in text or "垂線" in text:
            want.append("直角")
        svg = svg_path.read_text(encoding="utf-8")
        rows.append((cell, want, len(_TICK.findall(svg)),
                     len(_RIGHT.findall(svg)), len(_PARA.findall(svg))))

    print(f"{'セル':<26}{'本文の仮定':<14}{'等長印':>7}{'直角印':>7}{'平行印':>7}")
    miss = 0
    for cell, want, tick, right, para in rows:
        got = []
        if tick:
            got.append("等長")
        if right:
            got.append("直角")
        if para:
            got.append("平行")
        lack = [w for w in want if w not in got]
        flag = "  ← " + "・".join(lack) + "が図に無い" if lack else ""
        if lack:
            miss += 1
        print(f"{cell:<26}{'・'.join(want) or '-':<14}{tick:>7}{right:>7}{para:>7}{flag}")
    print(f"\n証明の図 {len(rows)} 枚 / 仮定の印が足りない {miss} 枚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
