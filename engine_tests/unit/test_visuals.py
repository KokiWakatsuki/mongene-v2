"""Task8: 座標平面グラフ SVG レンダラ（`engine/packs/math/visuals/graph.py`）の unit テスト。

検査項目（設計 §6.4・§8.2 G-Q5v）:
- SVG 文字列を返す・`<svg` で始まる。
- svg 内 `<text>` は全て `tick_labels_from_params`（＝visual_plan.labels）に含まれる（whitelist 整合）。
- 答え座標の点マーカー/座標ラベルを描かない（`<text>` に答え座標が現れない）。
- モノクロ印刷可（彩度のある色で情報を区別していない＝黒・グレースケール・none のみ）。
- G-Q5v を「わざと壊す」: labels に無い text を含む svg／禁止 kind を含む visual_plan で fail。
- 量-量グラフ（grid_mode="quantity"）: 第1象限のみ・軸ごとに独立な粗い目盛・既定は従来通り。
"""
from __future__ import annotations

import re
from typing import Any

from engine.core.contracts import (
    MR,
    Provenance,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import _Registry
from engine.core.verify.gates import VisualStageInput
from engine.core.verify.quality_gates import install_quality_gates
from engine.packs.math.visuals.distribution_chart import (
    box_plot_labels,
    frequency_chart_labels,
    render_box_plot_svg,
    render_frequency_chart_svg,
)
from engine.packs.math.visuals.graph import (
    compute_grid_spec_from_params,
    render_linear_graph,
    render_curve_svg,
    render_segment_solution_svg,
    tick_labels_from_params,
)


def _mr(params: dict[str, Any], *, visual_plan: VisualPlan | None = None) -> MR:
    return MR(
        signature="graph_read_two_lattice_points",
        family="math.g2_l25.graph_table",
        level=2,
        purpose="base",
        seed=1,
        params=params,
        given={},
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked="read_point",
                answer=SymbolicAnswer(srepr="Tuple(Tuple(Integer(0), Integer(3)), Tuple(Integer(3), Integer(6)))", display="(0, 3), (3, 6)"),
                steps=[],
                concept_tags=["graph.read_lattice_points"],
                cause_tags=[],
            )
        ],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="math.graph_read_two_points"),
    )


_PARAMS = {"a": "1", "b": "3", "pts": ["(0, 3)", "(3, 6)"]}


def _svg_texts(svg: str) -> list[str]:
    return [t.strip() for t in re.findall(r"<text[^>]*>([^<]*)</text>", svg)]


def test_render_returns_svg() -> None:
    svg = render_linear_graph(_mr(_PARAMS), ctx=None)  # type: ignore[arg-type]
    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_svg_texts_are_subset_of_tick_labels() -> None:
    svg = render_linear_graph(_mr(_PARAMS), ctx=None)  # type: ignore[arg-type]
    labels = set(tick_labels_from_params(_PARAMS))
    for t in _svg_texts(svg):
        assert t in labels, f"svg text {t!r} が tick_labels({sorted(labels)}) に無い"


def test_answer_point_not_drawn_as_text() -> None:
    """答えの点そのもの（例 "(3, 6)" や座標ペア）を text として描いていない。"""
    svg = render_linear_graph(_mr(_PARAMS), ctx=None)  # type: ignore[arg-type]
    assert "(3, 6)" not in svg
    assert "(0, 3)" not in svg
    # <text> は軸目盛の単独数値のみ（カンマを含む座標表記が無い）
    for t in _svg_texts(svg):
        assert "," not in t


def test_monochrome_only() -> None:
    """彩度のある色（r,g,b が不揃いな #rrggbb や red/blue 等）で区別していない。"""
    svg = render_linear_graph(_mr(_PARAMS), ctx=None)  # type: ignore[arg-type]
    colors = re.findall(r'(?:fill|stroke)="([^"]+)"', svg)
    for c in colors:
        if c == "none":
            continue
        if c.startswith("#") and len(c) == 7:
            r, g, b = c[1:3], c[3:5], c[5:7]
            assert r == g == b, f"グレースケールでない色: {c}"
        else:
            assert c.lower() in ("black", "white", "none", "gray", "grey"), f"彩度のある色名: {c}"


# ---------------------------------------------------------------------------
# 量-量グラフ（grid_mode="quantity"・C3 g3_l31.graph_table で開通）
# ---------------------------------------------------------------------------
_QUANTITY_PARAMS = {"a": "54", "b": "0", "pts": ["(0, 0)", "(3, 162)"], "grid_mode": "quantity"}


