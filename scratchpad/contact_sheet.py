"""図をまとめて1枚に並べ、目視しやすくする。

ゲートは図の内容の誤りを検出しない（点の並び違い・線が枠外・ラベル消失）。
282枚を1枚ずつ開くのは現実的でないので、格子に並べて眺め、
おかしいものだけ個別に拡大する。

実行: PYTHONPATH=. .venv/bin/python scratchpad/contact_sheet.py <出力名> <図のファイル名...>
      PYTHONPATH=. .venv/bin/python scratchpad/contact_sheet.py --list
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

_FIGS = Path("scratchpad/corpus/figs")
_OUT = Path("scratchpad/sheets")
_COLS = 4
_CELL = (300, 240)
_LABEL_H = 18


def main() -> None:
    if sys.argv[1] == "--list":
        names = sorted(p.stem for p in _FIGS.glob("*.png"))
        for n in names:
            print(n)
        print(f"--- {len(names)} 枚")
        return

    _OUT.mkdir(parents=True, exist_ok=True)
    out_name = sys.argv[1]
    stems = sys.argv[2:]
    rows = (len(stems) + _COLS - 1) // _COLS
    W = _COLS * _CELL[0]
    H = rows * (_CELL[1] + _LABEL_H)
    sheet = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(sheet)
    for i, stem in enumerate(stems):
        path = _FIGS / f"{stem}.png"
        if not path.exists():
            continue
        # SVG に背景が無いので PNG は透過。**白地に合成する**
        # （`convert("RGB")` だけだと透過が黒く潰れて図が全部真っ黒になる）。
        src = Image.open(path).convert("RGBA")
        img = Image.new("RGB", src.size, "white")
        img.paste(src, mask=src.split()[3])
        img.thumbnail((_CELL[0] - 8, _CELL[1] - 8))
        cx = (i % _COLS) * _CELL[0]
        cy = (i // _COLS) * (_CELL[1] + _LABEL_H)
        sheet.paste(img, (cx + 4, cy + _LABEL_H + 2))
        draw.text((cx + 4, cy + 3), stem.replace("_", " ")[:44], fill="black")
        draw.rectangle(
            [cx, cy, cx + _CELL[0] - 1, cy + _CELL[1] + _LABEL_H - 1],
            outline="#cccccc",
        )
    path = _OUT / f"{out_name}.png"
    sheet.save(path)
    print(f"{len(stems)} 枚 → {path}")


if __name__ == "__main__":
    main()
