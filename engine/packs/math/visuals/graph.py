"""一次関数グラフの SVG レンダラ（実装設計 §6.4・§8.2 G-Q5v）。

matplotlib に依存しない自己完結の SVG 文字列生成。座標平面（グリッド線・x軸/y軸・
軸目盛の数値ラベル・直線1本）を描く。モノクロ印刷可（色に情報を載せない。線種・
太さのみで区別する）。

`<text>` 要素は軸目盛の数値のみ。呼び出し側（recipe）はこれらの目盛文字列を
`visual_plan.labels` に含めることで G-Q5v（SVG 内テキスト ⊆ whitelist）を満たす。

`@register_visual("math.linear_graph")` で登録。シグネチャ `(mr, ctx) -> str`。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import sympy

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


# ---------------------------------------------------------------------------
# 描画パラメータ（固定・決定論）
# ---------------------------------------------------------------------------
_SVG_SIZE = 400  # px（正方形。縦横で縮尺を揃え、傾きを歪めない）
_MARGIN = 28  # px（目盛ラベル用の余白）
_MIN_HALF_RANGE = 5  # グリッドの最小半幅（点が原点近くでも読みやすい範囲を確保）
_EXTRA_MARGIN = 2  # 点の外側に確保する整数目盛の余白


def _parse_point(s: str) -> tuple[sympy.Expr, sympy.Expr]:
    t = sympy.sympify(s)
    return sympy.nsimplify(t[0]), sympy.nsimplify(t[1])


def _format_tick(v: sympy.Expr) -> str:
    """軸目盛の表示形（整数はそのまま）。"""
    return str(sympy.sstr(v))


def _compute_range(values: list[sympy.Expr]) -> tuple[int, int]:
    """整数目盛グリッドの範囲 [-lo, hi] を、values が収まるよう決める。"""
    nums = [int(v) for v in values]
    lo = min(nums + [-_MIN_HALF_RANGE])
    hi = max(nums + [_MIN_HALF_RANGE])
    lo -= _EXTRA_MARGIN
    hi += _EXTRA_MARGIN
    return lo, hi


def _linear_scale(
    domain_lo: int, domain_hi: int, range_lo: float, range_hi: float
) -> Callable[[float], float]:
    span = domain_hi - domain_lo
    if span == 0:
        span = 1

    def scale(v: float) -> float:
        return range_lo + (v - domain_lo) * (range_hi - range_lo) / span

    return scale


def compute_grid_bounds_from_params(params: dict[str, Any]) -> tuple[int, int, int, int]:
    """params（recipe が MR.params に残す a/b/pts）の pts が収まるグリッド範囲

    (x_lo, x_hi, y_lo, y_hi) を決める。render_linear_graph と recipe 側
    （visual_plan.labels 構築）が同じロジックを共有するための公開ヘルパー
    （labels と実描画の目盛を機械的に一致させる）。縦横の目盛間隔を揃える
    （傾きを視覚的に歪めない）ため、共通の半幅を採用する。
    """
    pts_raw = params["pts"]
    pts = [_parse_point(s) for s in pts_raw]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x_lo, x_hi = _compute_range(xs)
    y_lo, y_hi = _compute_range(ys)
    half = max(x_hi - x_lo, y_hi - y_lo)
    x_mid = (x_lo + x_hi) / 2
    y_mid = (y_lo + y_hi) / 2
    x_lo = int(x_mid - half / 2)
    x_hi = int(x_mid + half / 2)
    y_lo = int(y_mid - half / 2)
    y_hi = int(y_mid + half / 2)
    return x_lo, x_hi, y_lo, y_hi


def compute_grid_bounds(mr: "MR") -> tuple[int, int, int, int]:
    """`compute_grid_bounds_from_params(mr.params)` のショートカット。"""
    return compute_grid_bounds_from_params(mr.params)


def tick_labels_from_params(params: dict[str, Any]) -> list[str]:
    """実描画される軸目盛の数値ラベル一覧（0 を除く。visual_plan.labels 用）。

    recipe が MR を組み立てる前（params だけがある時点）から呼べるよう、
    dict を直接受け取る形にしてある（`tick_labels` はその MR 版ショートカット）。
    """
    x_lo, x_hi, y_lo, y_hi = compute_grid_bounds_from_params(params)
    labels: list[str] = []
    for gx in range(x_lo, x_hi + 1):
        if gx == 0:
            continue
        labels.append(_format_tick(sympy.Integer(gx)))
    for gy in range(y_lo, y_hi + 1):
        labels.append(_format_tick(sympy.Integer(gy)))
    return labels


def tick_labels(mr: "MR") -> list[str]:
    """`tick_labels_from_params(mr.params)` のショートカット。"""
    return tick_labels_from_params(mr.params)


def render_linear_graph(mr: "MR", ctx: "CellContext") -> str:
    """MR.params の a, b, pts と描画範囲から SVG を組む（決定論・自己完結）。"""
    a = sympy.nsimplify(sympy.sympify(mr.params["a"]))
    b = sympy.nsimplify(sympy.sympify(mr.params["b"]))

    x_lo, x_hi, y_lo, y_hi = compute_grid_bounds_from_params(mr.params)

    plot_lo = _MARGIN
    plot_hi = _SVG_SIZE - _MARGIN
    to_px_x = _linear_scale(x_lo, x_hi, plot_lo, plot_hi)
    to_px_y = _linear_scale(y_lo, y_hi, plot_hi, plot_lo)  # y は上下反転

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_SIZE} {_SVG_SIZE}" '
        f'width="{_SVG_SIZE}" height="{_SVG_SIZE}">'
    )
    parts.append(f'<rect x="0" y="0" width="{_SVG_SIZE}" height="{_SVG_SIZE}" fill="none" stroke="none"/>')

    # --- グリッド線（細い灰の実線。モノクロ印刷可＝色に情報を載せない） ---
    for gx in range(x_lo, x_hi + 1):
        px = to_px_x(gx)
        parts.append(
            f'<line x1="{px:.2f}" y1="{plot_lo:.2f}" x2="{px:.2f}" y2="{plot_hi:.2f}" '
            f'stroke="#bbbbbb" stroke-width="0.5"/>'
        )
    for gy in range(y_lo, y_hi + 1):
        py = to_px_y(gy)
        parts.append(
            f'<line x1="{plot_lo:.2f}" y1="{py:.2f}" x2="{plot_hi:.2f}" y2="{py:.2f}" '
            f'stroke="#bbbbbb" stroke-width="0.5"/>'
        )

    # --- 軸（実線・グリッドより太い黒） ---
    if y_lo <= 0 <= y_hi:
        py0 = to_px_y(0)
        parts.append(
            f'<line x1="{plot_lo:.2f}" y1="{py0:.2f}" x2="{plot_hi:.2f}" y2="{py0:.2f}" '
            f'stroke="#000000" stroke-width="1.5"/>'
        )
    if x_lo <= 0 <= x_hi:
        px0 = to_px_x(0)
        parts.append(
            f'<line x1="{px0:.2f}" y1="{plot_lo:.2f}" x2="{px0:.2f}" y2="{plot_hi:.2f}" '
            f'stroke="#000000" stroke-width="1.5"/>'
        )

    # --- 直線（太い黒の実線。線種・太さのみで区別＝モノクロ印刷可） ---
    x_start, x_end = x_lo, x_hi
    y_start = a * x_start + b
    y_end = a * x_end + b
    px1, py1 = to_px_x(x_start), to_px_y(float(y_start))
    px2, py2 = to_px_x(x_end), to_px_y(float(y_end))
    parts.append(
        f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
        f'stroke="#000000" stroke-width="2.5"/>'
    )

    # --- 軸目盛の数値ラベル（<text> はこれのみ。visual_plan.labels と一致させる） ---
    py0 = to_px_y(0) if y_lo <= 0 <= y_hi else plot_hi
    for gx in range(x_lo, x_hi + 1):
        if gx == 0:
            continue  # 原点の重複表記を避ける（0 は y 軸側で1回だけ出す）
        px = to_px_x(gx)
        parts.append(
            f'<text x="{px:.2f}" y="{py0 + 12:.2f}" font-size="10" '
            f'text-anchor="middle" fill="#000000">{_format_tick(sympy.Integer(gx))}</text>'
        )
    px0 = to_px_x(0) if x_lo <= 0 <= x_hi else plot_lo
    for gy in range(y_lo, y_hi + 1):
        py = to_px_y(gy)
        parts.append(
            f'<text x="{px0 - 8:.2f}" y="{py + 3:.2f}" font-size="10" '
            f'text-anchor="end" fill="#000000">{_format_tick(sympy.Integer(gy))}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


register_visual("math.linear_graph")(render_linear_graph)


__all__ = [
    "render_linear_graph",
    "compute_grid_bounds",
    "compute_grid_bounds_from_params",
    "tick_labels",
    "tick_labels_from_params",
]
