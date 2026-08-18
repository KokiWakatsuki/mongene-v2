"""一次関数グラフの SVG レンダラ（実装設計 §6.4・§8.2 G-Q5v）。

matplotlib に依存しない自己完結の SVG 文字列生成。座標平面（グリッド線・x軸/y軸・
軸目盛の数値ラベル・直線1本）を描く。モノクロ印刷可（色に情報を載せない。線種・
太さのみで区別する）。

`<text>` 要素は軸目盛の数値のみ。呼び出し側（recipe）はこれらの目盛文字列を
`visual_plan.labels` に含めることで G-Q5v（SVG 内テキスト ⊆ whitelist）を満たす。

`@register_visual("math.linear_graph")` で登録。シグネチャ `(mr, ctx) -> str`。
"""
from __future__ import annotations

import math

from typing import TYPE_CHECKING, Any, Callable, NamedTuple

import sympy

from engine.core.registry import register_visual
from engine.packs.math.visuals._label_place import centroid, haloed_text, outward

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


def _landing_step(values: list[int], v_max: int) -> int:
    """打つ点が**方眼の線の上に載る**目盛間隔。載せられなければ切りのよい間隔に戻す。

    ★「グラフにかけ」の問題で、答えの折れ点が (36, 648) なのに、方眼は横10刻み・
    縦100刻みだった。**答えの点が1つも打てない方眼**を配っていたことになる
    （点検の指摘）。切りのよさ（1/2/5×10ⁿ）は読みやすさのためだが、
    かく問題では「点が線に載る」ほうが先に来る。

    打つ値すべての最大公約数の約数のうち、目盛の本数が上限を超えず、かつ
    最も粗いものを選ぶ。1目盛が細かすぎる（本数が上限超え）ものは採らない。
    """
    nice = _nice_step(v_max)
    positives = [v for v in values if v > 0]
    if not positives:
        return nice
    g = positives[0]
    for v in positives[1:]:
        g = math.gcd(g, v)
    if g <= 0:
        return nice
    if g % nice == 0:
        return nice   # すでに載る（細かくする必要がない）
    # **粗ければよいわけではない。** 最大の約数を採ると、点が2つ（0 と 648）の軸で
    # 目盛が 648 刻みになり、線が2本の「方眼でないもの」が出た。本数が上限内の
    # 約数のうち、**切りのよい間隔にいちばん近いもの**を選ぶ。
    candidates = [
        d for d in range(1, g + 1)
        if g % d == 0 and v_max <= _QUANTITY_MAX_TICKS * d
    ]
    if not candidates:
        return nice
    return min(candidates, key=lambda d: (abs(d - nice), -d))


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
    x_step = _landing_step([int(v) for v in xs], x_max)
    y_step = _landing_step([int(v) for v in ys], y_max)
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
    # **描かないが枠には入れたい点**（移動後の図形など）。
    # 平行移動・回転の問題で、方眼の範囲を「元の図形」だけから決めていたため、
    # **移動後の三角形が方眼の外に出て生徒が描けない**状態だった（60 seed 中 43 件）。
    # 移動先は答えなので描かないが、枠には入っていなければならない。
    pts += [_parse_point(s) for s in params.get("bbox_pts", [])]
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


# 目盛ラベルの最小の間隔（px）。"-16" のような3文字が隣とぶつからない幅。
_MIN_LABEL_GAP_PX = 20.0


def _label_stride(lo: int, hi: int, step: int) -> int:
    """軸ラベルを何目盛おきに出すか。

    **範囲が広いと目盛ラベルが重なって読めなくなる。** -16〜16 を1目盛おきに書くと
    33個のラベルが約344pxに並び、"-16-15-14-13…" と続いて読めなかった
    （グラフから座標を読ませる問題なのに、読めない）。教科書と同じく間引く。
    """
    count = len(range(lo, hi + 1, step))
    if count <= 1:
        return 1
    gap = (_SVG_SIZE - 2 * _MARGIN) / (count - 1)
    for k in (1, 2, 5, 10):
        if gap * k >= _MIN_LABEL_GAP_PX:
            return k
    return 10


