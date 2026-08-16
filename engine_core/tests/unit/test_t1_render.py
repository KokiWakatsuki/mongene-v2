"""Task4: T1 レンダラ（engine.core.render.t1_template）の unit テスト。

TemplateContext が answer/srepr/params を一切公開しないこと（属性が無い）を
attribute-level で assert する（§7.2 の「構文的に答えを書けない」の検証）。
フィルタ num/frac/pt の出力・explanation の決定論結合（接続詞列の pin 含む）・
hints の steps_prefix（steps<2 のフォールバック含む）を検証する。
"""
from __future__ import annotations

import re
from typing import Any

import pytest
import sympy

from engine.core.contracts import (
    MR,
    Provenance,
    SpecFamily,
    SpecLevel,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    VisualReq,
)
from engine.core.contracts import CellContext, GenerateOptions, Coordinate
from engine.core.registry import _Registry
from engine.core.render.t1_template import (
    TemplateContext,
    TextResult,
    filter_frac,
    filter_num,
    filter_pt,
    filter_unit,
    render_text,
)


class DummyFrame:
    def __init__(self, form: str, given_vocab: frozenset[str], asked_vocab: frozenset[str], visual: VisualReq) -> None:
        self.form = form
        self.given_vocab = given_vocab
        self.asked_vocab = asked_vocab
        self.visual = visual

    def check_mr(self, mr: Any) -> tuple[bool, str]:
        return True, ""

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        return frozenset()


def _mk_mr(*, steps_count: int = 3, given: dict[str, str] | None = None) -> MR:
    given = given or {"point_a": "(1, 3)", "point_b": "(4, 12)"}
    steps = [
        Step(op=f"op{i}", args=[], result_srepr=f"r{i}", result_display=f"disp{i}", narration=f"narration{i}")
        for i in range(steps_count)
    ]
    return MR(
        signature="sig1",
        family="math.g2_l25.find_value",
        level=2,
        purpose="base",
        seed=1,
        params={"a": 3, "b": 0},
        given=given,
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked="expression",
                answer=SymbolicAnswer(srepr="x", display="y = 3x"),
                steps=steps,
                concept_tags=["c1"],
                cause_tags=[],
            )
        ],
        provenance=Provenance(recipe="math.dummy_recipe"),
    )


def _mk_ctx(*, hints: list[str] | None = None, text_hints: list[str] | None = None) -> CellContext:
    text: dict[str, Any] = {"tier": "T1", "template": "dummy_template_v1"}
    if text_hints is not None:
        text["hints"] = text_hints
    spec_level = SpecLevel(
        level=2, signature="sig1", recipe="math.dummy_recipe", params={},
        given=["point_a", "point_b"], asked=["expression"], visual="none",
        text=text, hints=hints if hints is not None else ["steps_prefix"], cause_tags=[],
    )
    spec_family = SpecFamily(
        family="math.g2_l25.find_value", form="find_value", source_desc="d",
        concepts_default=["c1"], levels={"2": spec_level}, remedial_default_level=2,
    )
    frame = DummyFrame(
        form="find_value",
        given_vocab=frozenset({"point_a", "point_b"}),
        asked_vocab=frozenset({"expression"}),
        visual="optional",
    )
    return CellContext(
        subject="math", family="math.g2_l25.find_value", form="find_value", unit="g2_l25",
        level=2, purpose="base", frame=frame, spec_family=spec_family, spec_level=spec_level,
        curriculum_view={}, requested=Coordinate(subject="math", unit="g2_l25", form="find_value", level=2),
        options=GenerateOptions(),
    )


def _registry_with_template(source: str) -> _Registry:
    reg = _Registry()
    reg.register_template("dummy_template_v1", source)
    return reg


# ---------------------------------------------------------------------------
# TemplateContext: answer/srepr/params を公開しない
# ---------------------------------------------------------------------------
def test_template_context_has_no_answer_or_srepr_or_params_attrs():
    mr = _mk_mr()
    tctx = TemplateContext.from_mr(mr)

    assert not hasattr(tctx, "answer")
    assert not hasattr(tctx, "srepr")
    assert not hasattr(tctx, "params")
    # sub_questions のビューも asked/label/narrations のみ
    sq = tctx.sub_questions[0]
    assert not hasattr(sq, "answer")
    assert not hasattr(sq, "srepr")
    assert sq.asked == "expression"
    assert sq.label == "(1)"
    assert sq.narrations == ["narration0", "narration1", "narration2"]


