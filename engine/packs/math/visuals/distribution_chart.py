"""分布のグラフ（ヒストグラム・度数折れ線・累積折れ線・箱ひげ図）の SVG レンダラ。

`graph.py`（座標平面）と同じ方針の自己完結 SVG 生成。matplotlib に依存しない。
モノクロ印刷可（色に情報を載せない。塗り・線種・太さだけで区別する）。

`<text>` 要素は**軸目盛の数値のみ**。呼び出し側（recipe）はこれらの目盛文字列を
`visual_plan.labels` に含めることで G-Q5v（SVG 内テキスト ⊆ whitelist）を満たす。
階級や5数要約の**値そのものを図中に書かない**ので、「読む」セルで答えを先出しする
ことがない（読む対象は目盛と図形の位置関係から読み取らせる）。

登録:
  - `math.frequency_chart` … 度数分布のグラフ（ヒストグラム／度数折れ線／累積折れ線）
  - `math.box_plot`        … 箱ひげ図（1本または2本の比較）

座標平面（graph.py）と土台を共有しないのは、こちらが「階級 × 度数」という
別の座標系（x が階級境界・y が度数）で、目盛の取り方も軸ラベルの位置も違うため。
見た目（サイズ・余白・線の太さ・色）は graph.py に揃えてある。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

import sympy

from engine.core.registry import register_visual

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext


# ---------------------------------------------------------------------------
# 描画パラメータ（固定・決定論）— graph.py と同じ見た目に揃える
# ---------------------------------------------------------------------------
_SVG_W = 460  # px（階級ラベルが横に並ぶので座標平面より横長にする）
_SVG_H = 400
_MARGIN_L = 40  # 左（度数の目盛ラベル）
_MARGIN_R = 20
_MARGIN_T = 20
_MARGIN_B = 34  # 下（階級境界の目盛ラベル）

_GRID_COLOR = "#bbbbbb"
_INK = "#000000"
_BAR_FILL = "#ffffff"  # 棒は白抜き＋黒枠（塗りつぶすと重なりが読めない）

_MAX_Y_TICKS = 10
_NICE_MANTISSAS = (1, 2, 5)

# 2本目の系列は破線で描く（色ではなく線種で区別＝モノクロ印刷可）
_DASH_B = "6 3"


def _nice_step(v_max: int) -> int:
    """0〜v_max を `_MAX_Y_TICKS` 本以内で覆う切りのよい目盛間隔（1/2/5×10ⁿ）。"""
    if v_max <= _MAX_Y_TICKS:
        return 1
    scale = 1
    for _ in range(10):
        for mantissa in _NICE_MANTISSAS:
            step = mantissa * scale
            if v_max <= _MAX_Y_TICKS * step:
                return step
        scale *= 10
    raise ValueError(f"目盛間隔を決められない大きさ: {v_max}")  # pragma: no cover


def _fmt(v: sympy.Expr | int | float) -> str:
    """目盛ラベルの表示形（整数はそのまま・小数は末尾の 0 を落とす）。"""
    e = sympy.nsimplify(sympy.sympify(v))
    if e == int(e):
        return str(int(e))
    return str(sympy.sstr(sympy.Float(float(e))).rstrip("0").rstrip("."))


def _scale(lo: float, hi: float, out_lo: float, out_hi: float) -> Callable[[float], float]:
    span = hi - lo or 1.0

    def f(v: float) -> float:
        return out_lo + (v - lo) * (out_hi - out_lo) / span

    return f


# ---------------------------------------------------------------------------
# 度数分布のグラフ（ヒストグラム／度数折れ線／累積折れ線）
# ---------------------------------------------------------------------------
def _y_axis_max(values: list[float]) -> tuple[int, int]:
    """度数軸の上限と目盛間隔。棒が天井に貼りつかないよう1目盛の余白を取る。"""
    v_max = max([1.0, *values])
    step = _nice_step(int(v_max) + 1)
    hi = (int(v_max) // step + 1) * step
    return hi, step


def _series_values(params: dict[str, Any], key: str) -> list[float]:
    raw = params.get(key)
    if not raw:
        return []
    return [float(sympy.nsimplify(sympy.sympify(v))) for v in raw]


def _cumulative(values: list[float]) -> list[float]:
    out: list[float] = []
    total = 0.0
    for v in values:
        total += v
        out.append(total)
    return out


def render_frequency_chart_svg(params: dict[str, Any], *, draw: bool) -> str:
    """度数分布のグラフ。

    params:
      class_lo     : 最初の階級の下限
      class_width  : 階級の幅
      frequencies  : 各階級の度数（または相対度数）のリスト
      frequencies_b: 比較する2本目の系列（任意・破線で重ねる）
      chart_kind   : "histogram" | "polygon" | "cumulative"

    draw=False は「かく」セルの問題図＝**目盛だけの空のグラフ用紙**（生徒が描き込む）。
    土台と目盛は draw の値によらず同じなので、問題図と解答図の座標系は必ず一致する。
    """
    lo = float(sympy.nsimplify(sympy.sympify(params["class_lo"])))
    width = float(sympy.nsimplify(sympy.sympify(params["class_width"])))
    freqs = _series_values(params, "frequencies")
    freqs_b = _series_values(params, "frequencies_b")
    kind = str(params.get("chart_kind", "histogram"))
    n = len(freqs)
    if n == 0:
        raise ValueError("frequencies が空（度数分布のグラフは1階級以上必要）")
    if freqs_b and len(freqs_b) != n:
        raise ValueError("frequencies_b の階級数が frequencies と違う")

    plotted = _cumulative(freqs) if kind == "cumulative" else freqs
    plotted_b = (_cumulative(freqs_b) if kind == "cumulative" else freqs_b) if freqs_b else []
    y_hi, y_step = _y_axis_max(plotted + plotted_b)

    x_lo, x_hi = lo, lo + width * n
    px = _scale(x_lo, x_hi, _MARGIN_L, _SVG_W - _MARGIN_R)
    py = _scale(0, y_hi, _SVG_H - _MARGIN_B, _MARGIN_T)  # 上下反転

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, Noto Sans JP, Yu Gothic, Meiryo, sans-serif">',
        f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff" stroke="none"/>',
    ]

    # --- 横の補助線（度数の目盛） ---
    for i in range(0, y_hi + 1, y_step):
        y = py(i)
        parts.append(
            f'<line x1="{_MARGIN_L:.2f}" y1="{y:.2f}" x2="{_SVG_W - _MARGIN_R:.2f}" y2="{y:.2f}" '
            f'stroke="{_GRID_COLOR}" stroke-width="0.5"/>'
        )

    # --- 軸 ---
    y0, x0 = py(0), px(x_lo)
    parts.append(
        f'<line x1="{_MARGIN_L:.2f}" y1="{y0:.2f}" x2="{_SVG_W - _MARGIN_R:.2f}" y2="{y0:.2f}" '
        f'stroke="{_INK}" stroke-width="1.5"/>'
    )
    parts.append(
        f'<line x1="{x0:.2f}" y1="{_MARGIN_T:.2f}" x2="{x0:.2f}" y2="{y0:.2f}" '
        f'stroke="{_INK}" stroke-width="1.5"/>'
    )

    if draw:
        parts.extend(_frequency_marks(kind, plotted, lo, width, px, py, dashed=False))
        if plotted_b:
            parts.extend(_frequency_marks(kind, plotted_b, lo, width, px, py, dashed=True))

    parts.extend(_frequency_ticks(lo, width, n, y_hi, y_step, px, py))
    parts.append("</svg>")
    return "".join(parts)


def _frequency_marks(
    kind: str,
    values: list[float],
    lo: float,
    width: float,
    px: Callable[[float], float],
    py: Callable[[float], float],
    *,
    dashed: bool,
) -> list[str]:
    """系列1本ぶんの描画要素。"""
    dash = f' stroke-dasharray="{_DASH_B}"' if dashed else ""
    out: list[str] = []

    if kind == "histogram":
        # 棒は隙間なく隣接させる（ヒストグラムの約束。棒グラフと区別がつく）。
        for i, v in enumerate(values):
            left, right = px(lo + width * i), px(lo + width * (i + 1))
            top, base = py(v), py(0)
            out.append(
                f'<rect x="{left:.2f}" y="{top:.2f}" width="{right - left:.2f}" '
                f'height="{base - top:.2f}" fill="{_BAR_FILL}" '
                f'stroke="{_INK}" stroke-width="1.5"{dash}/>'
            )
        return out

    if kind == "polygon":
        # 度数折れ線: 各階級の**中央の値**を結び、両端は度数 0 の階級まで下ろす。
        pts = [(px(lo - width / 2), py(0))]
        pts += [(px(lo + width * (i + 0.5)), py(v)) for i, v in enumerate(values)]
        pts.append((px(lo + width * (len(values) + 0.5)), py(0)))
    elif kind == "cumulative":
        # 累積の折れ線: 各階級の**上限**にその階級までの累積を打ち、起点は下限で 0。
        pts = [(px(lo), py(0))]
        pts += [(px(lo + width * (i + 1)), py(v)) for i, v in enumerate(values)]
    else:
        raise ValueError(f"未知の chart_kind: {kind!r}（histogram / polygon / cumulative）")

    joined = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    out.append(
        f'<polyline points="{joined}" fill="none" '
        f'stroke="{_INK}" stroke-width="2.5"{dash}/>'
    )
    for x, y in pts:
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{_INK}"/>')
    return out


def _frequency_ticks(
    lo: float,
    width: float,
    n: int,
    y_hi: int,
    y_step: int,
    px: Callable[[float], float],
    py: Callable[[float], float],
) -> list[str]:
    """軸目盛の数値ラベル（<text> はこれのみ）。"""
    out: list[str] = []
    y0 = py(0)
    for i in range(n + 1):
        v = lo + width * i
        x = px(v)
        out.append(
            f'<text x="{x:.2f}" y="{y0 + 14:.2f}" font-size="10" '
            f'text-anchor="middle" fill="{_INK}">{_fmt(v)}</text>'
        )
    for i in range(0, y_hi + 1, y_step):
        out.append(
            f'<text x="{px(lo) - 6:.2f}" y="{py(i) + 3:.2f}" font-size="10" '
            f'text-anchor="end" fill="{_INK}">{_fmt(i)}</text>'
        )
    return out


def frequency_chart_labels(params: dict[str, Any]) -> list[str]:
    """実描画される軸目盛の数値ラベル一覧（visual_plan.labels 用）。

    recipe が MR を組み立てる前（params だけの時点）から呼べるよう dict を受け取る。
    実描画と同じ計算を通すので、labels と SVG 内 <text> は機械的に一致する。
    """
    lo = float(sympy.nsimplify(sympy.sympify(params["class_lo"])))
    width = float(sympy.nsimplify(sympy.sympify(params["class_width"])))
    freqs = _series_values(params, "frequencies")
    freqs_b = _series_values(params, "frequencies_b")
    kind = str(params.get("chart_kind", "histogram"))
    plotted = _cumulative(freqs) if kind == "cumulative" else freqs
    plotted_b = (_cumulative(freqs_b) if kind == "cumulative" else freqs_b) if freqs_b else []
    y_hi, y_step = _y_axis_max(plotted + plotted_b)
    labels = [_fmt(lo + width * i) for i in range(len(freqs) + 1)]
    labels += [_fmt(i) for i in range(0, y_hi + 1, y_step)]
    return labels


def _draw_from_plan(mr: "MR", kind: str) -> bool:
    """visual_plan.elements に該当要素があれば描く（無ければ空のグラフ用紙）。

    `graph.py` の `_draw_line_from_plan` と同じ規約。
    """
    if mr.visual_plan is None:
        return True
    return any(e.kind == kind for e in mr.visual_plan.elements)


def render_frequency_chart(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。"""
    return render_frequency_chart_svg(mr.params, draw=_draw_from_plan(mr, "distribution"))


