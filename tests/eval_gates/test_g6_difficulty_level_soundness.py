"""G6 難易度レベル健全性ゲートの単体テスト（合成フィクスチャ・LLM不要）。

G6-b（レベル非崩壊・生成不要）と G6-a（制約適合・合成サンプル）を検証する。
実LLM・実コーパスは使わない。
"""
from __future__ import annotations

from scripts.eval_gates.g6_difficulty_level_soundness import (
    check,
    check_conformance,
    check_distinctness,
    compute_level_signature,
)
from tests.eval_gates.conftest import make_ground_truth


def _lv(lv: int, atom_constraints=None, blueprint_override=None, verb_config=None):
    return {
        "lv": lv,
        "description": f"Lv{lv} description (これは判定に無関係)",
        "atom_constraints": atom_constraints or {},
        "blueprint_override": blueprint_override,
        "verb_config": verb_config or {},
    }


def _gt_with_operands(operands: list) -> dict:
    gt = make_ground_truth(operands=operands)
    return gt


# ---------------------------------------------------------------------------
# G6-b: レベル非崩壊 (distinctness)
# ---------------------------------------------------------------------------


def test_distinctness_pass_when_all_levels_differ():
    levels = [
        _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False, "max_value": 10}}),
        _lv(2, atom_constraints={"NumberAtom": {"allow_negative": True, "max_value": 10}}),
        _lv(3, atom_constraints={"NumberAtom": {"allow_negative": True, "max_value": 50}}),
    ]
    result = check_distinctness("g1_l3", "calculation", levels)
    assert result.verdict == "PASS"


def test_distinctness_fail_when_two_levels_collapse():
    levels = [
        _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}}),
        _lv(2, atom_constraints={"NumberAtom": {"allow_negative": True}}),
        _lv(3, atom_constraints={"NumberAtom": {"allow_negative": True}}),  # Lv2と同じ
    ]
    result = check_distinctness("g1_l3", "calculation", levels)
    assert result.verdict == "FAIL"
    assert "Lv2" in result.reason and "Lv3" in result.reason


def test_distinctness_fail_when_all_levels_collapse_ignoring_blueprint_params():
    """spec 回帰アンカー: blueprint_params/description のみで区別された Lv群は崩壊とみなす

    (例: g1_l44 knowledge 5Lv → atom_constraints/verb_config が全て空で同一シグネチャ)。
    """
    levels = [
        {
            "lv": lv,
            "description": f"説明文{lv}（これだけ違う）",
            "atom_constraints": {},
            "blueprint_params": {"construction_type": f"type_{lv}", "knowledge_hint": f"hint_{lv}"},
            "verb_config": {},
        }
        for lv in range(1, 6)
    ]
    result = check_distinctness("g1_l44", "knowledge", levels)
    assert result.verdict == "FAIL"
    assert result.details["distinct_signatures"] == 1
    assert result.details["total_levels"] == 5


def test_distinctness_na_when_only_one_level():
    levels = [_lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}})]
    result = check_distinctness("g1_lX", "calculation", levels)
    assert result.verdict == "N/A"


def test_distinctness_na_when_no_levels_defined():
    result = check_distinctness("g1_lX", "calculation", [])
    assert result.verdict == "N/A"


def test_signature_ignores_description_and_blueprint_params():
    lv_a = _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}})
    lv_b = dict(lv_a)
    lv_b["description"] = "全く違う説明文"
    lv_b["blueprint_params"] = {"operation": "-"}
    assert compute_level_signature(lv_a) == compute_level_signature(lv_b)


def test_signature_differs_on_atom_constraints():
    lv_a = _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}})
    lv_b = _lv(2, atom_constraints={"NumberAtom": {"allow_negative": True}})
    assert compute_level_signature(lv_a) != compute_level_signature(lv_b)


# ---------------------------------------------------------------------------
# G6-a: 制約適合 (conformance)
# ---------------------------------------------------------------------------


def test_conformance_fail_when_negative_operand_appears_despite_allow_negative_false():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}})
    samples = [
        _gt_with_operands([5, 3]),
        _gt_with_operands([-2, 4]),  # 違反
    ]
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "FAIL"
    assert "allow_negative" in result.reason


def test_conformance_pass_when_all_samples_conform():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False, "max_value": 10}})
    samples = [
        _gt_with_operands([5, 3]),
        _gt_with_operands([10, 0]),
        _gt_with_operands([7, 2]),
    ]
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "PASS"


def test_conformance_fail_when_max_value_exceeded():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"max_value": 10}})
    samples = [_gt_with_operands([5, 3]), _gt_with_operands([50, 2])]
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "FAIL"
    assert "max_value" in result.reason


def test_conformance_na_when_no_observable_params_declared():
    """observable でない制約のみ宣言（例: polygon_type）→ N/A（偽FAILを出さない）。"""
    lv_def = _lv(1, atom_constraints={"PolygonAtom": {"polygon_type": "triangle"}})
    samples = [_gt_with_operands([5, 3])]
    result = check_conformance("g1_lX", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "N/A"


def test_conformance_na_when_no_samples():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}})
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints={}, samples=[])
    assert result.verdict == "N/A"


def test_conformance_merges_base_and_patch_constraints():
    """ベース atom_constraints の allow_negative=true が Lv patch の max_value=5 とマージされ、
    負のオペランドが出ても allow_negative 側は違反にならない（ベース設定が真）ことを確認。
    """
    base = {"NumberAtom": {"allow_negative": True, "max_value": 30}}
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"max_value": 5}})
    samples = [_gt_with_operands([-3, 2]), _gt_with_operands([4, -1])]
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints=base, samples=samples)
    # allow_negative=True なので負のオペランドはOK。max_value=5 も超過していないのでPASS。
    assert result.verdict == "PASS"


def test_conformance_fail_when_patch_overrides_base_max_value_and_violated():
    base = {"NumberAtom": {"allow_negative": True, "max_value": 30}}
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"max_value": 5}})
    samples = [_gt_with_operands([20, 2])]  # base の30以下だがpatchの5は超過
    result = check_conformance("g1_l3", "calculation", 1, lv_def, base_atom_constraints=base, samples=samples)
    assert result.verdict == "FAIL"


def test_conformance_force_fraction_true_pass_when_fraction_present():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"force_fraction": True}})
    samples = [_gt_with_operands(["1/2", 3])]
    result = check_conformance("g1_lX", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "PASS"


def test_conformance_force_fraction_true_fail_when_no_fraction_anywhere():
    lv_def = _lv(1, atom_constraints={"NumberAtom": {"force_fraction": True}})
    samples = [_gt_with_operands([5, 3]), _gt_with_operands([2, 1])]
    result = check_conformance("g1_lX", "calculation", 1, lv_def, base_atom_constraints={}, samples=samples)
    assert result.verdict == "FAIL"
    assert "force_fraction" in result.reason


def test_check_wrapper_always_na():
    """他ゲートと同じ check(product, ground_truth) 規約で誤って呼ばれた場合は N/A。"""
    result = check(None, make_ground_truth())
    assert result.verdict == "N/A"