def test_quantity_grid_is_first_quadrant_with_coarse_y_step() -> None:
    """単位の違う2量のグラフ: 第1象限のみ・y は粗い目盛（1刻みなら方眼が潰れる）。"""
    spec = compute_grid_spec_from_params(_QUANTITY_PARAMS)
    assert (spec.x_lo, spec.y_lo) == (0, 0)
    assert spec.x_step == 1  # x（時間 3 秒）は 1 刻みで足りる
    assert spec.y_step == 20  # y（面積 162）は 20 刻み＝目盛 10 本
    # 両軸とも値の 1 目盛先まで（点が枠に貼りつかない）。
    assert spec.x_hi == 4
    assert spec.y_hi == 180
    # 目盛の本数は上限以内（軸ラベルが潰れない）。
    assert len(range(spec.x_lo, spec.x_hi + 1, spec.x_step)) <= 13
    assert len(range(spec.y_lo, spec.y_hi + 1, spec.y_step)) <= 13


def test_quantity_grid_svg_texts_are_subset_of_tick_labels() -> None:
    svg = render_segment_solution_svg(
        {**_QUANTITY_PARAMS, "seg_x_lo": "0", "seg_x_hi": "3", "closed_lo": True, "closed_hi": True}
    )
    labels = set(tick_labels_from_params(_QUANTITY_PARAMS))
    for t in _svg_texts(svg):
        assert t in labels, f"svg text {t!r} が tick_labels({sorted(labels)}) に無い"


def test_default_grid_mode_is_unchanged_coordinate_plane() -> None:
    """grid_mode を宣言しない既存セルは従来の座標平面（縦横等スケール・1刻み）のまま。"""
    spec = compute_grid_spec_from_params(_PARAMS)
    assert (spec.x_step, spec.y_step) == (1, 1)
    assert spec.x_lo < 0 < spec.x_hi and spec.y_lo < 0 < spec.y_hi
    # 縦横がほぼ同じ幅（共通の半幅を中点から取るため、整数丸めで最大1目盛だけずれる）
    # ＝縮尺が揃い傾きを視覚的に歪めない。
    assert abs((spec.x_hi - spec.x_lo) - (spec.y_hi - spec.y_lo)) <= 1


def test_g_q5v_fails_when_svg_text_not_in_labels() -> None:
    reg = _Registry()
    install_quality_gates(reg)
    gate = next(fn for name, fn in reg.gates("visual") if name == "G-Q5v")

    visual_plan = VisualPlan(style="grid", labels=["1", "2"], elements=[VisualElement(kind="line", attrs={})])
    mr = _mr(_PARAMS, visual_plan=visual_plan)
    svg = '<svg><text>999</text></svg>'  # 999 は labels に無い
    stage = VisualStageInput(mr=mr, svg=svg, visual_plan=visual_plan)

    ok, detail = gate(stage, _DummyCtx())  # type: ignore[arg-type]
    assert ok is False


def test_g_q5v_fails_when_forbidden_element_present() -> None:
    reg = _Registry()
    install_quality_gates(reg)
    gate = next(fn for name, fn in reg.gates("visual") if name == "G-Q5v")

    # read_point で禁止される labeled_answer_point を elements に入れる
    visual_plan = VisualPlan(
        style="grid",
        labels=[],
        elements=[VisualElement(kind="labeled_answer_point", attrs={})],
    )
    mr = _mr(_PARAMS, visual_plan=visual_plan)
    svg = "<svg></svg>"
    stage = VisualStageInput(mr=mr, svg=svg, visual_plan=visual_plan)

    ok, detail = gate(stage, _DummyCtx(forbidden=frozenset({"labeled_answer_point"})))  # type: ignore[arg-type]
    assert ok is False


# ---------------------------------------------------------------------------
# 曲線（放物線 y=ax² / 双曲線 y=a/x）— C4（比例・反比例）と C6（y=ax²）の土台
# ---------------------------------------------------------------------------
_PARABOLA_PARAMS = {"curve_kind": "parabola", "coeff": "1/2", "pts": ["(-4, 8)", "(4, 8)", "(0, 0)"]}
_HYPERBOLA_PARAMS = {"curve_kind": "hyperbola", "coeff": "12", "pts": ["(2, 6)", "(-2, -6)", "(6, 2)"]}


def test_parabola_is_one_unbroken_polyline() -> None:
    """放物線は連続なので枠内で1本に描かれる（枝に割れない）。"""
    svg = render_curve_svg(_PARABOLA_PARAMS, draw_curve=True)
    assert svg.startswith("<svg")
    assert svg.count("<polyline") == 1


