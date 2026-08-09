"""数直線（1次元）の SVG レンダラ（実装設計 §6.4・§8.2 G-Q5v）。

`graph.py` の座標平面（2次元グリッド）とは別に、1本の数直線に整数目盛・等分の
補助目盛・点 P を描く自己完結の SVG 文字列生成（matplotlib 非依存）。モノクロ印刷可
（色に情報を載せない。線種・太さのみで区別）。

用途は g1_l2.graph_table Lv1「数直線上の点が表す数を読む」。点 P は単位区間 [a, a+1] を
k 等分した i 番目の目盛にあり、P が表す数は a + i/k（分数）。**この分数（＝答え）は
図に文字として描かない**。図の `<text>` は整数目盛のラベルと点の記号「P」だけで、いずれも
`visual_plan.labels`（whitelist）に入れて G-Q5v（SVG 内テキスト ⊆ whitelist）を満たす。

`@register_visual("math.number_line")` で登録。シグネチャ `(mr, ctx) -> str`。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sympy

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


# ---------------------------------------------------------------------------
# 描画パラメータ（固定・決定論）
# ---------------------------------------------------------------------------
_WIDTH = 480  # px
_HEIGHT = 120  # px
_MARGIN_X = 40  # px（左右の余白。矢じり・端の目盛ラベルを収める）
_AXIS_Y = 60  # px（数直線本体の y 位置）
_TICK_HALF = 9  # px（整数目盛の縦棒・軸から上下）
_MINOR_HALF = 5  # px（等分の補助目盛・整数目盛より短い）
_LABEL_DY = 26  # px（整数ラベルを軸の下に置く量）
_P_DY = 18  # px（点 P の記号を軸の上に置く量）
_ARROW = 6  # px（両端の矢じり）

# 窓（表示する整数目盛の範囲）は P の属する単位区間 [a, a+1] の両隣を含む 4 目盛。
_WINDOW_LEFT_PAD = 1  # a-1 から
_WINDOW_RIGHT_PAD = 2  # a+2 まで


def window_bounds(a: int) -> tuple[int, int]:
    """点 P が属する単位区間の左端 a から、表示する整数目盛の範囲 (lo, hi) を決める。

    render_number_line（実描画）と recipe 側（visual_plan.labels 構築）が同じ窓を
    共有するための公開ヘルパー（labels と実描画の目盛を機械的に一致させる）。
    """
    return a - _WINDOW_LEFT_PAD, a + _WINDOW_RIGHT_PAD


def integer_tick_values(a: int) -> list[int]:
    """窓に描く整数目盛の値一覧（左から右）。"""
    lo, hi = window_bounds(a)
    return list(range(lo, hi + 1))


def number_line_labels(a: int) -> list[str]:
    """図に描いてよい文字列（whitelist）＝整数目盛ラベル ＋ 点の記号「P」。

    答え（a + i/k という分数）は含めない（漏洩防止）。recipe はこの一覧をそのまま
    `visual_plan.labels` に入れる（実描画の `<text>` と機械的に一致する）。
    """
    return [str(v) for v in integer_tick_values(a)] + ["P"]


def _params_ints(params: dict[str, Any]) -> tuple[int, int, int]:
    """params（recipe が MR.params に残す a/k/i）を整数で取り出す。"""
    return int(params["a"]), int(params["k"]), int(params["i"])


def render_number_line(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。params の a/k/i から数直線＋補助目盛＋点 P を描く。

    `<text>` は整数目盛ラベルと「P」のみ（＝ number_line_labels(a) と一致）。
    点 P の値（分数）は描かない。
    """
    a, k, i = _params_ints(mr.params)
    lo, hi = window_bounds(a)
    span = hi - lo  # >= 3

    plot_lo = float(_MARGIN_X)
    plot_hi = float(_WIDTH - _MARGIN_X)

    def to_px(v: float) -> float:
        return plot_lo + (v - lo) * (plot_hi - plot_lo) / span

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_WIDTH} {_HEIGHT}" '
        f'width="{_WIDTH}" height="{_HEIGHT}" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, Noto Sans JP, Yu Gothic, Meiryo, sans-serif">'
    )
    parts.append(
        f'<rect x="0" y="0" width="{_WIDTH}" height="{_HEIGHT}" fill="#ffffff" stroke="none"/>'
    )

    # --- 数直線本体（水平の黒い実線・両端に矢じり） ---
    line_x1 = plot_lo - 2 * _ARROW
    line_x2 = plot_hi + 2 * _ARROW
    parts.append(
        f'<line x1="{line_x1:.2f}" y1="{_AXIS_Y:.2f}" x2="{line_x2:.2f}" y2="{_AXIS_Y:.2f}" '
        f'stroke="#000000" stroke-width="1.5"/>'
    )
    # 右向き矢じり
    parts.append(
        f'<polyline points="{line_x2 - _ARROW:.2f},{_AXIS_Y - _ARROW:.2f} '
        f'{line_x2:.2f},{_AXIS_Y:.2f} {line_x2 - _ARROW:.2f},{_AXIS_Y + _ARROW:.2f}" '
        f'fill="none" stroke="#000000" stroke-width="1.5"/>'
    )
    # 左向き矢じり
    parts.append(
        f'<polyline points="{line_x1 + _ARROW:.2f},{_AXIS_Y - _ARROW:.2f} '
        f'{line_x1:.2f},{_AXIS_Y:.2f} {line_x1 + _ARROW:.2f},{_AXIS_Y + _ARROW:.2f}" '
        f'fill="none" stroke="#000000" stroke-width="1.5"/>'
    )

    # --- 等分の補助目盛（各単位区間を k 等分・整数目盛より短い細線・ラベルなし） ---
    for g in range(lo, hi):
        for j in range(1, k):
            v = g + j / k
            px = to_px(v)
            parts.append(
                f'<line x1="{px:.2f}" y1="{_AXIS_Y - _MINOR_HALF:.2f}" '
                f'x2="{px:.2f}" y2="{_AXIS_Y + _MINOR_HALF:.2f}" '
                f'stroke="#000000" stroke-width="0.75"/>'
            )

    # --- 整数目盛（縦棒＋数値ラベル） ---
    for gx in range(lo, hi + 1):
        px = to_px(gx)
        parts.append(
            f'<line x1="{px:.2f}" y1="{_AXIS_Y - _TICK_HALF:.2f}" '
            f'x2="{px:.2f}" y2="{_AXIS_Y + _TICK_HALF:.2f}" '
            f'stroke="#000000" stroke-width="1.5"/>'
        )
        parts.append(
            f'<text x="{px:.2f}" y="{_AXIS_Y + _LABEL_DY:.2f}" font-size="13" '
            f'text-anchor="middle" fill="#000000">{sympy.Integer(gx)}</text>'
        )

    # --- 点 P（軸上の塗り● ＋ 記号「P」を上に置く。値は描かない＝漏洩防止） ---
    p_val = a + i / k
    p_px = to_px(p_val)
    parts.append(
        f'<circle cx="{p_px:.2f}" cy="{_AXIS_Y:.2f}" r="4" fill="#000000"/>'
    )
    parts.append(
        f'<text x="{p_px:.2f}" y="{_AXIS_Y - _P_DY:.2f}" font-size="14" '
        f'text-anchor="middle" fill="#000000">P</text>'
    )

    parts.append("</svg>")
    return "".join(parts)


register_visual("math.number_line")(render_number_line)


__all__ = [
    "render_number_line",
    "window_bounds",
    "integer_tick_values",
    "number_line_labels",
]
