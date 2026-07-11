"""Task6: 動的検証ゲート本体（`engine/core/verify/quality_gates.py`）の unit テスト。

各ゲートに「わざと壊す」fail テストと正常 pass テストを最低1本ずつ用意する。
テストは隔離のため各々 `_Registry()` を新規に作り `install_quality_gates(reg)` して
`reg.gates(stage)` から個別ゲート関数を取り出して直接呼ぶ。グローバル REGISTRY は
一切汚さない。`engine/packs/math` は import しない。
"""
from __future__ import annotations

from typing import Any

import pytest

from engine.core.contracts import (
    CellContext,
    ChoiceAnswer,
    Coordinate,
    Feature,
    GenerateOptions,
    GraphAnswer,
    MR,
    Provenance,
    Solution,
    SpecFamily,
    SpecLevel,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualElement,
    VisualPlan,
    VisualReq,
)
from engine.core.registry import _Registry
from engine.core.verify.gates import TextStageInput, VisualStageInput
from engine.core.verify.quality_gates import install_quality_gates, reset_fp_cache
from engine.core.render.t1_template import TextResult


# ---------------------------------------------------------------------------
# 共通フィクスチャ
# ---------------------------------------------------------------------------
class DummyFrame:
    """FrameProtocol を満たす最小のダミー frame。"""

    def __init__(
        self,
        *,
        check_mr_result: tuple[bool, str] = (True, ""),
        forbidden: frozenset[str] = frozenset(),
    ) -> None:
        self.form = "find_value"
        self.given_vocab: frozenset[str] = frozenset({"a"})
        self.asked_vocab: frozenset[str] = frozenset({"expression"})
        self.visual: VisualReq = "optional"
        self._check_mr_result = check_mr_result
        self._forbidden = forbidden

    def check_mr(self, mr: Any) -> tuple[bool, str]:
        return self._check_mr_result

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        return self._forbidden


def _spec_level(*, signature: str = "sig-1") -> SpecLevel:
    return SpecLevel(
        level=2,
        signature=signature,
        recipe="math.dummy_recipe",
        params={},
        given=["a"],
        asked=["expression"],
        visual="none",
        text={"tier": "T1", "template": "dummy_template_v1"},
        hints=["steps_prefix"],
        concept_tags=["c1"],
        cause_tags=[],
    )


def _spec_family() -> SpecFamily:
    return SpecFamily(
        family="math.g2_l25.find_value",
        form="find_value",
        source_desc="dummy",
        concepts_default=["c1"],
        levels={"2": _spec_level()},
        remedial_default_level=2,
    )


def _ctx(
    *,
    frame: DummyFrame | None = None,
    curriculum_view: dict[str, Any] | None = None,
    purpose: str = "base",
    spec_level: SpecLevel | None = None,
) -> CellContext:
    return CellContext(
        subject="math",
        family="math.g2_l25.find_value",
        form="find_value",
        unit="g2_l25",
        level=2,
        purpose=purpose,  # type: ignore[arg-type]
        frame=frame or DummyFrame(),
        spec_family=_spec_family(),
        spec_level=spec_level or _spec_level(),
        curriculum_view=curriculum_view if curriculum_view is not None else {
            "concept_ids": {"c1", "c2"},
            "cause_ids": {"e1"},
            "unit_concepts": {"c1"},
        },
        requested=Coordinate(subject="math", unit="g2_l25", form="find_value", level=2),
        options=GenerateOptions(),
    )


def _mr(
    *,
    signature: str = "sig-1",
    sub_questions: list[SubQuestionMR] | None = None,
    given: dict[str, str] | None = None,
    recipe: str = "math.dummy_recipe",
    visual_plan: VisualPlan | None = None,
) -> MR:
    if sub_questions is None:
        sub_questions = [
            SubQuestionMR(
                label="(1)",
                asked="expression",
                answer=SymbolicAnswer(srepr="Integer(3)", display="3"),
                steps=[
                    Step(op="add", args=["1", "2"], result_srepr="Integer(3)", result_display="3", narration="足す")
                ],
                concept_tags=["c1"],
                cause_tags=[],
            )
        ]
    return MR(
        signature=signature,
        family="math.g2_l25.find_value",
        level=2,
        purpose="base",
        seed=1,
        params={},
        given=given if given is not None else {"a": "1", "b": "2"},
        context_slots={},
        sub_questions=sub_questions,
        visual_plan=visual_plan,
        provenance=Provenance(recipe=recipe, recipe_version="v1", spec_version="v1", git_commit=""),
    )


