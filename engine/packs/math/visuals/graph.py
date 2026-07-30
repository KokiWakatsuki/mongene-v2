"""一次関数グラフの SVG レンダラ（実装設計 §6.4・§8.2 G-Q5v）。

matplotlib に依存しない自己完結の SVG 文字列生成。座標平面（グリッド線・x軸/y軸・
軸目盛の数値ラベル・直線1本）を描く。モノクロ印刷可（色に情報を載せない。線種・
太さのみで区別する）。

`<text>` 要素は軸目盛の数値のみ。呼び出し側（recipe）はこれらの目盛文字列を
`visual_plan.labels` に含めることで G-Q5v（SVG 内テキスト ⊆ whitelist）を満たす。

`@register_visual("math.linear_graph")` で登録。シグネチャ `(mr, ctx) -> str`。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, NamedTuple

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

# --- 量-量グラフ（grid_mode="quantity"）用 ---
_QUANTITY_MAX_TICKS = 12  # 1軸に置く目盛の本数の上限（これを超えないよう間隔を粗くする）
_NICE_MANTISSAS = (1, 2, 5)  # 切りのよい目盛間隔の仮数（×10ⁿ）


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


class _GridSpec(NamedTuple):
    """グリッドの範囲と目盛間隔（座標平面は間隔 1・量-量グラフは軸ごとに粗い間隔）。"""

    x_lo: int
    x_hi: int
    y_lo: int
    y_hi: int
    x_step: int
    y_step: int


def _nice_step(v_max: int) -> int:
    """0〜v_max を `_QUANTITY_MAX_TICKS` 本以内の目盛で覆う、切りのよい間隔（1/2/5×10ⁿ）。"""
    if v_max <= _QUANTITY_MAX_TICKS:
        return 1
    scale = 1
    for _ in range(10):  # 10¹⁰ まで見れば教材の値域は尽きる
        for mantissa in _NICE_MANTISSAS:
            step = mantissa * scale
            if v_max <= _QUANTITY_MAX_TICKS * step:
                return step
        scale *= 10
    raise ValueError(f"目盛間隔を決められない大きさ: {v_max}")  # pragma: no cover - 非現実な値域


def _quantity_grid_spec(xs: list[sympy.Expr], ys: list[sympy.Expr]) -> _GridSpec:
    """量-量グラフ（x と y で単位が違う）のグリッド範囲＋目盛間隔。

    時間 x 秒と面積 y cm² のように**単位の異なる2量**の関係を表すグラフでは、縦横で
    縮尺を揃える意味がない（教科書のグラフも軸ごとに目盛を取る）。そこで座標平面
    （`compute_grid_spec_from_params` の既定経路）と違い、
    ①第1象限のみ（x,y≧0 の量）②軸ごとに独立な目盛間隔③値の大きい軸は目盛を粗く、
    の3点で描く。範囲は最大値の1目盛先まで（点が枠に貼りつかない余白）。
    """
    x_max, y_max = max(int(v) for v in xs), max(int(v) for v in ys)
    assert min(int(v) for v in xs) >= 0 and min(int(v) for v in ys) >= 0, (
        "量-量グラフ（grid_mode=quantity）は第1象限のみを描く（負の値は非対応）"
    )
    x_step, y_step = _nice_step(x_max), _nice_step(y_max)
    return _GridSpec(
        x_lo=0,
        x_hi=(x_max // x_step + 1) * x_step,
        y_lo=0,
        y_hi=(y_max // y_step + 1) * y_step,
        x_step=x_step,
        y_step=y_step,
    )


def compute_grid_spec_from_params(params: dict[str, Any]) -> _GridSpec:
    """params（recipe が MR.params に残す a/b/pts）の pts が収まるグリッド範囲と目盛間隔。

    既定は**座標平面**（x も y も同じ数直線＝縦横等スケール・目盛は 1 刻み）。
    `params["grid_mode"] == "quantity"` を宣言したセルのみ量-量グラフの範囲取り
    （`_quantity_grid_spec`）に切り替わる。宣言しない既存セルは従来と完全に同じ
    計算を通る（＝出力バイト列不変・既存 golden 不変）。
    """
    pts_raw = params["pts"]
    pts = [_parse_point(s) for s in pts_raw]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if params.get("grid_mode") == "quantity":
        return _quantity_grid_spec(xs, ys)
    x_lo, x_hi = _compute_range(xs)
    y_lo, y_hi = _compute_range(ys)
    half = max(x_hi - x_lo, y_hi - y_lo)
    x_mid = (x_lo + x_hi) / 2
    y_mid = (y_lo + y_hi) / 2
    x_lo = int(x_mid - half / 2)
    x_hi = int(x_mid + half / 2)
    y_lo = int(y_mid - half / 2)
    y_hi = int(y_mid + half / 2)
    return _GridSpec(x_lo, x_hi, y_lo, y_hi, 1, 1)


def compute_grid_bounds_from_params(params: dict[str, Any]) -> tuple[int, int, int, int]:
    """グリッド範囲 (x_lo, x_hi, y_lo, y_hi) だけを返す（目盛間隔は不要な呼び出し用）。

    render_linear_graph と recipe 側（visual_plan.labels 構築）が同じロジックを
    共有するための公開ヘルパー（labels と実描画の目盛を機械的に一致させる）。
    """
    spec = compute_grid_spec_from_params(params)
    return spec.x_lo, spec.x_hi, spec.y_lo, spec.y_hi


def compute_grid_bounds(mr: "MR") -> tuple[int, int, int, int]:
    """`compute_grid_bounds_from_params(mr.params)` のショートカット。"""
    return compute_grid_bounds_from_params(mr.params)


def tick_labels_from_params(params: dict[str, Any]) -> list[str]:
    """実描画される軸目盛の数値ラベル一覧（0 を除く。visual_plan.labels 用）。

    recipe が MR を組み立てる前（params だけがある時点）から呼べるよう、
    dict を直接受け取る形にしてある（`tick_labels` はその MR 版ショートカット）。
    """
    spec = compute_grid_spec_from_params(params)
    labels: list[str] = []
    for gx in range(spec.x_lo, spec.x_hi + 1, spec.x_step):
        if gx == 0:
            continue
        labels.append(_format_tick(sympy.Integer(gx)))
    for gy in range(spec.y_lo, spec.y_hi + 1, spec.y_step):
        labels.append(_format_tick(sympy.Integer(gy)))
    return labels


def tick_labels(mr: "MR") -> list[str]:
    """`tick_labels_from_params(mr.params)` のショートカット。"""
    return tick_labels_from_params(mr.params)


class _GridScaffold(NamedTuple):
    """座標平面の土台（SVG open+rect+グリッド+軸）と座標変換・範囲。

    render_grid_svg / render_segment_solution_svg / render_polyline_svg が共有し、
    土台の後に各自の描画要素（直線・線分＋端点・折れ線）を挿し、最後に目盛を足す。
    """

    parts: list[str]
    to_px_x: Callable[[float], float]
    to_px_y: Callable[[float], float]
    x_lo: int
    x_hi: int
    y_lo: int
    y_hi: int
    plot_lo: float
    plot_hi: float
    # 目盛間隔（既定 1＝座標平面。量-量グラフのみ粗くなる。既存の呼び出し側が
    # 9 引数で構築できるよう末尾に既定値つきで置く）
    x_step: int = 1
    y_step: int = 1


def _grid_scaffold(params: dict[str, Any]) -> _GridScaffold:
    """SVG open+rect+グリッド線+軸までを組む（描画要素・目盛の手前まで・決定論）。"""
    spec = compute_grid_spec_from_params(params)
    x_lo, x_hi, y_lo, y_hi = spec.x_lo, spec.x_hi, spec.y_lo, spec.y_hi

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
    for gx in range(x_lo, x_hi + 1, spec.x_step):
        px = to_px_x(gx)
        parts.append(
            f'<line x1="{px:.2f}" y1="{plot_lo:.2f}" x2="{px:.2f}" y2="{plot_hi:.2f}" '
            f'stroke="#bbbbbb" stroke-width="0.5"/>'
        )
    for gy in range(y_lo, y_hi + 1, spec.y_step):
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

    return _GridScaffold(
        parts, to_px_x, to_px_y, x_lo, x_hi, y_lo, y_hi, plot_lo, plot_hi,
        spec.x_step, spec.y_step,
    )


def _grid_ticks(sc: _GridScaffold) -> list[str]:
    """軸目盛の数値ラベル（<text> はこれのみ。visual_plan.labels と一致させる）。"""
    ticks: list[str] = []
    py0 = sc.to_px_y(0) if sc.y_lo <= 0 <= sc.y_hi else sc.plot_hi
    for gx in range(sc.x_lo, sc.x_hi + 1, sc.x_step):
        if gx == 0:
            continue  # 原点の重複表記を避ける（0 は y 軸側で1回だけ出す）
        px = sc.to_px_x(gx)
        ticks.append(
            f'<text x="{px:.2f}" y="{py0 + 12:.2f}" font-size="10" '
            f'text-anchor="middle" fill="#000000">{_format_tick(sympy.Integer(gx))}</text>'
        )
    px0 = sc.to_px_x(0) if sc.x_lo <= 0 <= sc.x_hi else sc.plot_lo
    for gy in range(sc.y_lo, sc.y_hi + 1, sc.y_step):
        py = sc.to_px_y(gy)
        ticks.append(
            f'<text x="{px0 - 8:.2f}" y="{py + 3:.2f}" font-size="10" '
            f'text-anchor="end" fill="#000000">{_format_tick(sympy.Integer(gy))}</text>'
        )
    return ticks


def render_grid_svg(
    params: dict[str, Any],
    *,
    draw_line: bool,
    vline_x: Any = None,
    hline_y: Any = None,
) -> str:
    """params（a, b, pts）と描画範囲から座標平面 SVG を組む（決定論・自己完結）。

    draw_line=True: グリッド+軸+目盛+直線1本（read セルの問題図／かくセルの解答図）。
    draw_line=False: グリッド+軸+目盛のみの空の方眼（かくセルの問題図＝生徒が描き込む）。
      この場合 params に "a"/"b"（直線の傾き・切片）は不要（"pts" で描画範囲だけ決める）。

    vline_x/hline_y（keyword-only・任意）: x=k / y=k の特殊直線を追加で描く（g2_l26 Lv2）。
      既定 None では描かないため、既存の呼び出し（傾きのある直線1本）は完全に後方互換
      （出力バイト列が不変＝既存 golden 不変）。特殊直線も主直線と同じ黒の実線・太さで描く
      （色に情報を載せない＝モノクロ印刷可・N-4 適合）。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts

    # --- 直線（太い黒の実線。線種・太さのみで区別＝モノクロ印刷可） ---
    # draw_line=False（かくセルの問題図＝空の方眼）では直線を描かない（a/b も参照しない）。
    if draw_line:
        a = sympy.nsimplify(sympy.sympify(params["a"]))
        b = sympy.nsimplify(sympy.sympify(params["b"]))
        x_start, x_end = sc.x_lo, sc.x_hi
        y_start = a * x_start + b
        y_end = a * x_end + b
        px1, py1 = sc.to_px_x(x_start), sc.to_px_y(float(y_start))
        px2, py2 = sc.to_px_x(x_end), sc.to_px_y(float(y_end))
        parts.append(
            f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
            f'stroke="#000000" stroke-width="2.5"/>'
        )

    # --- 特殊直線 x=k（垂直）/ y=k（水平）（g2_l26 Lv2・任意） ---
    if vline_x is not None:
        vx = float(sympy.nsimplify(sympy.sympify(vline_x)))
        pvx = sc.to_px_x(vx)
        parts.append(
            f'<line x1="{pvx:.2f}" y1="{sc.plot_lo:.2f}" x2="{pvx:.2f}" y2="{sc.plot_hi:.2f}" '
            f'stroke="#000000" stroke-width="2.5"/>'
        )
    if hline_y is not None:
        hy = float(sympy.nsimplify(sympy.sympify(hline_y)))
        phy = sc.to_px_y(hy)
        parts.append(
            f'<line x1="{sc.plot_lo:.2f}" y1="{phy:.2f}" x2="{sc.plot_hi:.2f}" y2="{phy:.2f}" '
            f'stroke="#000000" stroke-width="2.5"/>'
        )

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


