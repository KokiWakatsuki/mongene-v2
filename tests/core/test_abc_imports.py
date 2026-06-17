"""ABC + データクラスがインポートできることの確認"""
from __future__ import annotations

import inspect

from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom, VerbAtom
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    SubQuestionStrategy,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL, VisualSlot
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)


def test_abc_classes_are_abstract() -> None:
    assert inspect.isabstract(NounAtom)
    assert inspect.isabstract(VerbAtom)
    assert inspect.isabstract(VisualComponent)


def test_atom_constraints_constructs() -> None:
    c = AtomConstraints(difficulty_band=(1, 10), forbidden_tags=[], seed=42)
    assert c.seed == 42
    assert c.custom == {}


def test_blueprint_definition_constructs() -> None:
    bp = BlueprintDefinition(
        blueprint_id="X",
        blueprint_version="v1",
        noun_slots={"a": NounSlot(slot_name="a")},
        verb_invocations=[],
        visual_slot=VisualSlot(component_type="NullRenderer"),
        supported_forms=["calculation"],
        base_difficulty_calculator=lambda n, c: 10,
        subquestion_strategy=SubQuestionStrategy(strategy_type="single"),
    )
    assert bp.blueprint_id == "X"
    assert "a" in bp.noun_slots