def render_frequency_chart_solution_svg(params: dict[str, Any]) -> str:
    """「かく」セルの模範解答図。"""
    return render_frequency_chart_svg(params, draw=True)


# ---------------------------------------------------------------------------
# 箱ひげ図
# ---------------------------------------------------------------------------
_BOX_H = 42  # 箱の高さ px
_BOX_GAP = 30  # 2本並べるときの間隔 px


def _five(params: dict[str, Any], key: str) -> list[float]:
    raw = params.get(key)
    if not raw:
        return []
    vals = [float(sympy.nsimplify(sympy.sympify(v))) for v in raw]
    if len(vals) != 5:
        raise ValueError(f"{key} は [最小値, Q1, 中央値, Q3, 最大値] の5つ")
    if any(vals[i] > vals[i + 1] for i in range(4)):
        raise ValueError(f"{key} が単調非減少でない: {vals}")
    return vals


def render_box_plot_svg(params: dict[str, Any], *, draw: bool) -> str:
    """箱ひげ図。

    params:
      five_number   : [最小値, Q1, 中央値, Q3, 最大値]
      five_number_b : 比較する2本目（任意）
      axis_lo/axis_hi/axis_step : 目盛の範囲と間隔

    draw=False は「かく」セルの問題図＝**数直線だけ**（生徒が箱ひげを描き込む）。
    """
    a = _five(params, "five_number")
    b = _five(params, "five_number_b")
    if not a:
        raise ValueError("five_number が無い")

    axis_lo = float(sympy.nsimplify(sympy.sympify(params["axis_lo"])))
    axis_hi = float(sympy.nsimplify(sympy.sympify(params["axis_hi"])))
    axis_step = float(sympy.nsimplify(sympy.sympify(params["axis_step"])))
    if axis_hi <= axis_lo or axis_step <= 0:
        raise ValueError("箱ひげ図の軸の指定が不正")

    px = _scale(axis_lo, axis_hi, _MARGIN_L, _SVG_W - _MARGIN_R)
    series = [a] + ([b] if b else [])
    y_axis = _SVG_H - _MARGIN_B
    # 箱は数直線の上に、上から順に積む
    tops = [y_axis - 40 - (len(series) - 1 - i) * (_BOX_H + _BOX_GAP) - _BOX_H for i in range(len(series))]

    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_SVG_W} {_SVG_H}" '
        f'width="{_SVG_W}" height="{_SVG_H}" font-family="Hiragino Sans, Hiragino Kaku Gothic ProN, Noto Sans JP, Yu Gothic, Meiryo, sans-serif">',
        f'<rect x="0" y="0" width="{_SVG_W}" height="{_SVG_H}" fill="#ffffff" stroke="none"/>',
    ]

    # --- 縦の補助線（数直線の目盛） ---
    ticks = _axis_ticks(axis_lo, axis_hi, axis_step)
    for v in ticks:
        x = px(v)
        parts.append(
            f'<line x1="{x:.2f}" y1="{_MARGIN_T:.2f}" x2="{x:.2f}" y2="{y_axis:.2f}" '
            f'stroke="{_GRID_COLOR}" stroke-width="0.5"/>'
        )

    # --- 数直線 ---
    parts.append(
        f'<line x1="{_MARGIN_L:.2f}" y1="{y_axis:.2f}" x2="{_SVG_W - _MARGIN_R:.2f}" '
        f'y2="{y_axis:.2f}" stroke="{_INK}" stroke-width="1.5"/>'
    )

    if draw:
        for i, s in enumerate(series):
            parts.extend(_box_marks(s, tops[i], px, dashed=(i == 1)))

    for v in ticks:
        parts.append(
            f'<text x="{px(v):.2f}" y="{y_axis + 14:.2f}" font-size="10" '
            f'text-anchor="middle" fill="{_INK}">{_fmt(v)}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def _axis_ticks(lo: float, hi: float, step: float) -> list[float]:
    out: list[float] = []
    v = lo
    # 浮動小数の累積誤差を避けるため整数倍で刻む
    k = 0
    while v <= hi + 1e-9:
        out.append(v)
        k += 1
        v = lo + step * k
    return out


def _box_marks(
    five: list[float], top: float, px: Callable[[float], float], *, dashed: bool
) -> list[str]:
    """箱ひげ1本ぶん（ひげ・箱・中央値の線）。"""
    lo, q1, med, q3, hi = five
    dash = f' stroke-dasharray="{_DASH_B}"' if dashed else ""
    mid = top + _BOX_H / 2
    out: list[str] = []

    # ひげ（最小値〜Q1、Q3〜最大値）と端の縦棒
    out.append(
        f'<line x1="{px(lo):.2f}" y1="{mid:.2f}" x2="{px(q1):.2f}" y2="{mid:.2f}" '
        f'stroke="{_INK}" stroke-width="1.5"{dash}/>'
    )
    out.append(
        f'<line x1="{px(q3):.2f}" y1="{mid:.2f}" x2="{px(hi):.2f}" y2="{mid:.2f}" '
        f'stroke="{_INK}" stroke-width="1.5"{dash}/>'
    )
    for v in (lo, hi):
        out.append(
            f'<line x1="{px(v):.2f}" y1="{top + 8:.2f}" x2="{px(v):.2f}" '
            f'y2="{top + _BOX_H - 8:.2f}" stroke="{_INK}" stroke-width="1.5"/>'
        )

    # 箱（白抜き＋黒枠。塗りつぶすと中央値の線が読めない）
    out.append(
        f'<rect x="{px(q1):.2f}" y="{top:.2f}" width="{px(q3) - px(q1):.2f}" '
        f'height="{_BOX_H:.2f}" fill="{_BAR_FILL}" stroke="{_INK}" stroke-width="1.5"{dash}/>'
    )
    # 中央値（箱の中の太い縦線）
    out.append(
        f'<line x1="{px(med):.2f}" y1="{top:.2f}" x2="{px(med):.2f}" '
        f'y2="{top + _BOX_H:.2f}" stroke="{_INK}" stroke-width="2.5"/>'
    )
    return out


def box_plot_labels(params: dict[str, Any]) -> list[str]:
    """箱ひげ図の軸目盛ラベル一覧（visual_plan.labels 用）。"""
    axis_lo = float(sympy.nsimplify(sympy.sympify(params["axis_lo"])))
    axis_hi = float(sympy.nsimplify(sympy.sympify(params["axis_hi"])))
    axis_step = float(sympy.nsimplify(sympy.sympify(params["axis_step"])))
    return [_fmt(v) for v in _axis_ticks(axis_lo, axis_hi, axis_step)]


def render_box_plot(mr: "MR", ctx: "CellContext") -> str:
    """登録 visual（問題図）。"""
    return render_box_plot_svg(mr.params, draw=_draw_from_plan(mr, "box_plot"))


def render_box_plot_solution_svg(params: dict[str, Any]) -> str:
    """「かく」セルの模範解答図。"""
    return render_box_plot_svg(params, draw=True)


register_visual("math.frequency_chart")(render_frequency_chart)
register_visual("math.box_plot")(render_box_plot)


__all__ = [
    "render_frequency_chart",
    "render_frequency_chart_svg",
    "render_frequency_chart_solution_svg",
    "frequency_chart_labels",
    "render_box_plot",
    "render_box_plot_svg",
    "render_box_plot_solution_svg",
    "box_plot_labels",
]
