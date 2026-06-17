"""y_base 推論 + difficulty reconciler のテスト"""
from __future__ import annotations

from apps.api.src.atoms.verb.calculate_arithmetic_verb import CalculateArithmeticVerb
from apps.api.src.core.abc.blueprint import (
    BlueprintDefinition,
    NounSlot,
    VerbInvocation,
)
from apps.api.src.core.abc.visuals import VisualSlot
from apps.api.src.core.difficulty.base_difficulty import compute_y_base
from apps.api.src.core.runner.difficulty_reconciler import (
    DELTA_MAX,
    reconcile_difficulty,
)


def _dummy_blueprint() -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id="X",
        blueprint_version="v1",
        noun_slots={"a": NounSlot(slot_name="a", accepted_noun_types=["NumberAtom"])},
        verb_invocations=[
            VerbInvocation(
                verb=CalculateArithmeticVerb("+"),
                input_slots=["a"],
                output_slot="r",
            )
        ],
        visual_slot=VisualSlot(component_type="NullRenderer"),
        supported_forms=["calculation"],
        base_difficulty_calculator=lambda n, c: 50,
    )


def test_compute_y_base_grade1_basic() -> None:
    y = compute_y_base("中学1年", "数と式", "符号のついた数", 1, 7)
    # 10 + 0 + 1.43 + 0 = 約 11
    assert 10 <= y <= 12


def test_compute_y_base_grade3_pythagorean_app() -> None:
    y = compute_y_base("中学3年", "図形", "三平方の空間図形への利用", 8, 10)
    # 55 + 8 + 8 + 5 = 約 76
    assert 70 <= y <= 80


def test_reconcile_within_delta_max() -> None:
    plan = reconcile_difficulty(target=20, y_base=15, blueprint=_dummy_blueprint(), problem_form="calculation")
    assert plan.unsatisfiable is False
    assert plan.computed_difficulty == 20


def test_reconcile_target_too_high_marks_unsatisfiable() -> None:
    plan = reconcile_difficulty(target=100, y_base=10, blueprint=_dummy_blueprint(), problem_form="calculation")
    # 差が 90、DELTA_MAX (15) + 余裕 20 を超えるので unsatisfiable
    assert plan.unsatisfiable is True


def test_reconcile_target_low_caps_at_minus_delta_max() -> None:
    plan = reconcile_difficulty(target=1, y_base=80, blueprint=_dummy_blueprint(), problem_form="calculation")
    assert plan.unsatisfiable is False
    assert plan.computed_difficulty == 80 - DELTA_MAX