def test_hyperbola_splits_into_two_branches() -> None:
    """双曲線は x=0 で不連続なので2本の枝になる。

    枝分けを場合分けで書いているのではなく、「枠外に出た区間で点列を切る」処理の
    結果として自然に2本になる。ここが崩れると原点をまたぐ直線が引かれてしまう。
    """
    svg = render_curve_svg(_HYPERBOLA_PARAMS, draw_curve=True)
    assert svg.count("<polyline") == 2


def test_curve_problem_figure_is_empty_grid() -> None:
    """「かく」セルの問題図は空の方眼＝曲線を描かない（＝答えの先出しをしない）。"""
    svg = render_curve_svg(_PARABOLA_PARAMS, draw_curve=False)
    assert "<polyline" not in svg
    # 土台（グリッド・軸・目盛）は解答図と共有される＝座標系が一致する
    assert _svg_texts(svg) == _svg_texts(render_curve_svg(_PARABOLA_PARAMS, draw_curve=True))


def test_curve_svg_texts_are_subset_of_tick_labels() -> None:
    """曲線図の <text> も軸目盛のみ（G-Q5v: SVG 内テキスト ⊆ visual_plan.labels）。"""
    for params in (_PARABOLA_PARAMS, _HYPERBOLA_PARAMS):
        svg = render_curve_svg(params, draw_curve=True)
        allowed = set(tick_labels_from_params(params))
        assert set(_svg_texts(svg)) <= allowed


def test_curve_stays_inside_the_frame() -> None:
    """曲線の点はすべて描画領域の内側（枠外へはみ出さない）。"""
    svg = render_curve_svg(_HYPERBOLA_PARAMS, draw_curve=True)
    coords = re.findall(r'<polyline points="([^"]*)"', svg)
    assert coords
    for run in coords:
        for pair in run.split(" "):
            px, py = (float(v) for v in pair.split(","))
            assert 0.0 <= px <= 400.0 and 0.0 <= py <= 400.0


def test_curve_is_monochrome() -> None:
    """モノクロ印刷可（彩度のある色で情報を区別しない）。"""
    svg = render_curve_svg(_PARABOLA_PARAMS, draw_curve=True)
    colors = set(re.findall(r'(?:stroke|fill)="([^"]*)"', svg))
    assert colors <= {"none", "#000000", "#bbbbbb", "#ffffff"}


def test_curve_rendering_is_deterministic() -> None:
    """同じ params からは同じバイト列（決定論）。"""
    a = render_curve_svg(_HYPERBOLA_PARAMS, draw_curve=True)
    b = render_curve_svg(_HYPERBOLA_PARAMS, draw_curve=True)
    assert a == b


# ---------------------------------------------------------------------------
# 分布のグラフ（ヒストグラム・度数折れ線・累積折れ線・箱ひげ図）— C11 統計の土台
# ---------------------------------------------------------------------------
_HIST = {"class_lo": 10, "class_width": 5, "frequencies": [2, 5, 8, 4, 1], "chart_kind": "histogram"}
_POLY = {"class_lo": 150, "class_width": 5, "frequencies": [2, 6, 9, 3], "chart_kind": "polygon"}
_CUML = {"class_lo": 0, "class_width": 10, "frequencies": [4, 9, 7, 5], "chart_kind": "cumulative"}
_CMP = {
    "class_lo": 0, "class_width": 2,
    "frequencies": [3, 7, 10, 6, 2], "frequencies_b": [6, 9, 5, 3, 1],
    "chart_kind": "polygon",
}
_BOX = {"five_number": [4, 8, 12, 17, 24], "axis_lo": 0, "axis_hi": 30, "axis_step": 5}
_BOX2 = {**_BOX, "five_number_b": [6, 11, 15, 19, 27]}

_ALL_FREQ = (_HIST, _POLY, _CUML, _CMP)


def test_histogram_bars_are_adjacent_and_one_per_class() -> None:
    """ヒストグラムの棒は階級数だけあり、隣どうしに隙間がない（棒グラフとの違い）。"""
    svg = render_frequency_chart_svg(_HIST, draw=True)
    rects = re.findall(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)"', svg)
    bars = rects[1:]  # 先頭は背景の rect
    assert len(bars) == len(_HIST["frequencies"])
    for (x1, w1), (x2, _) in zip(bars, bars[1:]):
        assert abs((float(x1) + float(w1)) - float(x2)) < 0.01


def test_frequency_polygon_drops_to_zero_at_both_ends() -> None:
    """度数折れ線は両端で度数 0 まで下ろす（教科書の作図規約）。"""
    svg = render_frequency_chart_svg(_POLY, draw=True)
    pts = re.findall(r'<polyline points="([^"]*)"', svg)[0].split(" ")
    ys = [float(p.split(",")[1]) for p in pts]
    assert len(pts) == len(_POLY["frequencies"]) + 2  # 両端の 0 を足した数
    assert ys[0] == ys[-1] == max(ys)  # y は下向きが正＝0 が最下端


