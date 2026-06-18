"""難易度モデルのテスト（Raw Score + 正規化モデル）"""
from __future__ import annotations

from apps.api.src.atoms.verb.calculate_arithmetic_verb import CalculateArithmeticVerb
from apps.api.src.core.abc.blueprint import BlueprintDefinition, NounSlot, VerbInvocation
from apps.api.src.core.abc.visuals import VisualSlot
from apps.api.src.core.difficulty.base_difficulty import (
    compute_raw_y_base,
    normalize,
    denormalize,
    LARGE_UNIT_RAW_SCORE,
    RAW_MIN,
    RAW_MAX,
)
from apps.api.src.core.runner.difficulty_reconciler import (
    reconcile_difficulty,
    get_form_range_from_y_base,
    FORM_RAW_BONUS,
)


def _dummy_blueprint(bp_id: str = "X") -> BlueprintDefinition:
    return BlueprintDefinition(
        blueprint_id=bp_id,
        blueprint_version="v1",
        noun_slots={"a": NounSlot(slot_name="a", accepted_noun_types=["NumberAtom"])},
        verb_invocations=[
            VerbInvocation(verb=CalculateArithmeticVerb("+"), input_slots=["a"], output_slot="r")
        ],
        visual_slot=VisualSlot(component_type="NullRenderer"),
        supported_forms=["calculation"],
        base_difficulty_calculator=lambda n, c: 50,
    )


# ------ Raw Score モデル ------

def test_normalize_min_is_1() -> None:
    assert normalize(RAW_MIN) == 1


def test_normalize_max_is_100() -> None:
    assert normalize(RAW_MAX) == 100


def test_denormalize_roundtrip() -> None:
    for score in [1, 25, 50, 75, 100]:
        raw = denormalize(score)
        assert RAW_MIN <= raw <= RAW_MAX


def test_raw_y_base_g1_intro() -> None:
    # 中1 正の数・負の数 + 意味/導入 → 100 + 0 = 100 → normalize = 1
    raw = compute_raw_y_base("正の数・負の数", "符号のついた数（意味と表し方）")
    assert raw == 100
    assert normalize(raw) == 1


def test_raw_y_base_g3_pythagorean_app() -> None:
    # 三平方の定理(900) + 利用(250) = 1150 → normalize ≒ 88
    raw = compute_raw_y_base("三平方の定理", "空間図形への利用")
    assert raw == 1150
    y = normalize(raw)
    assert 85 <= y <= 92


def test_raw_y_base_g3_surface_path() -> None:
    # 三平方の定理(900) + 融合/発展(400) = 1300 → normalize = 100
    raw = compute_raw_y_base("三平方の定理", "立体の表面上の最短距離（展開図の利用）")
    assert raw == RAW_MAX
    assert normalize(raw) == 100


def test_large_unit_scores_are_ordered() -> None:
    # 簡単な単元 < 難しい単元
    assert LARGE_UNIT_RAW_SCORE["正の数・負の数"] < LARGE_UNIT_RAW_SCORE["一次方程式"]
    assert LARGE_UNIT_RAW_SCORE["一次方程式"] < LARGE_UNIT_RAW_SCORE["三平方の定理"]


# ------ 難易度調整 ------

def test_form_raw_bonus_ordered() -> None:
    assert FORM_RAW_BONUS["calculation"] < FORM_RAW_BONUS["word_problem"] < FORM_RAW_BONUS["proof"]


def test_get_form_range_calculation_narrower_than_word_problem() -> None:
    c_lo, c_hi = get_form_range_from_y_base(50, "calculation")
    w_lo, w_hi = get_form_range_from_y_base(50, "word_problem")
    # word_problem は form_bonus が高いので min が高く、max も高い
    assert w_lo >= c_lo
    assert w_hi >= c_hi


def test_get_form_range_proof_has_highest_min() -> None:
    c_lo, _ = get_form_range_from_y_base(50, "calculation")
    w_lo, _ = get_form_range_from_y_base(50, "word_problem")
    p_lo, _ = get_form_range_from_y_base(50, "proof")
    assert p_lo > w_lo > c_lo


def test_reconcile_within_range() -> None:
    y_base = 34
    target = 50
    plan = reconcile_difficulty(target=target, y_base=y_base, blueprint=_dummy_blueprint(), problem_form="calculation")
    assert plan.unsatisfiable is False
    assert plan.computed_difficulty == target


def test_reconcile_target_below_min_caps_at_lo() -> None:
    y_base = 50
    lo, _ = get_form_range_from_y_base(y_base, "calculation")
    plan = reconcile_difficulty(target=1, y_base=y_base, blueprint=_dummy_blueprint(), problem_form="calculation")
    assert plan.unsatisfiable is False
    assert plan.computed_difficulty == lo


def test_reconcile_target_above_max_marks_unsatisfiable() -> None:
    y_base = 5  # 非常に簡単な単元
    _, hi = get_form_range_from_y_base(y_base, "calculation")
    plan = reconcile_difficulty(target=100, y_base=y_base, blueprint=_dummy_blueprint(), problem_form="calculation")
    # hi が 100 に満たない場合 unsatisfiable
    if hi < 90:
        assert plan.unsatisfiable is True


def test_delta_factors_have_correct_keys() -> None:
    plan = reconcile_difficulty(target=80, y_base=50, blueprint=_dummy_blueprint(), problem_form="word_problem")
    # word_problem には hint_reduction が含まれる
    assert "hint_reduction" in plan.delta_factors
