"""樹形図と、その題材の絵（Phase E 端物・g2_l52 / g2_l53 の graph_table Lv1）。

「起こりうる場合を樹形図に整理せよ」というセルなので、
  - 問題図＝**題材の絵**（投げる硬貨／袋に入っている玉）。樹形図は生徒がかく答えなので描かない
  - 解答図＝**樹形図**（根から1段目・2段目へ枝を伸ばし、枝に選んだものの名を書く）
の2枚を描く。方眼も座標軸も要らないので `graph.py` には載せず、ここに1本起こす。

描画の約束は既存の図資産と同じ（黒の実線だけ・色に情報を載せない・文字は
`VisualPlan.labels` で whitelist する）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


def _svg_open(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, Noto Sans JP, Yu Gothic, Meiryo, sans-serif">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff" stroke="none"/>',
    ]


def _line(x1: float, y1: float, x2: float, y2: float, *, w: float = 1.3) -> str:
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="#000000" stroke-width="{w}"/>'
    )


def _text(x: float, y: float, s: str, *, size: int = 12, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size}" text-anchor="{anchor}" '
        f'fill="#000000">{s}</text>'
    )


def _circle(cx: float, cy: float, r: float) -> str:
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" '
        f'stroke="#000000" stroke-width="1.3"/>'
    )


# ---------------------------------------------------------------------------
# 問題図: 題材の絵（横に並べた円＋その中の名前）
# ---------------------------------------------------------------------------
def render_tree_subject_svg(params: dict[str, Any]) -> str:
    """題材（硬貨／玉）を円で横に並べ、円の中に名前を書く。

    params: subject_labels（円の中に書く文字の並び）／subject_caption（下に書く一文）。
    **樹形図は描かない**（それが答え）。
    """
    labels = [str(v) for v in params["subject_labels"]]
    width, height = 420, 170
    parts = _svg_open(width, height)
    r = 30.0
    gap = 78.0
    total = gap * (len(labels) - 1)
    x0 = width / 2 - total / 2
    for i, label in enumerate(labels):
        cx = x0 + gap * i
        parts.append(_circle(cx, 70.0, r))
        parts.append(_text(cx, 75.0, label, size=13))
    parts.append(_text(width / 2, 140.0, str(params["subject_caption"]), size=12))
    parts.append("</svg>")
    return "".join(parts)


def render_tree_subject(mr: "MR", ctx: "CellContext") -> str:
    return render_tree_subject_svg(mr.params)


# ---------------------------------------------------------------------------
# 解答図: 樹形図（2段）
# ---------------------------------------------------------------------------
def render_tree_diagram_svg(params: dict[str, Any]) -> str:
    """2段の樹形図。`paths`（["表-表", "表-裏", ...]）から枝を組み立てる。

    1段目は最初に選んだもの（重複を除いた並び順は paths の出現順）、2段目はその下に
    続くもの。枝の右端に「できあがった場合」を並べて書く——樹形図を読んだ結果が
    そのまま場合の一覧になる、という見え方にそろえる。
    """
    paths = [str(v).split("-") for v in params["paths"]]
    firsts: list[str] = []
    for first, *_rest in paths:
        if first not in firsts:
            firsts.append(first)
    grouped = {f: [p[1] for p in paths if p[0] == f] for f in firsts}

    row_h = 34.0
    height = int(60 + row_h * len(paths))
    width = 420
    parts = _svg_open(width, height)

    root_x, root_y = 50.0, height / 2
    x1, x2 = 150.0, 260.0
    parts.append(_text(root_x - 8.0, root_y + 4.0, "はじめ", anchor="end"))

    y = 46.0
    for first in firsts:
        seconds = grouped[first]
        ys = [y + row_h * i for i in range(len(seconds))]
        y1 = sum(ys) / len(ys)
        parts.append(_line(root_x, root_y, x1, y1))
        parts.append(_text((root_x + x1) / 2, (root_y + y1) / 2 - 6.0, first))
        for yy, second in zip(ys, seconds, strict=True):
            parts.append(_line(x1, y1, x2, yy))
            parts.append(_text((x1 + x2) / 2, (y1 + yy) / 2 - 6.0, second))
            parts.append(_text(x2 + 10.0, yy + 4.0, f"（{first}、{second}）", anchor="start"))
        y += row_h * len(seconds)

    parts.append("</svg>")
    return "".join(parts)


register_visual("math.tree_subject")(render_tree_subject)


__all__ = [
    "render_tree_diagram_svg",
    "render_tree_subject",
    "render_tree_subject_svg",
]
