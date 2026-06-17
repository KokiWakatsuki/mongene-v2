"""低カバレッジモジュールの補助テスト"""
from __future__ import annotations

import sympy

from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.registry import (
    find_nouns_by_tags,
    get_noun_class,
    get_verb_class,
    list_noun_names,
    list_verb_names,
)
from apps.api.src.core.abc.atoms import AtomConstraints
from apps.api.src.core.constants import JHS_GRADE_FROM_LABEL, JHS_GRADE_LABEL
from apps.api.src.core.evaluation.appropriateness import (
    is_appropriate,
    load_forbidden_words,
)
from apps.api.src.core.llm.fallback import template_fallback_text
from apps.api.src.core.llm.translator import LLMTranslator, _strip_json_fence, translate
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)
from apps.api.src.visuals.null_renderer import NullRenderer
from apps.api.src.core.abc.visuals import VisualDSL


def test_constants_round_trip() -> None:
    for grade, label in JHS_GRADE_LABEL.items():
        assert JHS_GRADE_FROM_LABEL[label] == grade


def test_null_renderer_returns_empty_string() -> None:
    dsl = VisualDSL(render_type="Null", elements=[])
    assert NullRenderer().render(dsl) == ""


def test_registry_lookup() -> None:
    names = list_noun_names()
    assert "NumberAtom" in names
    assert get_noun_class("NumberAtom") is NumberAtom
    assert "CalculateArithmeticVerb" in list_verb_names()
    assert get_verb_class("CalculateArithmeticVerb").__name__ == "CalculateArithmeticVerb"


def test_find_nouns_by_tags_filters() -> None:
    matched = find_nouns_by_tags(["number"])
    assert NumberAtom in matched
    forbidden_matched = find_nouns_by_tags(["number"], forbidden=["number"])
    assert NumberAtom not in forbidden_matched


def test_load_forbidden_words_returns_list() -> None:
    # master_data/forbidden_words.txt が存在する前提
    words = load_forbidden_words()
    assert isinstance(words, list)
    assert all(isinstance(w, str) for w in words)


def test_is_appropriate_default_loads_file() -> None:
    # forbidden_words を指定せず: ファイルから読み込み
    assert is_appropriate("普通の問題文") is True


def _make_simple_mr() -> MiddleRepresentation:
    step = LogicStep(
        operation_name="arithmetic_+",
        operands=["1", "2"],
        sympy_expr=sympy.Integer(3),
        narration_hint="和を計算",
    )
    return MiddleRepresentation(
        problem_structure_type="X",
        selected_tags=[],
        difficulty_score=10.0,
        problem_form="calculation",
        sub_questions=[
            SubQuestion(
                label="(1)",
                prompt_hint="計算",
                logic_steps=[step],
                answer=AnswerObject(type="numeric", sympy_form=sympy.Integer(3), text_form="3"),
            )
        ],
        visual_dsl=None,
        seed=1234,
        blueprint_id="X",
        blueprint_version="v1",
    )


def test_template_fallback_text_includes_narration() -> None:
    text = template_fallback_text(_make_simple_mr())
    assert "和を計算" in text


def test_strip_json_fence() -> None:
    raw = "```json\n{\"a\": 1}\n```"
    assert _strip_json_fence(raw) == '{"a": 1}'


def test_translate_module_function_returns_str() -> None:
    out = translate("dummy prompt with problem_text and sub_question_texts", model="standard")
    assert isinstance(out, str)
    assert "TEST" in out or "problem_text" in out


def test_llm_translator_returns_three_values() -> None:
    translator = LLMTranslator()
    problem_text, sub_texts, explanation = translator.translate(_make_simple_mr(), story=None, lesson_grade=1)
    assert isinstance(problem_text, str)
    assert isinstance(sub_texts, list)
    assert isinstance(explanation, str)


def test_atom_constraints_estimate_param_space() -> None:
    constraints = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=0,
        custom={"max_value": 30, "allow_negative": True},
    )
    assert NumberAtom.estimate_param_space(constraints) > 0
