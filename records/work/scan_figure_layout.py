"""図の**置かれ方**を測る（縮尺・余白・線の太さ・文字の大きさ）。

## ここまでで測った面と、まだ測っていない面

  済  線の貫通・ラベルの重なり     `scan_figure_legibility.py`（0件）
  済  座標が設問と合っているか      `check_figure_matches_givens.py`
  済  仮定の記号が描かれているか    `scan_figure_marks.py`（0枚）
  未  **図が枠の中でどう置かれているか**  ← ここ

同じ大きさの枠に、小さくかたよって置かれた図と、枠いっぱいに置かれた図が
混ざっていると、並べたときに教材に見えない。

## 数え方（すべて SVG の座標から）

  占有率    図の内容の外接矩形が、枠の面積のどれだけを占めるか
  余白の偏り 左右・上下の余白の差（0 に近いほど中央に置かれている）
  はみ出し   内容が枠の外に出ている量（0 でなければならない）
  線の太さ   `stroke-width` の異なり（増えすぎると図ごとに印象が変わる）
  文字の大きさ `font-size` の異なり

**判断はしない。分布を出して、外れているものを見に行くための道具。**
★図のことは目で見ずに座標で数える（回転した正三角形を「不等辺だ」と読み違えた）。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/scan_figure_layout.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

_FIGS = Path("records/work/corpus/figs")
_ATTR = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)\s*=\s*"([^"]*)"')
_TAG = re.compile(r"<(\w+)([^>]*)>")
_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _content_bbox(svg: str) -> tuple[float, float, float, float] | None:
    """描かれているものの外接矩形。枠（背景の rect）と方眼の薄い線は含めない。"""
    xs: list[float] = []
    ys: list[float] = []
    for m in _TAG.finditer(svg):
        tag, raw = m.group(1), m.group(2)
        a = dict(_ATTR.findall(raw))
        if tag == "svg":
            continue
        if tag == "rect" and a.get("fill", "").lower() in ("#ffffff", "white"):
            continue  # 背景
        # 方眼の線（薄い灰色）は「内容」ではない
        if a.get("stroke", "").lower() in ("#bbbbbb", "#dddddd", "#eeeeee"):
            continue
        if tag == "line":
            # **枠外まで引いた直線は欠陥ではない。** グラフの直線は方眼の端まで
            # 見せるために枠の外まで引き、SVG が切り取る（描画の常道）。
            # 最初これを「はみ出し」と数えて4枚を欠陥として挙げたが、
            # PNG に起こしたらどれも正常だった。枠内に丸めてから数える。
            xs += [min(max(float(a["x1"]), 0.0), 10_000), min(max(float(a["x2"]), 0.0), 10_000)]
            ys += [min(max(float(a["y1"]), 0.0), 10_000), min(max(float(a["y2"]), 0.0), 10_000)]
        elif tag == "circle":
            r = float(a.get("r", 0))
            xs += [float(a["cx"]) - r, float(a["cx"]) + r]
            ys += [float(a["cy"]) - r, float(a["cy"]) + r]
        elif tag in ("polyline", "polygon"):
            v = [float(x) for x in _NUM.findall(a.get("points", ""))]
            xs += v[0::2]
            ys += v[1::2]
        elif tag == "text":
            xs.append(float(a.get("x", 0)))
            ys.append(float(a.get("y", 0)))
        elif tag == "rect":
            x, y = float(a.get("x", 0)), float(a.get("y", 0))
            xs += [x, x + float(a.get("width", 0))]
            ys += [y, y + float(a.get("height", 0))]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def main() -> int:
    widths: Counter[str] = Counter()
    sizes: Counter[str] = Counter()
    rows: list[tuple[float, float, float, str]] = []
    for p in sorted(_FIGS.glob("*.svg")):
        svg = p.read_text(encoding="utf-8")
        head = dict(_ATTR.findall(_TAG.search(svg).group(2)))  # type: ignore[union-attr]
        W, H = float(head.get("width", 0)), float(head.get("height", 0))
        if not W or not H:
            continue
        for m in _TAG.finditer(svg):
            a = dict(_ATTR.findall(m.group(2)))
            if "stroke-width" in a:
                widths[a["stroke-width"]] += 1
            if "font-size" in a:
                sizes[a["font-size"]] += 1
        bb = _content_bbox(svg)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        fill = ((x1 - x0) * (y1 - y0)) / (W * H)
        # 余白の偏り（左右差・上下差を枠の大きさで割る）
        skew = max(abs((x0) - (W - x1)) / W, abs((y0) - (H - y1)) / H)
        over = max(0.0, -x0, -y0, x1 - W, y1 - H)
        rows.append((fill, skew, over, p.stem))

    print(f"図 {len(rows)} 枚\n")
    print("=== 線の太さ ===", dict(widths.most_common()))
    print("=== 文字の大きさ ===", dict(sizes.most_common()))

    over = [r for r in rows if r[2] > 0.5]
    print(f"\n=== 枠からはみ出している（{len(over)} 枚）===")
    for f, s, o, n in sorted(over, key=lambda r: -r[2])[:12]:
        print(f"  {n:<40} はみ出し {o:.1f}px")

    small = sorted(rows)[:12]
    print("\n=== 枠に対して小さい（占有率の低い順・上位12）===")
    for f, s, o, n in small:
        print(f"  {n:<40} 占有率 {f:.0%}  余白の偏り {s:.0%}")

    skewed = sorted(rows, key=lambda r: -r[1])[:12]
    print("\n=== 中央から寄っている（偏りの大きい順・上位12）===")
    for f, s, o, n in skewed:
        print(f"  {n:<40} 偏り {s:.0%}  占有率 {f:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