def test_template_context_exposes_given_and_context_slots():
    mr = _mk_mr()
    mr.context_slots = {"name": "太郎"}
    tctx = TemplateContext.from_mr(mr)
    assert tctx.given == {"point_a": "(1, 3)", "point_b": "(4, 12)"}
    assert tctx.context_slots == {"name": "太郎"}


# ---------------------------------------------------------------------------
# フィルタ
# ---------------------------------------------------------------------------
def test_filter_num_wraps_negative_in_parens():
    assert filter_num(-3) == "(-3)"
    assert filter_num(3) == "3"


def test_filter_frac_reduced_no_mixed_number():
    v = sympy.Rational(6, 4)  # 既約化すると 3/2
    assert filter_frac(v) == "3/2"
    assert filter_frac(sympy.Rational(-3, 2)) == "-3/2"
    assert filter_frac(4) == "4"  # 整数はそのまま


def test_filter_pt_formats_coordinate():
    assert filter_pt((1, 3)) == "(1, 3)"
    assert filter_pt((-2, 4)) == "(-2, 4)"


def test_filter_unit_appends_unit():
    assert filter_unit(3, "cm") == "3cm"


# ---------------------------------------------------------------------------
# render_text: problem_text にテンプレが適用される・フィルタが使える
# ---------------------------------------------------------------------------
def test_render_text_applies_template_and_filters():
    template_src = (
        "2点 {{ given.point_a }} と {{ given.point_b }} を通る直線の式を求めなさい。"
        "{% for sq in sub_questions %}{{ sq.label }}{{ sq.asked }}{% endfor %}"
    )
    registry = _registry_with_template(template_src)
    mr = _mk_mr()
    ctx = _mk_ctx()

    result = render_text(mr, ctx, registry=registry)

    assert isinstance(result, TextResult)
    assert "(1, 3)" in result.problem_text
    assert "(4, 12)" in result.problem_text
    assert "(1)expression" in result.problem_text
    assert result.render_keys == {"tier": "T1", "template": "dummy_template_v1"}
    assert "(1)" in result.prompts


# ---------------------------------------------------------------------------
# explanation: narration + result_display の決定論結合
# ---------------------------------------------------------------------------
def test_explanation_is_deterministic_concatenation_of_narration_and_display():
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=2)
    ctx = _mk_ctx()

    result = render_text(mr, ctx, registry=registry)
    explanation = result.explanations["(1)"]

    assert "narration0" in explanation
    assert "disp0" in explanation
    assert "narration1" in explanation
    assert "disp1" in explanation
    # 決定論: 同じ MR から2回呼んでも同じ結果
    result2 = render_text(mr, ctx, registry=registry)
    assert result2.explanations["(1)"] == explanation


# ---------------------------------------------------------------------------
# Step.detail: 解説だけに出る（ヒント・問題文には流れない）
#
# detail は**実際の値で操作を名指しする**ための欄なので、数字を持つ。ヒントや
# 問題文に漏れると G-Q5t（答えの先出し）の穴になる。「解説にしか出ない」を
# 検査で固定する（`Step` の docstring・鉄則⑦）。
# ---------------------------------------------------------------------------
def _mk_mr_with_detail() -> MR:
    mr = _mk_mr(steps_count=2)
    mr.sub_questions[0].steps[0].detail = "両辺から 5 をひく。"
    return mr


def test_explanation_prefers_detail_over_narration():
    registry = _registry_with_template("stem")
    explanation = render_text(_mk_mr_with_detail(), _mk_ctx(), registry=registry).explanations["(1)"]

    assert "両辺から 5 をひく。" in explanation
    # detail を書いた手は narration が出ない（二重に出ると同じことを2回言う）
    assert "narration0" not in explanation
    # 書いていない手は従来どおり narration が出る
    assert "narration1" in explanation


def test_detail_never_reaches_hints():
    registry = _registry_with_template("stem")
    hints = render_text(_mk_mr_with_detail(), _mk_ctx(hints=["steps_prefix"]), registry=registry).hints["(1)"]

    assert hints == ["narration0"]
    assert not any("5" in h for h in hints), hints


def test_detail_is_not_exposed_to_templates():
    """テンプレートから detail を書けない＝問題文に漏れないことを構造で保つ。"""
    tctx = TemplateContext.from_mr(_mk_mr_with_detail())
    assert not hasattr(tctx.sub_questions[0], "detail")
    assert not hasattr(tctx.sub_questions[0], "details")

    # テンプレートが detail を参照しても、Jinja は未定義として空を返す（本文に出ない）
    registry = _registry_with_template("{{ sub_questions[0].details }}stem")
    text = render_text(_mk_mr_with_detail(), _mk_ctx(), registry=registry).problem_text
    assert "5" not in text, text


