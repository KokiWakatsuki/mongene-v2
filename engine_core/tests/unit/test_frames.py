"""Task5a: 数学パック frames（form の実装）の unit テスト。

各 frame が registry から引ける・given/asked 語彙・check_mr が正常系と異常系
（語彙外 asked を弾く、calculation で visual_plan 非 None を弾く）を判定することを
確認する。ダミー MR は contracts で組み立てる。
"""
from __future__ import annotations

import pytest

import engine.packs.math  # noqa: F401  (register_frame の副作用のため import)
from engine.core.contracts import (
    MR,
    Provenance,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
)
from engine.core.registry import REGISTRY


def _mk_mr(
    *,
    family: str = "math.g2_l25.find_value",
    given: dict[str, str] | None = None,
    asked: str = "expression",
    visual_plan: VisualPlan | None = None,
) -> MR:
    given = given if given is not None else {"point_a": "(1, 3)"}
    return MR(
        signature="s1",
        family=family,
        level=2,
        purpose="base",
        seed=1,
        params={"a": 3, "b": 0},
        given=given,
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked=asked,
                answer=SymbolicAnswer(srepr="x", display="y = 3x"),
                steps=[Step(op="form_expression", result_srepr="x", result_display="y=3x", narration="n")],
                concept_tags=["c1"],
                cause_tags=[],
            )
        ],
        visual_plan=visual_plan,
        provenance=Provenance(recipe="r"),
    )


# ---------------------------------------------------------------------------
# registry lookup
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "form",
    ["knowledge", "calculation", "find_value", "graph_table", "word_problem", "proof", "construction"],
)
def test_all_seven_frames_registered(form: str) -> None:
    frame = REGISTRY.frame(form)
    assert frame.form == form


# ---------------------------------------------------------------------------
# vocab tables (§6.3)
# ---------------------------------------------------------------------------
def test_calculation_vocab_and_visual():
    f = REGISTRY.frame("calculation")
    assert f.given_vocab == frozenset({
        "expression", "equation", "input_value", "equation_a", "equation_b", "candidate",
        "target_variable", "expressions", "sig_figs",
    })
    assert f.asked_vocab == frozenset({
        "value", "simplified_expr", "solution", "coordinate", "degree", "expression",
    })
    assert f.visual == "none"


def test_knowledge_vocab_and_visual():
    """★**knowledge の図は「禁止」から「あってもよい」に変えた。**

    M0 では図を禁じていたが、実物を読むと要る問いがある——「直方体PQRS-TUVWで、
    辺UVと辺SPの位置関係」は、どの辺がどこにあるかを頭の中で組み立てないと
    判断できない。`optional` にしても図が勝手に増えることはない
    （recipe が visual_plan を付けたセルにだけ出る）。
    """
    f = REGISTRY.frame("knowledge")
    assert f.given_vocab == frozenset({"statement", "term_context"})
    assert f.asked_vocab == frozenset({"term", "true_false", "choice"})
    assert f.visual == "optional"


def test_find_value_vocab_and_visual():
    f = REGISTRY.frame("find_value")
    assert f.given_vocab == frozenset({
        "point_a", "point_b", "slope", "intercept", "expression_coeffs",
        "condition", "figure_spec",
        "line_a", "line_b",  # 横展開: 2直線の交点（g2_l27）
        "expression", "x_domain", "y_range",  # 横展開: 変域とグラフの端点（g2_l23）
    })
    assert f.asked_vocab == frozenset({
        "value", "expression", "coordinate", "rate_of_change",
        "domain_range", "intersection", "area",
    })
    assert f.visual == "optional"


def test_graph_table_vocab_and_visual():
    f = REGISTRY.frame("graph_table")
    assert f.given_vocab == frozenset({
        "expression", "data_table", "situation_params", "equation", "equation2",
        "x_domain", "condition", "line_a", "line_b",
        "polygon_points", "polygon_coordinates", "move_spec",
        # g1_l32/g1_l35 Lv1: 読ませる格子点の x 座標だけを与える（答えを一意にする）。
        "x_target",
    })
    assert f.asked_vocab == frozenset({
        "draw_graph", "read_point", "read_intersection", "read_table", "complete_table",
        "read_slope_intercept", "draw_segment", "draw_transformed_polygon",
        "read_box_plot", "draw_box_plot",
        # C8/C10 空間図形: 立体を読む／見取図・投影図・展開図・断面をかく
        "read_solid", "draw_solid",
        # C13 exam_l1: 直線と図形の位置関係を図から読む
        "read_position",
        # Phase E 端物: 図の中の要素（線分・直線・辺）を記号で答える
        "read_figure_element",
        # Phase E 端物: 起こりうる場合を樹形図に整理してかく
        "draw_tree_diagram",
    })
    assert f.visual == "required"