def _labelled_ticks(lo: int, hi: int, step: int) -> list[int]:
    """ラベルを書く目盛の値（0 を基準に間引くので、原点まわりが左右対称になる）。"""
    span = step * _label_stride(lo, hi, step)
    return [g for g in range(lo, hi + 1, step) if g % span == 0]


def tick_labels_from_params(params: dict[str, Any]) -> list[str]:
    """実描画される軸目盛の数値ラベル一覧（0 を除く。visual_plan.labels 用）。

    recipe が MR を組み立てる前（params だけがある時点）から呼べるよう、
    dict を直接受け取る形にしてある（`tick_labels` はその MR 版ショートカット）。
    """
    spec = compute_grid_spec_from_params(params)
    labels: list[str] = []
    for gx in _labelled_ticks(spec.x_lo, spec.x_hi, spec.x_step):
        if gx == 0:
            continue
        labels.append(_format_tick(sympy.Integer(gx)))
    for gy in _labelled_ticks(spec.y_lo, spec.y_hi, spec.y_step):
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


def _line_endpoints_in_grid(
    a: sympy.Expr, b: sympy.Expr, sc: _GridScaffold
) -> tuple[float, float, float, float] | None:
    """直線 y=ax+b を、方眼の枠 [x_lo,x_hi]×[y_lo,y_hi] で切り取った画素座標を返す。

    枠の左端から右端まで引くと、**傾きが大きいとき線が枠の外へはみ出す**
    （y が y_lo..y_hi に収まらない）。曲線のほうは `_curve_polylines` が枠外を
    切っているのに、直線だけ切っていなかった。市販の教材では直線は必ず枠内で
    止まる。枠と交わらない直線は None（引かない）。
    """
    x_lo, x_hi = float(sc.x_lo), float(sc.x_hi)
    y_lo, y_hi = float(sc.y_lo), float(sc.y_hi)
    a_f, b_f = float(a), float(b)

    if a_f == 0:
        if not (y_lo <= b_f <= y_hi):
            return None
        xs = (x_lo, x_hi)
    else:
        # y が枠内に収まる x の区間を、左右の枠と上下の枠の両方から狭める。
        x_at_y_lo, x_at_y_hi = (y_lo - b_f) / a_f, (y_hi - b_f) / a_f
        lo = max(x_lo, min(x_at_y_lo, x_at_y_hi))
        hi = min(x_hi, max(x_at_y_lo, x_at_y_hi))
        if lo >= hi:
            return None
        xs = (lo, hi)

    return (
        sc.to_px_x(xs[0]), sc.to_px_y(a_f * xs[0] + b_f),
        sc.to_px_x(xs[1]), sc.to_px_y(a_f * xs[1] + b_f),
    )


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
        f'width="{_SVG_SIZE}" height="{_SVG_SIZE}" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, Noto Sans JP, Yu Gothic, Meiryo, sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{_SVG_SIZE}" height="{_SVG_SIZE}" fill="#ffffff" stroke="none"/>')

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


_TICK_FONT = 10.0


def _tick_label(px: float, py: float, anchor: str, text: str) -> str:
    """目盛の数値。白い縁取りを付けて、上を通る線に負けないようにする。

    目盛は最後に描くので文字自体はグラフ線の上に来るが、線は文字の隙間を
    そのまま通る。傾きの急な直線や放物線が y 軸のそばを通ると、「-4」「-6」の
    上に太い線が重なって読めなくなっていた（走査で 149 件）。
    """
    return haloed_text(px, py, text, size=_TICK_FONT, anchor=anchor)


