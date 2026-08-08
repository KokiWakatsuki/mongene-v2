"""立体（空間図形）の SVG レンダラ（実装設計 §6.4・§8.2 G-Q5v）。

`graph.py`（座標平面）・`distribution_chart.py`（分布）と同じ設計方針を踏襲する:
matplotlib 非依存の自己完結 SVG 文字列生成・決定論・モノクロ印刷可。
座標平面ではないので `graph.py` のグリッド土台は使わず、立体ごとの寸法から
直接 SVG 座標を組む。

## 5つのビュー（`params["view"]`）

  - `sketch`         見取図。斜投影（奥行きを右上 45°・0.5 倍）で描き、見えない稜線を
                     破線にする。角柱・角錐・円柱・円錐・球。
  - `projection`     投影図。立面図（上）と平面図（下）を上下に並べ、対応を破線で結ぶ
                     （教科書の並べ方）。
  - `net`            展開図。角柱＝側面の帯＋底面2枚、円柱＝長方形＋円2枚、
                     円錐＝おうぎ形＋円。
  - `section`        断面。頂点名つきの多角形1枚。
  - `rotation_source` 回転体の元図。回転させる平面図形と回転の軸（一点鎖線）。

いずれも「かく」セルの問題図は**答えを先出ししない**。`draw=False` を渡すと
外枠だけ（あるいは元図だけ）を描く——`graph.py` の「空の方眼」と同じ規約。

## 寸法ラベルと G-Q5v

図中に書く文字（頂点名・辺の長さ）は `solid_labels(params)` が params から機械的に
作る。手で書かない（G-Q5v は SVG の <text> がこの集合に収まることを検査する）。
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext

_W = 460  # px（横。投影図・展開図は横に広がるので graph.py より広くとる）
_H = 400  # px
_PAD = 30  # px（ラベル用の余白）

# 斜投影の奥行き方向（右上 45°・長さは 0.5 倍＝カバリエ図法の慣習）
_DEPTH_COS = 0.5 * math.cos(math.radians(45))
_DEPTH_SIN = 0.5 * math.sin(math.radians(45))

_STROKE = "#000000"
_THIN = 1.2
_DASH = 'stroke-dasharray="5 4"'
_CHAIN = 'stroke-dasharray="12 3 3 3"'  # 一点鎖線（回転の軸）


# ---------------------------------------------------------------------------
# SVG の素片
# ---------------------------------------------------------------------------
def _svg(parts: list[str], width: int = _W, height: int = _H) -> str:
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="none" stroke="none"/>'
    )
    return head + "".join(parts) + "</svg>"


def _line(x1: float, y1: float, x2: float, y2: float, *, dashed: bool = False) -> str:
    extra = f" {_DASH}" if dashed else ""
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{_STROKE}" stroke-width="{_THIN}"{extra}/>'
    )


def _chain_line(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
        f'stroke="{_STROKE}" stroke-width="{_THIN}" {_CHAIN}/>'
    )


def _polygon(pts: list[tuple[float, float]], *, dashed: bool = False) -> str:
    joined = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    extra = f" {_DASH}" if dashed else ""
    return (
        f'<polygon points="{joined}" fill="none" stroke="{_STROKE}" '
        f'stroke-width="{_THIN}"{extra}/>'
    )


def _ellipse(cx: float, cy: float, rx: float, ry: float, *, dashed: bool = False) -> str:
    extra = f" {_DASH}" if dashed else ""
    return (
        f'<ellipse cx="{cx:.2f}" cy="{cy:.2f}" rx="{rx:.2f}" ry="{ry:.2f}" '
        f'fill="none" stroke="{_STROKE}" stroke-width="{_THIN}"{extra}/>'
    )


def _arc_half(cx: float, cy: float, rx: float, ry: float, *, lower: bool) -> str:
    """楕円の下半分（見えている側）／上半分（隠れている側）だけを描く。"""
    sweep = 1 if lower else 0
    return (
        f'<path d="M {cx - rx:.2f} {cy:.2f} A {rx:.2f} {ry:.2f} 0 0 {sweep} '
        f'{cx + rx:.2f} {cy:.2f}" fill="none" stroke="{_STROKE}" '
        f'stroke-width="{_THIN}"{"" if lower else " " + _DASH}/>'
    )


def _circle(cx: float, cy: float, r: float) -> str:
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" fill="none" '
        f'stroke="{_STROKE}" stroke-width="{_THIN}"/>'
    )


def _text(x: float, y: float, s: str, *, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" font-size="12" text-anchor="{anchor}" '
        f'fill="{_STROKE}">{s}</text>'
    )


def _depth(d: float) -> tuple[float, float]:
    """奥行き d を斜投影したときの (右へのずれ, 上へのずれ)。"""
    return d * _DEPTH_COS, d * _DEPTH_SIN


# ---------------------------------------------------------------------------
# 図中の文字（G-Q5v の whitelist）
# ---------------------------------------------------------------------------
def solid_labels(params: dict[str, Any]) -> list[str]:
    """図に出す文字を params から機械的に作る（手で書かない・G-Q5v）。

    頂点名（`vertices`）と、寸法として書き入れる長さ（`dim_labels`）だけ。
    答えそのもの（求める体積・表面積・最短距離）はここに入れない。
    """
    out: list[str] = []
    for v in params.get("vertices") or []:
        out.append(str(v))
    for d in params.get("dim_labels") or []:
        out.append(str(d))
    # 投影図は「立面図」「平面図」の見出しを図に書く（教科書の並べ方）。見出しは
    # 寸法でも答えでもないが、svg の <text> に出るので whitelist に載せる必要がある。
    if str(params.get("view")) == "projection":
        shown = str(params.get("shown_view", "none"))
        if shown in ("both", "elevation"):
            out.append("立面図")
        if shown in ("both", "plan"):
            out.append("平面図")
    return out


# ---------------------------------------------------------------------------
# 見取図（sketch）
# ---------------------------------------------------------------------------
def _prism_sketch(params: dict[str, Any]) -> list[str]:
    """角柱の見取図。底面は長方形（正方形を含む）。

    奥の稜線3本（奥の底面の2辺＋奥の縦棱）を破線にする＝教科書の見取図の規約。
    """
    w = float(params["width_px"])
    h = float(params["height_px"])
    d = float(params["depth_px"])
    dx, dy = _depth(d)
    x0 = _PAD + 40
    y0 = _H - _PAD - 60  # 手前下の頂点

    # 手前の面（長方形）
    fa = (x0, y0)
    fb = (x0 + w, y0)
    fc = (x0 + w, y0 - h)
    fd = (x0, y0 - h)
    # 奥の面
    ba = (x0 + dx, y0 - dy)
    bb = (x0 + w + dx, y0 - dy)
    bc = (x0 + w + dx, y0 - h - dy)
    bd = (x0 + dx, y0 - h - dy)

    parts = [
        _polygon([fa, fb, fc, fd]),
        # 見えている奥の稜線
        _line(*fb, *bb), _line(*fc, *bc), _line(*fd, *bd),
        _line(*bb, *bc), _line(*bc, *bd),
        # 見えない稜線（奥の左下の頂点まわり）
        _line(*fa, *ba, dashed=True),
        _line(*ba, *bb, dashed=True),
        _line(*ba, *bd, dashed=True),
    ]
    pts = {"A": fa, "B": fb, "C": bb, "D": ba, "E": fd, "F": fc, "G": bc, "H": bd}
    return parts + _vertex_labels(params, pts)


def _dimension_labels(
    params: dict[str, Any], *, radius_at: tuple[float, float], height_at: tuple[float, float]
) -> list[str]:
    """底面の半径・高さを図に書き入れる（`dim_labels` = [半径, 高さ] の順）。

    「見取図をかき、底面の半径と高さを図中に書き入れよ」という設問に、模範解答図が
    答えきるために要る（features に値があっても、図に無ければ設問に答えていない）。
    """
    labels = list(params.get("dim_labels") or [])
    out: list[str] = []
    if len(labels) >= 1:
        out.append(_text(radius_at[0], radius_at[1], str(labels[0])))
    if len(labels) >= 2:
        out.append(_text(height_at[0], height_at[1], str(labels[1]), anchor="end"))
    return out


def _cylinder_sketch(params: dict[str, Any]) -> list[str]:
    """円柱の見取図。上面は楕円まるごと、下面は手前半分だけ実線・奥半分を破線。"""
    r = float(params["radius_px"])
    h = float(params["height_px"])
    ry = r * 0.32  # 楕円のつぶれ具合（見た目の慣習）
    cx = _W / 2
    cy_bottom = _H - _PAD - 50
    cy_top = cy_bottom - h
    return [
        _ellipse(cx, cy_top, r, ry),
        _line(cx - r, cy_top, cx - r, cy_bottom),
        _line(cx + r, cy_top, cx + r, cy_bottom),
        _arc_half(cx, cy_bottom, r, ry, lower=True),
        _arc_half(cx, cy_bottom, r, ry, lower=False),
        # 底面の半径を示す線分（中心から右へ）と高さを示す線分（左の母線に沿って）
        _line(cx, cy_bottom, cx + r, cy_bottom, dashed=True),
    ] + _dimension_labels(
        params,
        radius_at=(cx + r / 2, cy_bottom - 6),
        height_at=(cx - r - 6, (cy_top + cy_bottom) / 2),
    )


def _cone_sketch(params: dict[str, Any]) -> list[str]:
    """円錐の見取図。底面は手前半分だけ実線・奥半分を破線。"""
    r = float(params["radius_px"])
    h = float(params["height_px"])
    ry = r * 0.32
    cx = _W / 2
    cy_bottom = _H - _PAD - 50
    apex_y = cy_bottom - h
    return [
        _line(cx - r, cy_bottom, cx, apex_y),
        _line(cx + r, cy_bottom, cx, apex_y),
        _arc_half(cx, cy_bottom, r, ry, lower=True),
        _arc_half(cx, cy_bottom, r, ry, lower=False),
        # 底面の半径（中心から右へ）と高さ（頂点から底面の中心へ）を示す補助線
        _line(cx, cy_bottom, cx + r, cy_bottom, dashed=True),
        _line(cx, apex_y, cx, cy_bottom, dashed=True),
    ] + _dimension_labels(
        params,
        radius_at=(cx + r / 2, cy_bottom - 6),
        height_at=(cx - 6, (apex_y + cy_bottom) / 2),
    )


def _sphere_sketch(params: dict[str, Any]) -> list[str]:
    """球の見取図。円＋赤道の楕円（手前半分が実線・奥半分が破線）。"""
    r = float(params["radius_px"])
    cx, cy = _W / 2, _H / 2
    return [
        _circle(cx, cy, r),
        _arc_half(cx, cy, r, r * 0.32, lower=True),
        _arc_half(cx, cy, r, r * 0.32, lower=False),
    ]


def _pyramid_sketch(params: dict[str, Any]) -> list[str]:
    """正四角錐の見取図。底面の奥の2辺を破線にする。"""
    w = float(params["width_px"])
    h = float(params["height_px"])
    d = float(params["depth_px"])
    dx, dy = _depth(d)
    x0 = _PAD + 60
    y0 = _H - _PAD - 60
    fa = (x0, y0)
    fb = (x0 + w, y0)
    bb = (x0 + w + dx, y0 - dy)
    ba = (x0 + dx, y0 - dy)
    apex = (x0 + w / 2 + dx / 2, y0 - dy / 2 - h)
    parts = [
        _line(*fa, *fb),
        _line(*fb, *bb),
        _line(*bb, *ba, dashed=True),
        _line(*ba, *fa, dashed=True),
        _line(*fa, *apex), _line(*fb, *apex), _line(*bb, *apex),
        _line(*ba, *apex, dashed=True),
    ]
    pts = {"A": fa, "B": fb, "C": bb, "D": ba, "E": apex}
    return parts + _vertex_labels(params, pts)


def _vertex_labels(params: dict[str, Any], pts: dict[str, str]) -> list[str]:
    """`params["vertices"]` の並びを、立体の決まった位置に順に置く。

    vertices は「手前左下から時計まわり → 上面も同じ順」で与える規約
    （直方体なら ABCD-EFGH）。位置は立体ごとに固定なので、名前だけを差し替える。
    """
    names = list(params.get("vertices") or [])
    if not names:
        return []
    slots = list(pts.values())
    out: list[str] = []
    for name, (x, y) in zip(names, slots, strict=False):
        out.append(_text(float(x), float(y) - 6, str(name)))
    return out


_SKETCH_BY_KIND = {
    "rectangular_prism": _prism_sketch,
    "square_prism": _prism_sketch,
    "cube": _prism_sketch,
    "cylinder": _cylinder_sketch,
    "cone": _cone_sketch,
    "sphere": _sphere_sketch,
    "square_pyramid": _pyramid_sketch,
}


# ---------------------------------------------------------------------------
# 投影図（projection）: 立面図（上）と平面図（下）
# ---------------------------------------------------------------------------
# solid_kind -> (立面図の形, 平面図の形)。**対応表の出典は solver 側**
# （`solvers/solid_view.projection_shapes`）で、ここでは描画のためにそれを引くだけ。
# 表を2か所に持つと、片方だけ直したときに図と答えが食い違う（実際に一度ずれた）。
# 直方体だけは投影図のセルに出さない（立面図・平面図がともに長方形で、
# 見取図のセルでしか使わない）ので、描画専用の追加として持つ。
_PROJECTION_DRAW_ONLY: dict[str, tuple[str, str]] = {
    "rectangular_prism": ("rect", "rect"),
}


def _projection_shapes(kind: str) -> tuple[str, str]:
    from engine.packs.math.solvers.solid_view import projection_shapes

    if kind in _PROJECTION_DRAW_ONLY:
        return _PROJECTION_DRAW_ONLY[kind]
    return projection_shapes(kind)


def _shape_parts(shape: str, cx: float, cy: float, w: float, h: float) -> list[str]:
    if shape == "circle":
        return [_circle(cx, cy, min(w, h) / 2)]
    if shape == "triangle":
        return [_polygon([(cx - w / 2, cy + h / 2), (cx + w / 2, cy + h / 2), (cx, cy - h / 2)])]
    if shape == "square_with_diagonals":
        s = min(w, h)
        a = (cx - s / 2, cy - s / 2)
        b = (cx + s / 2, cy - s / 2)
        c = (cx + s / 2, cy + s / 2)
        d = (cx - s / 2, cy + s / 2)
        return [_polygon([a, b, c, d]), _line(*a, *c), _line(*b, *d)]
    s = min(w, h) if shape == "square" else w
    return [_polygon([
        (cx - s / 2, cy - h / 2), (cx + s / 2, cy - h / 2),
        (cx + s / 2, cy + h / 2), (cx - s / 2, cy + h / 2),
    ])]


def _projection_parts(params: dict[str, Any], *, draw: bool) -> list[str]:
    """立面図（上）と平面図（下）を上下に並べる。

    `draw=False`（「かく」セルの問題図）は、示されている側の図だけを描く
    （`params["shown_view"]` ∈ {"elevation", "plan", "none"}）。
    """
    kind = str(params["solid_kind"])
    elev, plan = _projection_shapes(kind)
    w = float(params["width_px"])
    h = float(params["height_px"])
    cx = _W / 2
    cy_elev = _PAD + 60
    cy_plan = _H - _PAD - 80
    shown = str(params.get("shown_view", "none")) if not draw else "both"

    parts: list[str] = []
    if shown in ("both", "elevation"):
        parts += _shape_parts(elev, cx, cy_elev, w, h)
        parts.append(_text(cx - w / 2 - 24, cy_elev, "立面図", anchor="end"))
    if shown in ("both", "plan"):
        parts += _shape_parts(plan, cx, cy_plan, w, w)
        parts.append(_text(cx - w / 2 - 24, cy_plan, "平面図", anchor="end"))
    if shown == "both":
        # 対応を示す縦の破線（教科書の並べ方）
        for dx in (-w / 2, w / 2):
            parts.append(
                _line(cx + dx, cy_elev + h / 2, cx + dx, cy_plan - w / 2, dashed=True)
            )
        # 「長さがわかるようにかけ」に答えるため、高さ（立面図の縦）と底面（平面図の横）を
        # 書き入れる。`dim_labels` = [底面, 高さ] の順（solid_labels が whitelist に載せる）。
        parts += _dimension_labels(
            params,
            radius_at=(cx, cy_plan + w / 2 + 14),
            height_at=(cx + w / 2 + 30, cy_elev),
        )
    return parts


# ---------------------------------------------------------------------------
# 展開図（net）
# ---------------------------------------------------------------------------
def _net_parts(params: dict[str, Any]) -> list[str]:
    """展開図。角柱＝側面の帯＋底面2枚、円柱＝長方形＋円2枚、円錐＝おうぎ形＋円。"""
    kind = str(params["solid_kind"])
    w = float(params["width_px"])
    h = float(params["height_px"])
    parts: list[str] = []
    if kind == "cylinder":
        r = float(params["radius_px"])
        band_w = float(params["band_width_px"])
        x0, y0 = _PAD + 20, _H / 2 - h / 2
        parts += [_polygon([
            (x0, y0), (x0 + band_w, y0), (x0 + band_w, y0 + h), (x0, y0 + h)
        ])]
        parts.append(_circle(x0 + band_w / 2, y0 - r - 8, r))
        parts.append(_circle(x0 + band_w / 2, y0 + h + r + 8, r))
        return parts
    if kind == "cylinder_cone_side":
        # 複合立体（円柱の上に円錐）の側面だけの展開図: 長方形とおうぎ形を横に並べる。
        band_w = float(params["band_width_px"])
        slant = float(params["slant_px"])
        angle = float(params["sector_angle_deg"])
        x0, y0 = _PAD, _H / 2 - h / 2
        parts.append(_polygon([
            (x0, y0), (x0 + band_w, y0), (x0 + band_w, y0 + h), (x0, y0 + h)
        ]))
        a0, a1 = math.radians(-angle / 2), math.radians(angle / 2)
        # おうぎ形が長方形に重ならないように置く。中心角が 180°を超えると扇は中心より
        # 左にもはみ出すので、はみ出し量を測ってから左端を決める（固定の余白では重なる）。
        gap = 28.0
        left_overhang = max(0.0, -min(math.cos(a0), math.cos(a1), 1.0)) * slant
        avail = _W - _PAD - (x0 + band_w + gap)
        span = slant + left_overhang
        if span > avail:  # 枠に収まるよう縮める
            slant *= avail / span
            left_overhang *= avail / span
        cx = x0 + band_w + gap + left_overhang
        cy = _H / 2
        p0 = (cx + slant * math.cos(a0), cy + slant * math.sin(a0))
        p1 = (cx + slant * math.cos(a1), cy + slant * math.sin(a1))
        large = 1 if angle > 180 else 0
        parts.append(
            f'<path d="M {cx:.2f} {cy:.2f} L {p0[0]:.2f} {p0[1]:.2f} '
            f'A {slant:.2f} {slant:.2f} 0 {large} 1 {p1[0]:.2f} {p1[1]:.2f} Z" '
            f'fill="none" stroke="{_STROKE}" stroke-width="{_THIN}"/>'
        )
        labels = list(params.get("dim_labels") or [])
        anchors = [
            (x0 - 6, _H / 2),                    # 円柱側面の縦
            (x0 + band_w / 2, y0 + h + 16),      # 円柱側面の横
            (cx + slant * 0.55, cy - 10),        # おうぎ形の半径
            (cx + slant + 24, cy + 18),          # おうぎ形の弧の長さ
        ]
        for lab, (lx, ly) in zip(labels, anchors, strict=False):
            parts.append(_text(lx, ly, str(lab)))
        return parts
    if kind == "cone":
        r = float(params["radius_px"])
        slant = float(params["slant_px"])
        angle = float(params["sector_angle_deg"])
        cx, cy = _PAD + 140, _H / 2
        a0 = math.radians(-angle / 2)
        a1 = math.radians(angle / 2)
        p0 = (cx + slant * math.cos(a0), cy + slant * math.sin(a0))
        p1 = (cx + slant * math.cos(a1), cy + slant * math.sin(a1))
        large = 1 if angle > 180 else 0
        parts.append(
            f'<path d="M {cx:.2f} {cy:.2f} L {p0[0]:.2f} {p0[1]:.2f} '
            f'A {slant:.2f} {slant:.2f} 0 {large} 1 {p1[0]:.2f} {p1[1]:.2f} Z" '
            f'fill="none" stroke="{_STROKE}" stroke-width="{_THIN}"/>'
        )
        parts.append(_circle(cx + slant + r + 16, cy, r))
        return parts
    # 角柱: 側面の帯（辺の数ぶんの長方形）＋底面2枚。
    # 底面の形は側面の枚数で決まる（3枚なら正三角形・6枚なら正六角形）。角柱の展開図で
    # 底面を一律に長方形で描くと、三角柱や五角柱・六角柱の展開図が誤りになる。
    faces = int(params.get("face_count", 4))
    # 帯（faces 枚ぶん）と底面が枠に収まるよう、1枚の幅を自動で縮める。
    avail = _W - 2 * _PAD
    w = min(w, avail / (faces + 1))
    x0, y0 = _PAD, _H / 2 - h / 2
    for i in range(faces):
        x = x0 + i * w
        parts.append(_polygon([(x, y0), (x + w, y0), (x + w, y0 + h), (x, y0 + h)]))
    parts += _net_base_parts(faces, x0, y0, w, above=True)
    parts += _net_base_parts(faces, x0, y0 + h, w, above=False)
    return parts


def _net_base_parts(
    faces: int, x0: float, y_edge: float, base: float, *, above: bool
) -> list[str]:
    """展開図の底面1枚（正 faces 角形）を、側面の帯の1辺に貼り付ける。

    帯の左端の1辺 [x0, x0+base] をそのまま多角形の1辺として使い、正多角形を
    その外側（above=True なら上）に組む。`above` は貼り付ける側。
    """
    n = max(3, faces)
    # 正n角形: 1辺 base のとき、外接円の半径 R と、辺から中心までの距離（アポテム）。
    apothem = base / (2 * math.tan(math.pi / n))
    radius = base / (2 * math.sin(math.pi / n))
    cx = x0 + base / 2
    cy = y_edge - apothem if above else y_edge + apothem
    start = math.atan2(y_edge - cy, x0 - cx)
    step = 2 * math.pi / n
    # above のときは辺の左端から時計回り（画面座標では角度が減る向き）に頂点を並べる。
    sign = -1.0 if above else 1.0
    pts = [
        (cx + radius * math.cos(start + sign * step * k),
         cy + radius * math.sin(start + sign * step * k))
        for k in range(n)
    ]
    return [_polygon(pts)]


# ---------------------------------------------------------------------------
# 断面（section）と回転体の元図（rotation_source）
# ---------------------------------------------------------------------------
def _section_parts(params: dict[str, Any]) -> list[str]:
    """頂点名つきの多角形1枚（見取図から抜き出した断面／回転体の切り口）。

    形は `section_shape` で切り替える。円柱を軸をふくむ平面で切ると長方形、
    円錐なら二等辺三角形になる——ここを一律に長方形で描くと図が答えと食い違う。
    """
    shape = str(params.get("section_shape", "rectangle"))
    w = float(params["width_px"])
    h = float(params["height_px"])
    cx, cy = _W / 2, _H / 2
    a = (cx - w / 2, cy + h / 2)
    b = (cx + w / 2, cy + h / 2)
    c = (cx + w / 2, cy - h / 2)
    d = (cx - w / 2, cy - h / 2)
    if shape == "isosceles_triangle":
        apex = (cx, cy - h / 2)
        parts = [_polygon([a, b, apex])]
        return parts + _vertex_labels(params, {"A": a, "B": b, "C": apex})
    parts = [_polygon([a, b, c, d])]
    if params.get("draw_diagonal"):
        parts.append(_line(*a, *c))
    return parts + _vertex_labels(params, {"A": a, "B": b, "C": c, "D": d})


def _rotation_source_parts(params: dict[str, Any]) -> list[str]:
    """回転させる平面図形と、回転の軸（一点鎖線）。

    `shape` ∈ {"rectangle", "right_triangle"}。軸は図形の左辺に重ねて縦に引く。
    """
    shape = str(params.get("shape", "rectangle"))
    w = float(params["width_px"])
    h = float(params["height_px"])
    cx, cy = _W / 2, _H / 2
    x0 = cx - w / 2
    y_top = cy - h / 2
    y_bot = cy + h / 2
    if shape == "semicircle":
        # 半円を直径（＝回転の軸）が縦になる向きに置く。直径の両端と弧の頂点に
        # 名前を振れるよう、頂点の位置は3つ返す。
        r = h / 2
        parts = [
            f'<path d="M {x0:.2f} {y_top:.2f} A {r:.2f} {r:.2f} 0 0 1 '
            f'{x0:.2f} {y_bot:.2f} Z" fill="none" stroke="{_STROKE}" '
            f'stroke-width="{_THIN}"/>',
            _chain_line(x0, y_top - 30, x0, y_bot + 30),
        ]
        pts = [(x0, y_bot), (x0 + r, cy), (x0, y_top)]
    else:
        if shape == "right_triangle":
            pts = [(x0, y_bot), (x0 + w, y_bot), (x0, y_top)]
        else:
            pts = [(x0, y_bot), (x0 + w, y_bot), (x0 + w, y_top), (x0, y_top)]
        parts = [_polygon(pts), _chain_line(x0, y_top - 30, x0, y_bot + 30)]
    slots = {chr(ord("A") + i): q for i, q in enumerate(pts)}
    return parts + _vertex_labels(params, slots)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
_VIEW_BUILDERS = {
    "projection": None,  # draw を見るので個別に扱う
    "net": _net_parts,
    "section": _section_parts,
    "rotation_source": _rotation_source_parts,
}


def render_solid_svg(params: dict[str, Any], *, draw: bool) -> str:
    """params の `view` に応じて立体の図を描く。

    `draw=False` は「かく」セルの問題図＝答えの図を先出ししない。
    見取図・展開図・断面は答えそのものなので `draw=False` なら空（外枠だけ）を返す。
    投影図は「示されている側だけ」を描く（`shown_view`）。
    回転体の元図は答えではないので常に描く。
    """
    view = str(params["view"])
    if view == "projection":
        return _svg(_projection_parts(params, draw=draw))
    if view == "rotation_source":
        return _svg(_rotation_source_parts(params))
    if not draw:
        return _svg([])
    if view == "sketch":
        builder = _SKETCH_BY_KIND.get(str(params["solid_kind"]))
        if builder is None:
            raise ValueError(f"見取図に未対応の立体: {params['solid_kind']!r}")
        return _svg(builder(params))
    builder2 = _VIEW_BUILDERS.get(view)
    if builder2 is None:
        raise ValueError(f"未知の view: {view!r}")
    return _svg(builder2(params))


def _draw_from_plan(mr: "MR") -> bool:
    """visual_plan.elements に "solid" 要素が宣言されていれば図を描く。"""
    plan = mr.visual_plan
    if plan is None:
        return False
    return any(e.kind == "solid" for e in plan.elements)


def render_solid(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。"""
    return render_solid_svg(mr.params, draw=_draw_from_plan(mr))


def render_solid_solution_svg(params: dict[str, Any]) -> str:
    """「かく」セルの模範解答図（答えの立体・展開図・断面を描く）。"""
    return render_solid_svg(params, draw=True)


register_visual("math.solid")(render_solid)


__all__ = [
    "render_solid",
    "render_solid_svg",
    "render_solid_solution_svg",
    "solid_labels",
]
