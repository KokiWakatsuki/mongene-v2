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
        "expression", "equation", "input_value", "equation_a", "equation_b",
    })
    assert f.asked_vocab == frozenset({"value", "simplified_expr", "solution", "coordinate"})
    assert f.visual == "none"


def test_knowledge_vocab_and_visual():
    f = REGISTRY.frame("knowledge")
    assert f.given_vocab == frozenset({"statement", "term_context"})
    assert f.asked_vocab == frozenset({"term", "true_false", "choice"})
    assert f.visual == "none"


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
        "line_a", "line_b",
    })
    assert f.asked_vocab == frozenset({
        "draw_graph", "read_point", "read_intersection", "read_table", "complete_table",
        "read_slope_intercept",
    })
    assert f.visual == "required"


def test_word_problem_vocab_and_visual():
    f = REGISTRY.frame("word_problem")
    assert f.given_vocab == frozenset({"scenario", "quantities"})
    assert f.asked_vocab == frozenset({"formulation", "value"})
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