def _installed_registry() -> _Registry:
    reg = _Registry()
    install_quality_gates(reg)
    return reg


def _gate(reg: _Registry, stage: str, name: str) -> Any:
    for gname, fn in reg.gates(stage):
        if gname == name:
            return fn
    raise KeyError(f"gate {name} not found in stage {stage}")


# ---------------------------------------------------------------------------
# install_quality_gates: 登録内容の確認
# ---------------------------------------------------------------------------
def test_install_quality_gates_registers_expected_gates():
    reg = _installed_registry()
    mr_names = [n for n, _ in reg.gates("mr")]
    text_names = [n for n, _ in reg.gates("text")]
    visual_names = [n for n, _ in reg.gates("visual")]

    assert mr_names == ["G-SIG", "G-FP", "G-Q1", "G-Q2", "G-Q7", "G-Q7r"]
    assert text_names == ["G-Q5t", "G-GND", "G-STY"]
    assert visual_names == ["G-Q5v"]


def test_install_quality_gates_is_idempotent():
    reg = _Registry()
    install_quality_gates(reg)
    install_quality_gates(reg)  # 2回目は無視される
    assert len(reg.gates("mr")) == 6


# ---------------------------------------------------------------------------
# G-SIG
# ---------------------------------------------------------------------------
def test_g_sig_pass_when_signature_matches():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-SIG")
    mr = _mr(signature="sig-1")
    ctx = _ctx(spec_level=_spec_level(signature="sig-1"))

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_sig_fail_when_signature_mismatches():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-SIG")
    mr = _mr(signature="sig-WRONG")
    ctx = _ctx(spec_level=_spec_level(signature="sig-1"))

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "signature" in detail


# ---------------------------------------------------------------------------
# G-FP
# ---------------------------------------------------------------------------
def test_g_fp_pass_when_same_signature_same_fingerprint():
    reset_fp_cache()
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-FP")
    ctx = _ctx()

    mr1 = _mr(signature="sig-fp")
    ok1, _ = gate(mr1, ctx)
    assert ok1 is True

    # 同一 signature・同一構造（fingerprint も同一）
    mr2 = _mr(signature="sig-fp")
    ok2, _ = gate(mr2, ctx)
    assert ok2 is True
    reset_fp_cache()


def test_g_fp_fail_when_same_signature_different_fingerprint():
    reset_fp_cache()
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-FP")
    ctx = _ctx()

    mr1 = _mr(signature="sig-fp2")
    ok1, _ = gate(mr1, ctx)
    assert ok1 is True

    # 同一 signature だが sub_questions の asked を変えて fingerprint を壊す
    broken_sq = [
        SubQuestionMR(
            label="(1)",
            asked="DIFFERENT_ASKED",
            answer=SymbolicAnswer(srepr="Integer(3)", display="3"),
            steps=[
                Step(op="add", args=["1", "2"], result_srepr="Integer(3)", result_display="3", narration="足す")
            ],
            concept_tags=["c1"],
            cause_tags=[],
        )
    ]
    mr2 = _mr(signature="sig-fp2", sub_questions=broken_sq)
    ok2, detail = gate(mr2, ctx)
    assert ok2 is False
    assert "fingerprint" in detail
    reset_fp_cache()


# ---------------------------------------------------------------------------
# G-Q1（double-solve）
# ---------------------------------------------------------------------------
def test_g_q1_fail_when_checker_unregistered():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q1")
    mr = _mr(recipe="math.no_checker_recipe")
    ctx = _ctx()

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "double_solve" in detail


def test_g_q1_pass_when_checker_registered_and_matches():
    reg = _Registry()

    @reg.register_checker("math.dummy_recipe.double_solve")
    def _checker(mr: MR) -> Solution:
        return Solution(answer=SymbolicAnswer(srepr="Integer(3)", display="3"), steps=[])

    install_quality_gates(reg)
    gate = _gate(reg, "mr", "G-Q1")
    mr = _mr(recipe="math.dummy_recipe")
    ctx = _ctx()

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_q1_fail_when_checker_registered_but_mismatches():
    reg = _Registry()

    @reg.register_checker("math.dummy_recipe.double_solve")
    def _checker(mr: MR) -> Solution:
        return Solution(answer=SymbolicAnswer(srepr="Integer(999)", display="999"), steps=[])

    install_quality_gates(reg)
    gate = _gate(reg, "mr", "G-Q1")
    mr = _mr(recipe="math.dummy_recipe")
    ctx = _ctx()

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "不一致" in detail