def test_cumulative_line_is_monotone_non_decreasing() -> None:
    """累積の折れ線は必ず単調非減少（描画 y は単調非増加）。"""
    svg = render_frequency_chart_svg(_CUML, draw=True)
    pts = re.findall(r'<polyline points="([^"]*)"', svg)[0].split(" ")
    ys = [float(p.split(",")[1]) for p in pts]
    assert all(a >= b for a, b in zip(ys, ys[1:]))


def test_second_series_is_distinguished_by_dash_not_color() -> None:
    """2本目の系列は破線で区別する（色に情報を載せない＝モノクロ印刷可）。"""
    svg = render_frequency_chart_svg(_CMP, draw=True)
    assert svg.count("stroke-dasharray") >= 1
    colors = set(re.findall(r'(?:stroke|fill)="([^"]*)"', svg))
    assert colors <= {"none", "#000000", "#bbbbbb", "#ffffff"}


def test_distribution_problem_figure_is_empty_chart() -> None:
    """「かく」セルの問題図は目盛だけ＝分布を描かない（答えの先出しをしない）。

    土台（軸・補助線・目盛）は解答図と共有されるので座標系は必ず一致する。
    """
    for params in _ALL_FREQ:
        empty = render_frequency_chart_svg(params, draw=False)
        assert "<polyline" not in empty
        assert empty.count("<rect") == 1  # 背景の rect だけ＝棒が無い
        assert _svg_texts(empty) == _svg_texts(render_frequency_chart_svg(params, draw=True))


def test_distribution_svg_texts_are_subset_of_labels() -> None:
    """G-Q5v: 図中の <text> は軸目盛だけで、labels 生成関数と機械的に一致する。

    階級や度数の**値そのもの**は図に書かないので、「読む」セルで答えが先出しされない。
    """
    for params in _ALL_FREQ:
        svg = render_frequency_chart_svg(params, draw=True)
        assert set(_svg_texts(svg)) <= set(frequency_chart_labels(params))
    for params in (_BOX, _BOX2):
        svg = render_box_plot_svg(params, draw=True)
        assert set(_svg_texts(svg)) <= set(box_plot_labels(params))


def test_box_plot_orders_whisker_box_median_left_to_right() -> None:
    """箱ひげ図: 最小値 ≤ Q1 ≤ 中央値 ≤ Q3 ≤ 最大値 が x 座標の順序として出る。"""
    svg = render_box_plot_svg(_BOX, draw=True)
    box = re.search(r'<rect x="([\d.]+)" y="[\d.]+" width="([\d.]+)" height="42', svg)
    assert box is not None
    left, width = float(box.group(1)), float(box.group(2))
    med = float(re.findall(r'<line x1="([\d.]+)"[^>]*stroke-width="2.5"', svg)[-1])
    assert left < med < left + width


def test_box_plot_problem_figure_is_number_line_only() -> None:
    """「かく」セルの問題図は数直線と目盛だけ（箱ひげを描かない）。"""
    empty = render_box_plot_svg(_BOX, draw=False)
    assert empty.count("<rect") == 1  # 背景のみ＝箱が無い
    assert _svg_texts(empty) == _svg_texts(render_box_plot_svg(_BOX, draw=True))


def test_box_plot_rejects_unordered_five_number() -> None:
    """5数要約が単調でない（＝データとして成立しない）入力は弾く。"""
    import pytest

    with pytest.raises(ValueError):
        render_box_plot_svg({**_BOX, "five_number": [4, 12, 8, 17, 24]}, draw=True)


def test_distribution_rendering_is_deterministic() -> None:
    """同じ params からは同じバイト列（決定論）。"""
    assert render_frequency_chart_svg(_CMP, draw=True) == render_frequency_chart_svg(_CMP, draw=True)
    assert render_box_plot_svg(_BOX2, draw=True) == render_box_plot_svg(_BOX2, draw=True)


class _DummyFrame:
    def __init__(self, forbidden: frozenset[str]) -> None:
        self.form = "graph_table"
        self.given_vocab: frozenset[str] = frozenset()
        self.asked_vocab: frozenset[str] = frozenset({"read_point"})
        self.visual = "required"
        self._forbidden = forbidden

    def check_mr(self, mr: Any) -> tuple[bool, str]:
        return True, ""

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        return self._forbidden


class _DummyCtx:
    """G-Q5v は ctx.frame.forbidden_visual_elements のみ使う。最小スタブ。"""

    def __init__(self, forbidden: frozenset[str] = frozenset()) -> None:
        self.frame = _DummyFrame(forbidden)