def grid_tick_anchors(sc: _GridScaffold) -> list[tuple[float, float]]:
    """目盛の数値ラベルを置く位置。**そこへ他のラベルを置かない**ために使う。

    多角形の頂点が軸の上にあると、頂点名と目盛の数字がぴったり重なって
    どちらも読めなくなっていた（走査で6件）。
    """
    out: list[tuple[float, float]] = []
    py0 = sc.to_px_y(0) if sc.y_lo <= 0 <= sc.y_hi else sc.plot_hi
    for gx in _labelled_ticks(sc.x_lo, sc.x_hi, sc.x_step):
        if gx != 0:
            out.append((sc.to_px_x(gx), py0 + 12))
    px0 = sc.to_px_x(0) if sc.x_lo <= 0 <= sc.x_hi else sc.plot_lo
    for gy in _labelled_ticks(sc.y_lo, sc.y_hi, sc.y_step):
        out.append((px0 - 8, sc.to_px_y(gy) + 3))
    return out


def _grid_ticks(sc: _GridScaffold) -> list[str]:
    """軸目盛の数値ラベル（<text> はこれのみ。visual_plan.labels と一致させる）。"""
    ticks: list[str] = []
    py0 = sc.to_px_y(0) if sc.y_lo <= 0 <= sc.y_hi else sc.plot_hi
    for gx in _labelled_ticks(sc.x_lo, sc.x_hi, sc.x_step):
        if gx == 0:
            continue  # 原点の重複表記を避ける（0 は y 軸側で1回だけ出す）
        ticks.append(_tick_label(
            sc.to_px_x(gx), py0 + 12, "middle", _format_tick(sympy.Integer(gx))))
    px0 = sc.to_px_x(0) if sc.x_lo <= 0 <= sc.x_hi else sc.plot_lo
    for gy in _labelled_ticks(sc.y_lo, sc.y_hi, sc.y_step):
        ticks.append(_tick_label(
            px0 - 8, sc.to_px_y(gy) + 3, "end", _format_tick(sympy.Integer(gy))))
    return ticks


