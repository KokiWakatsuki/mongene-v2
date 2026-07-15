"""平面図形の移動（平行移動・回転移動・対称移動）の SVG レンダラ

（実装設計 §6.4・§8.2 G-Q5v）。

`engine/packs/math/visuals/graph.py`（座標平面グラフ）と同じ設計方針（matplotlib
非依存の自己完結 SVG 文字列生成・決定論・モノクロ印刷可）を踏襲し、グリッド座標
変換ヘルパ（`_grid_scaffold`/`compute_grid_bounds_from_params`/`tick_labels_from_params`）
を再利用する。多角形の頂点＋辺の描画を追加する点のみが新規。

2つの描画スタイルを持つ:
  - "grid_only"（Lv1・方眼のみ）: 座標軸・目盛の数値ラベルを一切描かない（グリッド線
    のみ）。対称移動の軸(ℓ)は「どのマス目の線か」を太線で示すが、座標としての数値
    ラベルは付けない＝ G-Q5v の whitelist は多角形の頂点ラベル(A,B,C 等)のみで足りる。
  - "coordinate"（Lv2・座標平面）: `graph.py` と同じグリッド＋軸＋目盛数値を描く。

問題図（`register_visual` 登録）は移動前の多角形のみを描く（移動後の多角形＝答えは
描かない）。模範解答図（`GraphAnswer.solution_svg_ref`）は移動前(実線)＋移動後(破線)
の両方を描く（`render_*_solution_svg` として recipe から直接呼ぶ・graph.py の
`render_segment_solution_svg` と同型）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import sympy

from engine.core.registry import register_visual
from engine.packs.math.visuals.graph import (
    _MARGIN,
    _SVG_SIZE,
    _GridScaffold,
    _grid_scaffold,
    _grid_ticks,
    _linear_scale,
    _parse_point,
    compute_grid_bounds_from_params,
)

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


def _labeled_points_from_params(
    params: dict[str, Any], *, pts_key: str, labels_key: str
) -> list[tuple[str, sympy.Expr, sympy.Expr]]:
    """params[pts_key]（"(x, y)" 文字列の列）と params[labels_key]（頂点名の列）から

    (label, x, y) の列を組む。両者は同じ長さでなければならない。
    """
    pts_raw = params[pts_key]
    labels = params[labels_key]
    out: list[tuple[str, sympy.Expr, sympy.Expr]] = []
    for label, s in zip(labels, pts_raw):
        x, y = _parse_point(s)
        out.append((label, x, y))
    return out


def _plain_grid_scaffold(params: dict[str, Any]) -> _GridScaffold:
    """方眼のみ(軸・目盛の数値ラベルなし)の座標変換土台を組む（Lv1・grid_only 用）。

    `graph.py._grid_scaffold` は 0 を含む範囲で太線の軸を描いてしまう（Lv1 は
    「座標軸」を見せない方眼なので不適）。ここではグリッド線のみを描く専用の
    土台を組む（座標変換は graph.py と共有し座標系を一致させる）。
    """
    x_lo, x_hi, y_lo, y_hi = compute_grid_bounds_from_params(params)

    plot_lo = _MARGIN
    plot_hi = _SVG_SIZE - _MARGIN
    to_px_x = _linear_scale(x_lo, x_hi, plot_lo, plot_hi)
    to_px_y = _linear_scale(y_lo, y_hi, plot_hi, plot_lo)

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_SIZE} {_SVG_SIZE}" '
        f'width="{_SVG_SIZE}" height="{_SVG_SIZE}">'
    )
    parts.append(
        f'<rect x="0" y="0" width="{_SVG_SIZE}" height="{_SVG_SIZE}" fill="none" stroke="none"/>'
    )
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
    return _GridScaffold(parts, to_px_x, to_px_y, x_lo, x_hi, y_lo, y_hi, plot_lo, plot_hi)


def _polygon_parts(
    sc: _GridScaffold, labeled_pts: list[tuple[str, sympy.Expr, sympy.Expr]], *, dashed: bool = False
) -> list[str]:
    """多角形(頂点＋ラベル＋辺)の SVG 要素を組む（実線=移動前／破線=移動後）。"""
    coords = [(sc.to_px_x(float(x)), sc.to_px_y(float(y))) for _, x, y in labeled_pts]
    path_d = "M " + " L ".join(f"{px:.2f} {py:.2f}" for px, py in coords) + " Z"
    dash_attr = ' stroke-dasharray="5 4"' if dashed else ""
    parts = [f'<path d="{path_d}" fill="none" stroke="#000000" stroke-width="2"{dash_attr}/>']
    for (label, _x, _y), (px, py) in zip(labeled_pts, coords):
        parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="2.5" fill="#000000"/>')
        parts.append(
            f'<text x="{px + 6:.2f}" y="{py - 6:.2f}" font-size="13" fill="#000000">{label}</text>'
        )
    return parts


def _axis_line_parts(sc: _GridScaffold, axis: str) -> list[str]:
    """対称の軸(x軸/y軸に対応する太線)を描く（grid_only スタイルで ℓ を示す用）。"""
    if axis == "x_axis":
        py = sc.to_px_y(0)
        return [
            f'<line x1="{sc.plot_lo:.2f}" y1="{py:.2f}" x2="{sc.plot_hi:.2f}" y2="{py:.2f}" '
            f'stroke="#000000" stroke-width="1.5"/>'
        ]
    px = sc.to_px_x(0)
    return [
        f'<line x1="{px:.2f}" y1="{sc.plot_lo:.2f}" x2="{px:.2f}" y2="{sc.plot_hi:.2f}" '
        f'stroke="#000000" stroke-width="1.5"/>'
    ]


# ---------------------------------------------------------------------------
# 問題図（register_visual 登録・移動前の多角形のみを描く）
# ---------------------------------------------------------------------------
def _extra_point_parts(sc: _GridScaffold, params: dict[str, Any]) -> list[str]:
    """回転の中心など、多角形の頂点以外に単独で描く点(あれば)の SVG 要素。"""
    label = params.get("center_label")
    pt = params.get("center_pt")
    if label is None or pt is None:
        return []
    x, y = _parse_point(str(pt))
    px, py = sc.to_px_x(float(x)), sc.to_px_y(float(y))
    return [
        f'<circle cx="{px:.2f}" cy="{py:.2f}" r="2.5" fill="#000000"/>',
        f'<text x="{px + 6:.2f}" y="{py - 6:.2f}" font-size="13" fill="#000000">{label}</text>',
    ]


def render_polygon_grid_only(mr: "MR", ctx: "CellContext") -> str:
    """問題図（Lv1・grid_only）。方眼＋移動前の多角形のみ（座標の数値は描かない）。"""
    sc = _plain_grid_scaffold(mr.params)
    parts = list(sc.parts)
    if mr.params.get("reflect_axis") is not None:
        parts.extend(_axis_line_parts(sc, str(mr.params["reflect_axis"])))
    parts.extend(_polygon_parts(sc, _labeled_points_from_params(mr.params, pts_key="pts", labels_key="vertex_labels")))
    parts.extend(_extra_point_parts(sc, mr.params))
    parts.append("</svg>")
    return "".join(parts)


def render_polygon_coordinate(mr: "MR", ctx: "CellContext") -> str:
    """問題図（Lv2・coordinate）。座標平面(軸＋目盛)＋移動前の多角形のみ。"""
    sc = _grid_scaffold(mr.params)
    parts = list(sc.parts)
    parts.extend(_polygon_parts(sc, _labeled_points_from_params(mr.params, pts_key="pts", labels_key="vertex_labels")))
    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# 模範解答図（GraphAnswer.solution_svg_ref・recipe から直接呼ぶ）
# ---------------------------------------------------------------------------
def render_polygon_transform_solution_svg(params: dict[str, Any], *, style: str) -> str:
    """移動前(実線)＋移動後(破線)の両方を描く模範解答図。

    問題図の座標変換ロジックは共有するが、描画範囲は移動前+移動後の全頂点が収まる
    よう別途計算する（問題図は移動前の頂点だけで範囲を決めるため、そのまま使うと
    移動後の多角形がキャンバス外にはみ出しうる）。
    """
    extra_pts = [params["center_pt"]] if params.get("center_pt") is not None else []
    bounds_params = {**params, "pts": [*params["pts"], *params["new_pts"], *extra_pts]}
    sc = _plain_grid_scaffold(bounds_params) if style == "grid_only" else _grid_scaffold(bounds_params)
    parts = list(sc.parts)
    if style == "grid_only" and params.get("reflect_axis") is not None:
        parts.extend(_axis_line_parts(sc, str(params["reflect_axis"])))
    parts.extend(_polygon_parts(sc, _labeled_points_from_params(params, pts_key="pts", labels_key="vertex_labels")))
    parts.extend(
        _polygon_parts(
            sc,
            _labeled_points_from_params(params, pts_key="new_pts", labels_key="vertex_labels_prime"),
            dashed=True,
        )
    )
    parts.extend(_extra_point_parts(sc, params))
    if style != "grid_only":
        parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


register_visual("math.polygon_grid_only")(render_polygon_grid_only)
register_visual("math.polygon_coordinate")(render_polygon_coordinate)


__all__ = [
    "render_polygon_grid_only",
    "render_polygon_coordinate",
    "render_polygon_transform_solution_svg",
]