def test_word_problem_vocab_and_visual():
    f = REGISTRY.frame("word_problem")
    assert f.given_vocab == frozenset({"scenario", "quantities"})
    # draw_graph は「関係をグラフに表してから値を求めよ」という融合の文章題
    # （g3_l38 Lv4・g2_l29 Lv4）のために足した。frame の分担は「文章題か図の問題か」
    # であって「図をかかせるか否か」ではない（frames.py の当該コメント参照）。
    assert f.asked_vocab == frozenset({"formulation", "value", "draw_graph"})
    assert f.visual == "optional"


def test_proof_vocab_declared_only():
    f = REGISTRY.frame("proof")
    assert f.given_vocab == frozenset({"premises", "conclusion"})
    assert f.asked_vocab == frozenset({"proof_text"})


def test_construction_vocab_declared_only():
    f = REGISTRY.frame("construction")
    assert f.given_vocab == frozenset({"construction_conditions"})
    assert f.asked_vocab == frozenset({"construction_steps"})
    assert f.visual == "required"


# ---------------------------------------------------------------------------
# check_mr: 正常系
# ---------------------------------------------------------------------------
def test_check_mr_ok_for_find_value():
    f = REGISTRY.frame("find_value")
    mr = _mk_mr(given={"point_a": "(1, 3)", "point_b": "(4, 12)"}, asked="expression")
    ok, detail = f.check_mr(mr)
    assert ok, detail


def test_check_mr_ok_for_calculation_no_visual():
    f = REGISTRY.frame("calculation")
    mr = _mk_mr(given={"expression": "2x + 3"}, asked="value", visual_plan=None)
    ok, detail = f.check_mr(mr)
    assert ok, detail


def test_check_mr_ok_for_graph_table_with_required_visual():
    f = REGISTRY.frame("graph_table")
    plan = VisualPlan(style="grid", labels=["A", "B"], elements=[VisualElement(kind="grid")])
    mr = _mk_mr(
        given={"expression": "y = 2x + 1"},
        asked="draw_graph",
        visual_plan=plan,
    )
    ok, detail = f.check_mr(mr)
    assert ok, detail


# ---------------------------------------------------------------------------
# check_mr: 異常系
# ---------------------------------------------------------------------------
def test_check_mr_rejects_unknown_given_key():
    f = REGISTRY.frame("find_value")
    mr = _mk_mr(given={"not_in_vocab": "xxx"}, asked="expression")
    ok, detail = f.check_mr(mr)
    assert not ok
    assert "given_vocab" in detail


def test_check_mr_rejects_unknown_asked():
    f = REGISTRY.frame("find_value")
    mr = _mk_mr(given={"point_a": "(1, 3)"}, asked="not_in_asked_vocab")
    ok, detail = f.check_mr(mr)
    assert not ok
    assert "asked_vocab" in detail


def test_check_mr_rejects_visual_plan_for_calculation():
    f = REGISTRY.frame("calculation")
    plan = VisualPlan(style="grid", labels=[], elements=[])
    mr = _mk_mr(given={"expression": "2x + 3"}, asked="value", visual_plan=plan)
    ok, detail = f.check_mr(mr)
    assert not ok
    assert "visual" in detail


def test_check_mr_rejects_missing_visual_plan_for_required():
    f = REGISTRY.frame("graph_table")
    mr = _mk_mr(given={"expression": "y = 2x + 1"}, asked="draw_graph", visual_plan=None)
    ok, detail = f.check_mr(mr)
    assert not ok
    assert "visual" in detail


def test_check_mr_rejects_empty_sub_questions():
    f = REGISTRY.frame("find_value")
    mr = _mk_mr(given={"point_a": "(1, 3)"}, asked="expression")
    mr.sub_questions = []
    ok, detail = f.check_mr(mr)
    assert not ok


# ---------------------------------------------------------------------------
# forbidden_visual_elements (§6.4)
# ---------------------------------------------------------------------------
def test_forbidden_visual_elements_find_value_intersection():
    f = REGISTRY.frame("find_value")
    forbidden = f.forbidden_visual_elements(["intersection"])
    assert forbidden == frozenset({"grid_with_both_lines"})


def test_forbidden_visual_elements_find_value_value_is_empty():
    f = REGISTRY.frame("find_value")
    forbidden = f.forbidden_visual_elements(["value"])
    assert forbidden == frozenset()


def test_forbidden_visual_elements_graph_table_read_point():
    f = REGISTRY.frame("graph_table")
    forbidden = f.forbidden_visual_elements(["read_point"])
    assert forbidden == frozenset({"labeled_answer_point"})


def test_forbidden_visual_elements_graph_table_read_slope_intercept():
    f = REGISTRY.frame("graph_table")
    forbidden = f.forbidden_visual_elements(["read_slope_intercept"])
    assert forbidden == frozenset({"labeled_answer_point"})


def test_forbidden_visual_elements_calculation_always_empty():
    f = REGISTRY.frame("calculation")
    assert f.forbidden_visual_elements(["value", "solution"]) == frozenset()


def test_forbidden_visual_elements_proof_construction_empty_for_m0():
    assert REGISTRY.frame("proof").forbidden_visual_elements(["proof_text"]) == frozenset()
    assert REGISTRY.frame("construction").forbidden_visual_elements(["construction_steps"]) == frozenset()
