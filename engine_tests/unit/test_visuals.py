"""Task8: 座標平面グラフ SVG レンダラ（`engine/packs/math/visuals/graph.py`）の unit テスト。

検査項目（設計 §6.4・§8.2 G-Q5v）:
- SVG 文字列を返す・`<svg` で始まる。
- svg 内 `<text>` は全て `tick_labels_from_params`（＝visual_plan.labels）に含まれる（whitelist 整合）。
- 答え座標の点マーカー/座標ラベルを描かない（`<text>` に答え座標が現れない）。
- モノクロ印刷可（彩度のある色で情報を区別していない＝黒・グレースケール・none のみ）。
- G-Q5v を「わざと壊す」: labels に無い text を含む svg／禁止 kind を含む visual_plan で fail。
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
from engine.packs.math.visuals.graph import render_linear_graph, tick_labels_from_params


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