def _draw_line_from_plan(mr: "MR") -> bool:
    """visual_plan.elements に "line" 要素が宣言されていれば直線を描く。

    既存の read セル（g2_l25.graph_table / g2_l21）は line 要素を宣言済みなので
    draw_line=True で従来どおり。かくセルの問題図は elements=[grid, axis] のみ
    （line なし）にして空の方眼を描く。
    """
    if mr.visual_plan is None:
        return True
    return any(e.kind == "line" for e in mr.visual_plan.elements)


def render_linear_graph(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。visual_plan の line 要素の有無で直線描画を切替える。"""
    return render_grid_svg(mr.params, draw_line=_draw_line_from_plan(mr))


def render_line_solution_svg(params: dict[str, Any]) -> str:
    """かくセルの模範解答図（直線つき）。recipe が GraphAnswer.solution_svg_ref に格納する。

    問題図（空の方眼）と同じ params・同じ描画範囲を使うので図の座標系が一致する。
    """
    return render_grid_svg(params, draw_line=True)


def render_special_lines_solution_svg(params: dict[str, Any]) -> str:
    """特殊直線つきの模範解答図（g2_l26 Lv2）。主直線 y=ax+b＋特殊直線 x=k / y=k を描く。

    params に "a"/"b"（主直線）と、"vline_x"（x=k）または "hline_y"（y=k）のいずれかを持つ。
    問題図（空の方眼）と同じ pts・描画範囲を使うので座標系が一致する。
    """
    return render_grid_svg(
        params,
        draw_line=True,
        vline_x=params.get("vline_x"),
        hline_y=params.get("hline_y"),
    )


def render_segment_solution_svg(params: dict[str, Any]) -> str:
    """線分（変域つきグラフ）の模範解答図（g2_l23 Lv2）。

    params: a, b（直線 y=ax+b）／seg_x_lo, seg_x_hi（変域の両端 x）／closed_lo, closed_hi（端点の
    開閉＝閉区間は塗り● / 開区間は白抜き○）。端点の開閉は「塗り/白抜き」で区別する（色に情報を
    載せない＝モノクロ印刷可・N-4 適合）。問題図は空の方眼（render_grid_svg draw_line=False）と
    同じ pts・範囲を使う。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts

    a = sympy.nsimplify(sympy.sympify(params["a"]))
    b = sympy.nsimplify(sympy.sympify(params["b"]))
    x_lo = sympy.sympify(params["seg_x_lo"])
    x_hi = sympy.sympify(params["seg_x_hi"])
    y_lo = a * x_lo + b
    y_hi = a * x_hi + b
    px1, py1 = sc.to_px_x(float(x_lo)), sc.to_px_y(float(y_lo))
    px2, py2 = sc.to_px_x(float(x_hi)), sc.to_px_y(float(y_hi))

    # --- 線分本体（太い黒の実線・変域の両端で止める） ---
    parts.append(
        f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
        f'stroke="#000000" stroke-width="2.5"/>'
    )

    # --- 端点マーカー（閉=塗り● / 開=白抜き○・色以外で区別） ---
    for (px, py), closed in ((( px1, py1), bool(params["closed_lo"])),
                             ((px2, py2), bool(params["closed_hi"]))):
        if closed:
            parts.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="#000000"/>'
            )
        else:
            parts.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="#ffffff" '
                f'stroke="#000000" stroke-width="1.5"/>'
            )

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


register_visual("math.linear_graph")(render_linear_graph)


__all__ = [
    "render_linear_graph",
    "render_grid_svg",
    "render_line_solution_svg",
    "render_special_lines_solution_svg",
    "render_segment_solution_svg",
    "compute_grid_bounds",
    "compute_grid_bounds_from_params",
    "compute_grid_spec_from_params",
    "tick_labels",
    "tick_labels_from_params",
]