# ---------------------------------------------------------------------------
# G-Q2（frame.check_mr）
# ---------------------------------------------------------------------------
def test_g_q2_pass_when_frame_accepts():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q2")
    mr = _mr()
    ctx = _ctx(frame=DummyFrame(check_mr_result=(True, "")))

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_q2_fail_when_frame_rejects():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q2")
    mr = _mr()
    ctx = _ctx(frame=DummyFrame(check_mr_result=(False, "frame は MR を拒否した")))

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert detail == "frame は MR を拒否した"


# ---------------------------------------------------------------------------
# G-Q7（concept/cause tags 実在）
# ---------------------------------------------------------------------------
def test_g_q7_pass_when_tags_exist_in_curriculum():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7")
    mr = _mr()
    ctx = _ctx(curriculum_view={"concept_ids": {"c1"}, "cause_ids": set(), "unit_concepts": {"c1"}})

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_q7_fail_when_concept_tag_unknown():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7")
    mr = _mr()
    ctx = _ctx(curriculum_view={"concept_ids": {"OTHER"}, "cause_ids": set(), "unit_concepts": set()})

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "concept_tags" in detail


def test_g_q7_fail_when_concept_tags_empty():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7")
    sub_questions = [
        SubQuestionMR(
            label="(1)", asked="expression",
            answer=SymbolicAnswer(srepr="Integer(3)", display="3"),
            steps=[], concept_tags=[], cause_tags=[],
        )
    ]
    mr = _mr(sub_questions=sub_questions)
    ctx = _ctx()

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "concept_tags が空" in detail


# ---------------------------------------------------------------------------
# G-Q7r（remedial 被覆）
# ---------------------------------------------------------------------------
def test_g_q7r_pass_when_base_purpose_regardless_of_coverage():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7r")
    mr = _mr()  # concept_tags=["c1"]
    ctx = _ctx(purpose="base", curriculum_view={"remedial_target_concepts": ["c1", "c2"]})

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_q7r_pass_when_remedial_and_covered():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7r")
    mr = _mr()  # concept_tags=["c1"]
    ctx = _ctx(purpose="remedial", curriculum_view={"remedial_target_concepts": ["c1"]})

    ok, detail = gate(mr, ctx)
    assert ok is True


def test_g_q7r_fail_when_remedial_and_not_covered():
    reg = _installed_registry()
    gate = _gate(reg, "mr", "G-Q7r")
    mr = _mr()  # concept_tags=["c1"] のみ
    ctx = _ctx(purpose="remedial", curriculum_view={"remedial_target_concepts": ["c1", "c2"]})

    ok, detail = gate(mr, ctx)
    assert ok is False
    assert "c2" in detail


# ---------------------------------------------------------------------------
# G-Q5t（漏洩検査・text段）
# ---------------------------------------------------------------------------
def test_g_q5t_pass_when_answer_value_not_in_text():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-Q5t")
    mr = _mr(given={"a": "1", "b": "2"})  # answer=3 は given に無い
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 を足しなさい。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": "まず、足す 3"},
        hints={"(1)": ["問題文の与えられた値をもう一度確認しよう。"]},
        render_keys={"tier": "T1"},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_q5t_pass_when_answer_value_matches_given_whitelist():
    # answer=1 で given にも 1 がある場合は whitelist により許容される
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-Q5t")
    sub_questions = [
        SubQuestionMR(
            label="(1)", asked="expression",
            answer=SymbolicAnswer(srepr="Integer(1)", display="1"),
            steps=[], concept_tags=["c1"], cause_tags=[],
        )
    ]
    mr = _mr(given={"a": "1", "b": "2"}, sub_questions=sub_questions)
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 が与えられている。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": "答えは1"},
        hints={"(1)": []},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_q5t_fail_when_answer_value_leaks_into_problem_text():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-Q5t")
    mr = _mr(given={"a": "1", "b": "2"})  # answer=3、given には無い値
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 を足すと 3 になる問題です。3 を答えなさい。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": "まず、足す 3"},
        hints={"(1)": []},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "漏洩" in detail


def test_g_q5t_fail_when_answer_value_leaks_into_hints():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-Q5t")
    mr = _mr(given={"a": "1", "b": "2"})
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 を足しなさい。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": "まず、足す 3"},
        hints={"(1)": ["答えは3です"]},  # hints に漏洩
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "漏洩" in detail