# ---------------------------------------------------------------------------
# explanation の接続詞列: 「最後に、」は最終ステップ専用（steps>=3）
# steps が4個以上でも「最後に、」が途中に出ないことを pin する
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("steps_count", "expected"),
    [
        (1, ["まず、"]),
        (2, ["まず、", "次に、"]),
        (3, ["まず、", "次に、", "最後に、"]),
        (4, ["まず、", "次に、", "次に、", "最後に、"]),
        (6, ["まず、", "次に、", "次に、", "次に、", "次に、", "最後に、"]),
    ],
)
def test_explanation_connectives_use_last_only_for_final_step(steps_count, expected):
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=steps_count)
    ctx = _mk_ctx()

    explanation = render_text(mr, ctx, registry=registry).explanations["(1)"]

    # narration{i} の直前に付いた接続詞を取り出して列として比較する
    assert re.findall(r"まず、|次に、|最後に、|さらに、", explanation) == expected
    # 「さらに、」は使わない・「最後に、」は1回だけ（steps>=3 のとき末尾に1回）
    assert "さらに、" not in explanation
    assert explanation.count("最後に、") == (1 if steps_count >= 3 else 0)
    # 期待する完全一致（narration/result_display の結合形も固定）
    # 1ステップ=1行・result_display は括弧。区切り無し連結だと result_display の末尾に
    # 次の接続詞が直付けされて「…をつくる。 disp0次に、」と読めない文になる。
    assert explanation == "\n".join(
        f"{conn}narration{i}（disp{i}）" for i, conn in enumerate(expected)
    )


# ---------------------------------------------------------------------------
# explanation: 文の切れ目（result_display の直後に次の接続詞が来ない）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("steps_count", [2, 3, 4, 6])
def test_explanation_never_runs_result_display_into_next_connective(steps_count):
    """接続詞の直前は必ず文の終わり（句点・閉じ括弧・改行）であること。

    実バグの回帰: 区切り無し連結だと「…残った文字を求める。 x = 125最後に、…」となり、
    golden 1140 件のうち 1059 件がこの読めない文を持っていた。
    """
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=steps_count)
    explanation = render_text(mr, _mk_ctx(), registry=registry).explanations["(1)"]

    assert re.search(r"[^。）\n](次に、|最後に、)", explanation) is None, explanation


def test_explanation_omits_parentheses_when_result_display_is_empty():
    """result_display が空のステップは空括弧「（）」を出さない。"""
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=2)
    steps = list(mr.sub_questions[0].steps)
    steps[0] = steps[0].model_copy(update={"result_display": ""})
    sq = mr.sub_questions[0].model_copy(update={"steps": steps})
    mr = mr.model_copy(update={"sub_questions": [sq]})

    explanation = render_text(mr, _mk_ctx(), registry=registry).explanations["(1)"]

    assert "（）" not in explanation
    assert explanation == "まず、narration0\n次に、narration1（disp1）"


# ---------------------------------------------------------------------------
# hints: steps_prefix は steps>=2 で前から k=len-1 個開示
# ---------------------------------------------------------------------------
def test_hints_steps_prefix_reveals_all_but_last():
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=3)
    ctx = _mk_ctx(hints=["steps_prefix"])

    result = render_text(mr, ctx, registry=registry)
    hints = result.hints["(1)"]

    assert hints == ["narration0", "narration1"]  # 最後の narration2 は開示しない


# ---------------------------------------------------------------------------
# hints: steps<2 の場合は空にせずテンプレ定義ヒント（spec に無ければ最小定型ヒント）
# ---------------------------------------------------------------------------
def test_hints_fallback_when_steps_below_two_uses_template_defined_hint():
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=1)
    ctx = _mk_ctx(hints=["steps_prefix"], text_hints=["与えられた2点を式に代入してみよう。"])

    result = render_text(mr, ctx, registry=registry)
    hints = result.hints["(1)"]

    assert hints == ["与えられた2点を式に代入してみよう。"]


def test_hints_fallback_minimal_when_no_template_hint_defined():
    registry = _registry_with_template("stem")
    mr = _mk_mr(steps_count=1)
    ctx = _mk_ctx(hints=["steps_prefix"], text_hints=None)

    result = render_text(mr, ctx, registry=registry)
    hints = result.hints["(1)"]

    assert len(hints) == 1
    assert hints[0]  # 非空の定型ヒント