def render_grid_svg(
    params: dict[str, Any],
    *,
    draw_line: bool,
    vline_x: Any = None,
    hline_y: Any = None,
    extra_lines: list[tuple[Any, Any]] | None = None,
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
        ends = _line_endpoints_in_grid(a, b, sc)
        if ends is not None:
            px1, py1, px2, py2 = ends
            parts.append(
                f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
                f'stroke="#000000" stroke-width="2.5"/>'
            )

    # --- もう1本以上の直線（入試の「2直線の交点」など・任意） ---
    # ★**入試融合のセルは図が1枚も無かった。** 「2直線 y=3x-3 と y=4x-8 の交点を
    # N…三角形ONPの面積を求めよ」を、座標平面を思い浮かべながら解くことになる。
    # 実物の入試問題は必ずグラフが添えてある。主直線と同じ書式で重ねる。
    for ea, eb in extra_lines or []:
        ends2 = _line_endpoints_in_grid(
            sympy.nsimplify(sympy.sympify(ea)), sympy.nsimplify(sympy.sympify(eb)), sc
        )
        if ends2 is not None:
            qx1, qy1, qx2, qy2 = ends2
            parts.append(
                f'<line x1="{qx1:.2f}" y1="{qy1:.2f}" x2="{qx2:.2f}" y2="{qy2:.2f}" '
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


def render_line_and_polygon_svg(params: dict[str, Any], *, draw_line: bool) -> str:
    """直線1本と多角形を同じ座標平面に描く（exam_l1.graph_table Lv2）。

    直線は `render_grid_svg` と同じ描き方（params の "a"/"b"・太い黒の実線）、多角形は
    `params["polygon_pts"]` を順に結んだ閉じた折れ線。頂点には既存の折れ線図と同じ
    黒丸を打つ。色に情報を載せない（モノクロ印刷可・N-4 適合）。

    描画範囲は params["pts"] から決まるので、recipe は直線と多角形の**両方**が
    収まる点を "pts" に載せる。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts

    if draw_line:
        a = sympy.nsimplify(sympy.sympify(params["a"]))
        b = sympy.nsimplify(sympy.sympify(params["b"]))
        ends = _line_endpoints_in_grid(a, b, sc)
        if ends is not None:
            px1, py1, px2, py2 = ends
            parts.append(
                f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
                f'stroke="#000000" stroke-width="2.5"/>'
            )

    poly = [_parse_point(s) for s in params["polygon_pts"]]
    px = [(sc.to_px_x(float(x)), sc.to_px_y(float(y))) for x, y in poly]
    joined = " ".join(f"{a_:.2f},{b_:.2f}" for a_, b_ in px)
    parts.append(f'<polygon points="{joined}" fill="none" stroke="#000000" stroke-width="1.5"/>')
    for a_, b_ in px:
        parts.append(f'<circle cx="{a_:.2f}" cy="{b_:.2f}" r="4" fill="#000000"/>')

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


def render_line_polygon_graph(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。直線と多角形の位置関係を読むセル（exam_l1.graph_table Lv2）。"""
    return render_line_and_polygon_svg(mr.params, draw_line=_draw_line_from_plan(mr))


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
    """登録 visual（問題図）。visual_plan の line 要素の有無で直線描画を切替える。

    `params["extra_lines"]` があれば2本目以降も描く（入試の「2直線の交点」）。
    """
    extra = mr.params.get("extra_lines")
    return render_grid_svg(
        mr.params, draw_line=_draw_line_from_plan(mr),
        extra_lines=[tuple(e) for e in extra] if extra else None,
    )


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


# ---------------------------------------------------------------------------
# 曲線（放物線 y=ax² / 双曲線 y=a/x）
#
# 土台（_grid_scaffold / _grid_ticks）は直線に依存していないので、曲線は
# 「サンプリングした点列を polyline で結ぶ」だけで直線と同じ座標系に乗る。
# これ1つで C4（比例・反比例のグラフ）と C6（y=ax² のグラフ）の graph_table が
# 描けるようになる。比例 y=ax は直線なので既存の render_grid_svg 経路をそのまま使う。
# ---------------------------------------------------------------------------
_CURVE_SAMPLES = 241  # x 方向のサンプル点数（枠の端で 1/240 目盛以内に収まる細かさ）


def _curve_y(kind: str, coeff: sympy.Expr, x: sympy.Expr) -> sympy.Expr | None:
    """曲線の y 値（描けない点＝双曲線の x=0 では None）。"""
    if kind == "parabola":
        return coeff * x**2
    if kind == "hyperbola":
        if x == 0:
            return None
        return coeff / x
    raise ValueError(f"未知の curve_kind: {kind!r}（parabola / hyperbola）")


def _curve_polylines(kind: str, coeff: sympy.Expr, sc: _GridScaffold) -> list[list[tuple[float, float]]]:
    """曲線を、枠内に収まる連続区間ごとの画素座標の点列に離散化する。

    枠の外に出た区間で点列を切る（＝双曲線は原点付近で自然に2本の枝に分かれ、
    放物線は上端で切れる）。線を枠外へはみ出させないための処理であって、
    分岐そのものを場合分けで書いてはいない。
    """
    runs: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    span = sympy.Rational(sc.x_hi - sc.x_lo, _CURVE_SAMPLES - 1)
    for i in range(_CURVE_SAMPLES):
        x = sympy.Integer(sc.x_lo) + span * i
        y = _curve_y(kind, coeff, x)
        if y is None or not (sc.y_lo <= y <= sc.y_hi):
            if len(current) >= 2:
                runs.append(current)
            current = []
            continue
        current.append((sc.to_px_x(float(x)), sc.to_px_y(float(y))))
    if len(current) >= 2:
        runs.append(current)
    return runs


def _curve_arc_points(
    kind: str, coeff: sympy.Expr, sc: _GridScaffold, x_lo: sympy.Expr, x_hi: sympy.Expr
) -> list[tuple[float, float]]:
    """曲線の [x_lo, x_hi] 部分を画素座標の点列に離散化する（枠内に収まる前提）。"""
    span = sympy.Rational(x_hi - x_lo, _CURVE_SAMPLES - 1)
    out: list[tuple[float, float]] = []
    for i in range(_CURVE_SAMPLES):
        x = x_lo + span * i
        y = _curve_y(kind, coeff, x)
        if y is None:
            continue
        out.append((sc.to_px_x(float(x)), sc.to_px_y(float(y))))
    return out


def _hatch_lines_in_region(
    boundary: list[tuple[float, float]], clip_id: str
) -> list[str]:
    """境界 boundary（画素座標の閉多角形）の内側を斜線で塗る SVG 断片。

    clipPath で領域を切り抜き、45°の平行線を等間隔に引く（色に情報を載せない・
    モノクロ印刷可）。<text> は増えないので G-Q5v に影響しない。
    """
    poly = " ".join(f"{px:.2f},{py:.2f}" for px, py in boundary)
    parts = [
        f'<defs><clipPath id="{clip_id}"><polygon points="{poly}"/></clipPath></defs>',
        f'<g clip-path="url(#{clip_id})">',
    ]
    # 45°（右下がり）の平行線を、図全体を覆う範囲で等間隔に引く。
    step = 10
    for k in range(-_SVG_SIZE // step, 2 * _SVG_SIZE // step + 1):
        c = k * step
        parts.append(
            f'<line x1="{c}" y1="0" x2="{c + _SVG_SIZE}" y2="{_SVG_SIZE}" '
            f'stroke="#000000" stroke-width="0.7"/>'
        )
    parts.append("</g>")
    return parts


def render_curve_svg(
    params: dict[str, Any],
    *,
    draw_curve: bool,
    second_coeff: Any = None,
    line: tuple[Any, Any] | None = None,
    arc_range: tuple[Any, Any] | None = None,
    hatch_between: bool = False,
) -> str:
    """params（curve_kind, coeff, pts）から曲線つき／空の座標平面 SVG を組む。

    draw_curve=False は「かく」セルの問題図＝空の方眼（生徒が描き込む）。
    render_grid_svg と同じ土台・同じ範囲計算（pts 由来）を使うので、問題図と
    解答図の座標系は必ず一致する。

    keyword-only の追加要素（いずれも既定 None/False＝描かない。既存の呼び出しは
    出力バイト列が完全に不変＝既存 golden 不変）:

    - second_coeff: 同じ座標軸にもう1本の曲線を重ねる（g3_l33 Lv2「開き方の比較」）。
      1本目と区別できるよう破線にする（色ではなく線種で区別＝モノクロ印刷可）。
    - line: (m, b) の直線 y=mx+b を重ねる（g3_l37 Lv2「放物線と直線」）。
      render_grid_svg の直線描画と同じ書式・同じ太さ（黒の実線 2.5）。
    - arc_range: (x_lo, x_hi) の区間だけ曲線を太くなぞる（g3_l34 Lv2「変域の部分」）。
    - hatch_between: line と曲線が囲む部分（交点間）を斜線で示す（g3_l37 Lv2）。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts
    kind = str(params.get("curve_kind", "parabola"))

    if draw_curve:
        coeff = sympy.nsimplify(sympy.sympify(params["coeff"]))
        for run in _curve_polylines(kind, coeff, sc):
            pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in run)
            parts.append(
                f'<polyline points="{pts}" fill="none" '
                f'stroke="#000000" stroke-width="2.5"/>'
            )

    # --- 2本目の曲線（破線・線種で区別） ---
    if second_coeff is not None:
        coeff2 = sympy.nsimplify(sympy.sympify(second_coeff))
        for run in _curve_polylines(kind, coeff2, sc):
            pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in run)
            parts.append(
                f'<polyline points="{pts}" fill="none" stroke="#000000" '
                f'stroke-width="2.5" stroke-dasharray="7 5"/>'
            )

    # --- 直線 y=mx+b（render_grid_svg の直線と同じ書式・同じ太さ） ---
    if line is not None:
        m_s = sympy.nsimplify(sympy.sympify(line[0]))
        b_s = sympy.nsimplify(sympy.sympify(line[1]))
        ends = _line_endpoints_in_grid(m_s, b_s, sc)
        if ends is not None:
            px1, py1, px2, py2 = ends
            parts.append(
                f'<line x1="{px1:.2f}" y1="{py1:.2f}" x2="{px2:.2f}" y2="{py2:.2f}" '
                f'stroke="#000000" stroke-width="2.5"/>'
            )

    # --- 曲線と直線が囲む部分の斜線（境界＝放物線の弧＋直線） ---
    if hatch_between and line is not None:
        coeff = sympy.nsimplify(sympy.sympify(params["coeff"]))
        m_s = sympy.nsimplify(sympy.sympify(line[0]))
        b_s = sympy.nsimplify(sympy.sympify(line[1]))
        xa = sympy.nsimplify(sympy.sympify(params["hatch_x_lo"]))
        xb = sympy.nsimplify(sympy.sympify(params["hatch_x_hi"]))
        arc = _curve_arc_points(kind, coeff, sc, xa, xb)
        chord = [
            (sc.to_px_x(float(xb)), sc.to_px_y(float(m_s * xb + b_s))),
            (sc.to_px_x(float(xa)), sc.to_px_y(float(m_s * xa + b_s))),
        ]
        parts.extend(_hatch_lines_in_region(arc + chord, "enclosed-region"))

    # --- 変域に対応する部分を太くなぞる ---
    if arc_range is not None:
        coeff = sympy.nsimplify(sympy.sympify(params["coeff"]))
        xa = sympy.nsimplify(sympy.sympify(arc_range[0]))
        xb = sympy.nsimplify(sympy.sympify(arc_range[1]))
        arc = _curve_arc_points(kind, coeff, sc, xa, xb)
        pts = " ".join(f"{px:.2f},{py:.2f}" for px, py in arc)
        parts.append(
            f'<polyline points="{pts}" fill="none" '
            f'stroke="#000000" stroke-width="5"/>'
        )

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


def render_polyline_svg(params: dict[str, Any], *, draw_polyline: bool) -> str:
    """折れ線（区間ごとに式が変わる関数のグラフ）の SVG（g3_l38 Lv3）。

    params["poly_pts"]（"(x, y)" 文字列のリスト）を順に結ぶ。draw_polyline=False は
    「かく」セルの問題図＝空の方眼。範囲計算（pts 由来）は他の描画と共通なので、
    問題図と解答図の座標系は必ず一致する。折れ点は塗り●で示す（色に情報を載せない）。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts

    if draw_polyline:
        pts = [_parse_point(s) for s in params["poly_pts"]]
        px = [(sc.to_px_x(float(x)), sc.to_px_y(float(y))) for x, y in pts]
        joined = " ".join(f"{a:.2f},{b:.2f}" for a, b in px)
        parts.append(
            f'<polyline points="{joined}" fill="none" '
            f'stroke="#000000" stroke-width="2.5"/>'
        )
        for a, b in px:
            parts.append(f'<circle cx="{a:.2f}" cy="{b:.2f}" r="4" fill="#000000"/>')

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


def _draw_polyline_from_plan(mr: "MR") -> bool:
    """visual_plan.elements に "polyline" 要素が宣言されていれば折れ線を描く。"""
    if mr.visual_plan is None:
        return True
    return any(e.kind == "polyline" for e in mr.visual_plan.elements)


def render_polyline_graph(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。visual_plan の polyline 要素の有無で折れ線描画を切替える。"""
    return render_polyline_svg(mr.params, draw_polyline=_draw_polyline_from_plan(mr))


def render_polyline_solution_svg(params: dict[str, Any]) -> str:
    """折れ線の模範解答図（g3_l38 Lv3）。GraphAnswer.solution_svg_ref に格納する。"""
    return render_polyline_svg(params, draw_polyline=True)


def render_curve_pair_solution_svg(params: dict[str, Any]) -> str:
    """2本の放物線を同じ座標軸にかいた模範解答図（g3_l33 Lv2）。

    params に "coeff"（1本目・実線）と "coeff2"（2本目・破線）を持つ。
    """
    return render_curve_svg(params, draw_curve=True, second_coeff=params["coeff2"])


def render_curve_domain_solution_svg(params: dict[str, Any]) -> str:
    """変域に対応する部分を太くなぞった模範解答図（g3_l34 Lv2）。

    params に "arc_x_lo"/"arc_x_hi"（変域の両端）を持つ。
    """
    return render_curve_svg(
        params, draw_curve=True, arc_range=(params["arc_x_lo"], params["arc_x_hi"])
    )


def render_curve_line_solution_svg(params: dict[str, Any]) -> str:
    """放物線と直線をかき、囲まれた部分を斜線で示した模範解答図（g3_l37 Lv2）。

    params に "line_m"/"line_b"（直線 y=mx+b）と "hatch_x_lo"/"hatch_x_hi"（交点の
    x 座標）を持つ。
    """
    return render_curve_svg(
        params,
        draw_curve=True,
        line=(params["line_m"], params["line_b"]),
        hatch_between=True,
    )


def _draw_curve_from_plan(mr: "MR") -> bool:
    """visual_plan.elements に "curve" 要素が宣言されていれば曲線を描く。

    `_draw_line_from_plan` と同じ規約（「かく」セルの問題図は elements=[grid, axis]
    のみにして空の方眼を出す）。
    """
    if mr.visual_plan is None:
        return True
    return any(e.kind == "curve" for e in mr.visual_plan.elements)


def render_curve_graph(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。visual_plan の curve 要素の有無で曲線描画を切替える。

    `params["line"]` があれば直線も重ねる（入試の「放物線と直線が2点で交わる」）。
    """
    ln = mr.params.get("line")
    return render_curve_svg(
        mr.params, draw_curve=_draw_curve_from_plan(mr),
        line=(ln[0], ln[1]) if ln else None,
    )


def render_curve_solution_svg(params: dict[str, Any]) -> str:
    """「かく」セルの模範解答図（曲線つき）。GraphAnswer.solution_svg_ref に格納する。"""
    return render_curve_svg(params, draw_curve=True)


# ---------------------------------------------------------------------------
# 座標平面上の2点と、その2点を斜辺とする直角三角形（g3_l54.graph_table Lv2）
#
# 問題図は「方眼＋与えられた2点」まで（直角三角形は生徒がかき込む答えなので描かない）。
# 解答図で三角形と直角の記号を足す。点名（A・B）は図に書く——問題文がその名前で
# 点を呼ぶので、名前が図に無いとどちらがどちらか決まらない。
# ---------------------------------------------------------------------------
def render_coordinate_points_svg(params: dict[str, Any], *, draw_triangle: bool) -> str:
    """方眼に2点を打ち、必要なら斜辺 AB の直角三角形を描く。

    params: pts（["(x, y)", ...]・描画範囲もここから決まる）／point_labels（点名）。
    直角の頂点は「一方の x 座標ともう一方の y 座標」の点で、recipe が
    `right_angle_pt` として渡す（描画側で組み立て直さない＝対応表を2か所に持たない）。
    """
    sc = _grid_scaffold(params)
    parts = sc.parts

    pts = [_parse_point(s) for s in params["pts"]]
    labels = [str(v) for v in params.get("point_labels", [])]
    # 名前を逃がす向きの基準。三角形を描くならその重心（直角の頂点を含む）。
    shape_px: list[tuple[float, float]] = []

    if draw_triangle:
        cx, cy = _parse_point(str(params["right_angle_pt"]))
        (ax, ay), (bx, by) = pts[0], pts[1]
        tri = [(ax, ay), (cx, cy), (bx, by)]
        px_tri = [(sc.to_px_x(float(x)), sc.to_px_y(float(y))) for x, y in tri]
        shape_px = px_tri
        joined = " ".join(f"{x:.2f},{y:.2f}" for x, y in px_tri)
        parts.append(
            f'<polygon points="{joined}" fill="none" stroke="#000000" stroke-width="2.5"/>'
        )
        # 直角の記号（頂点 C の内側に小さな正方形）。向きは2辺の伸びる向きで決める。
        pcx, pcy = px_tri[1]
        sx = 1.0 if float(ax) > float(cx) or float(bx) > float(cx) else -1.0
        sy = 1.0 if float(ay) > float(cy) or float(by) > float(cy) else -1.0
        m = 10.0
        parts.append(
            f'<polyline points="{pcx + sx * m:.2f},{pcy:.2f} '
            f'{pcx + sx * m:.2f},{pcy - sy * m:.2f} {pcx:.2f},{pcy - sy * m:.2f}" '
            f'fill="none" stroke="#000000" stroke-width="1.2"/>'
        )

    # --- 与えられた2点（黒丸＋点名。名前は図の重心と反対側へ逃がす） ---
    px_pts = [(sc.to_px_x(float(x)), sc.to_px_y(float(y))) for x, y in pts]
    ccx, ccy = centroid(shape_px or px_pts)
    # 点が軸の上にあると、点名が目盛の数字とぴったり重なる。目盛の位置は避ける。
    blocked = grid_tick_anchors(sc)
    for i, (px, py) in enumerate(px_pts):
        parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="#000000"/>')
        if i < len(labels):
            dist = 13.0
            for _ in range(4):
                lx, ly, anchor = outward(px, py, ccx, ccy, dist=dist)
                if all(abs(lx - qx) > 16.0 or abs(ly - qy) > 13.0 for qx, qy in blocked):
                    break
                dist += 13.0
            blocked.append((lx, ly))
            parts.append(haloed_text(lx, ly, labels[i], size=13, anchor=anchor))

    parts.extend(_grid_ticks(sc))
    parts.append("</svg>")
    return "".join(parts)


def render_coordinate_points_graph(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。方眼と与えられた2点だけを描く（三角形は答えなので描かない）。"""
    return render_coordinate_points_svg(mr.params, draw_triangle=False)


def render_coordinate_triangle_solution_svg(params: dict[str, Any]) -> str:
    """模範解答図。2点を斜辺とする直角三角形と直角の記号を足す。"""
    return render_coordinate_points_svg(params, draw_triangle=True)


register_visual("math.linear_graph")(render_linear_graph)
register_visual("math.curve_graph")(render_curve_graph)
register_visual("math.polyline_graph")(render_polyline_graph)
register_visual("math.line_polygon_graph")(render_line_polygon_graph)
register_visual("math.coordinate_points_graph")(render_coordinate_points_graph)


__all__ = [
    "render_linear_graph",
    "render_grid_svg",
    "render_line_solution_svg",
    "render_special_lines_solution_svg",
    "render_segment_solution_svg",
    "render_curve_graph",
    "render_curve_svg",
    "render_curve_solution_svg",
    "render_curve_pair_solution_svg",
    "render_curve_domain_solution_svg",
    "render_curve_line_solution_svg",
    "render_polyline_graph",
    "render_polyline_svg",
    "render_polyline_solution_svg",
    "render_coordinate_points_graph",
    "render_coordinate_points_svg",
    "render_coordinate_triangle_solution_svg",
    "compute_grid_bounds",
    "compute_grid_bounds_from_params",
    "compute_grid_spec_from_params",
    "tick_labels",
    "tick_labels_from_params",
]