# ---------------------------------------------------------------------------
# G-GND（接地）
# ---------------------------------------------------------------------------
def test_g_gnd_pass_when_given_grounded_and_prompt_count_matches():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-GND")
    mr = _mr(given={"a": "1", "b": "2"})
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 を足しなさい。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": ""},
        hints={"(1)": []},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_gnd_fail_when_given_value_missing_from_text():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-GND")
    mr = _mr(given={"a": "1", "b": "2"})
    ctx = _ctx()
    text = TextResult(
        problem_text="何かを足しなさい。",  # 1, 2 とも出現しない
        prompts={"(1)": "expression を求めなさい。"},
        explanations={"(1)": ""},
        hints={"(1)": []},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "given" in detail


def test_g_gnd_fail_when_prompt_count_mismatches():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-GND")
    mr = _mr(given={"a": "1", "b": "2"})
    ctx = _ctx()
    text = TextResult(
        problem_text="1 と 2 を足しなさい。",
        prompts={},  # 小問数不一致
        explanations={},
        hints={},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "小問数不一致" in detail


# ---------------------------------------------------------------------------
# G-STY（最小スタイル lint）
# ---------------------------------------------------------------------------
def test_g_sty_pass_for_normal_text():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-STY")
    mr = _mr()
    ctx = _ctx()
    text = TextResult(
        problem_text="1個150円のりんごを2個買う。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={},
        hints={},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_sty_fail_when_dollar_currency_used():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-STY")
    mr = _mr()
    ctx = _ctx()
    text = TextResult(
        problem_text="1個$3のりんごを2個買う。",
        prompts={"(1)": "expression を求めなさい。"},
        explanations={},
        hints={},
        render_keys={},
    )
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "通貨表記" in detail


def test_g_sty_fail_when_problem_text_empty():
    reg = _installed_registry()
    gate = _gate(reg, "text", "G-STY")
    mr = _mr()
    ctx = _ctx()
    text = TextResult(problem_text="   ", prompts={}, explanations={}, hints={}, render_keys={})
    stage_input = TextStageInput(mr=mr, text=text)

    ok, detail = gate(stage_input, ctx)
    assert ok is False


# ---------------------------------------------------------------------------
# G-Q5v（図内漏洩・visual段）
# ---------------------------------------------------------------------------
def test_g_q5v_pass_when_no_visual_plan():
    reg = _installed_registry()
    gate = _gate(reg, "visual", "G-Q5v")
    mr = _mr(visual_plan=None)
    ctx = _ctx()
    stage_input = VisualStageInput(mr=mr, svg=None, visual_plan=None)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_q5v_pass_when_svg_none_even_with_visual_plan():
    reg = _installed_registry()
    gate = _gate(reg, "visual", "G-Q5v")
    plan = VisualPlan(style="grid", labels=["A", "B"], elements=[])
    mr = _mr(visual_plan=plan)
    ctx = _ctx()
    stage_input = VisualStageInput(mr=mr, svg=None, visual_plan=plan)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_q5v_pass_when_svg_texts_subset_of_labels():
    reg = _installed_registry()
    gate = _gate(reg, "visual", "G-Q5v")
    plan = VisualPlan(style="grid", labels=["A", "B"], elements=[VisualElement(kind="point", attrs={})])
    mr = _mr(visual_plan=plan)
    ctx = _ctx(frame=DummyFrame(forbidden=frozenset()))
    svg = "<svg><text>A</text><text>B</text></svg>"
    stage_input = VisualStageInput(mr=mr, svg=svg, visual_plan=plan)

    ok, detail = gate(stage_input, ctx)
    assert ok is True


def test_g_q5v_fail_when_svg_text_not_in_labels():
    reg = _installed_registry()
    gate = _gate(reg, "visual", "G-Q5v")
    plan = VisualPlan(style="grid", labels=["A", "B"], elements=[])
    mr = _mr(visual_plan=plan)
    ctx = _ctx()
    svg = "<svg><text>A</text><text>SECRET</text></svg>"
    stage_input = VisualStageInput(mr=mr, svg=svg, visual_plan=plan)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "SECRET" in detail


def test_g_q5v_fail_when_forbidden_element_present():
    reg = _installed_registry()
    gate = _gate(reg, "visual", "G-Q5v")
    plan = VisualPlan(
        style="grid", labels=["A"],
        elements=[VisualElement(kind="right_angle_mark", attrs={})],
    )
    mr = _mr(visual_plan=plan)
    ctx = _ctx(frame=DummyFrame(forbidden=frozenset({"right_angle_mark"})))
    svg = "<svg><text>A</text></svg>"
    stage_input = VisualStageInput(mr=mr, svg=svg, visual_plan=plan)

    ok, detail = gate(stage_input, ctx)
    assert ok is False
    assert "right_angle_mark" in detail
