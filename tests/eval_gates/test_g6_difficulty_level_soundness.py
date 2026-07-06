"""G6 難易度レベル健全性ゲートの単体テスト（合成フィクスチャ・LLM不要）。

G6-b（レベル非崩壊・生成不要）と G6-a（制約適合・合成サンプル）を検証する。
実LLM・実コーパスは使わない。
"""
from __future__ import annotations

from scripts.eval_gates.g6_difficulty_level_soundness import (
    build_generation_fingerprint,
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


def test_distinctness_fail_when_all_levels_collapse_ignoring_blueprint_params_static_fallback():
    """静的シグネチャのみのフォールバックモード（sample_fn 未指定）の回帰アンカー。

    blueprint_params/description のみで区別された Lv群は、生成器が無い環境では
    区別不能とみなさざるを得ない（例: g1_l44 knowledge 5Lv → atom_constraints/verb_config が
    全て空で同一シグネチャ）。生成ベースモードでは PASS になりうる
    （test_distinctness_pass_generation_based_when_knowledge_hint_differs 参照）。
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
    assert result.details["mode"] == "static_only"


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
# G6-b: レベル非崩壊 (distinctness) — 生成ベース判定（sample_fn 指定時）
# ---------------------------------------------------------------------------


def _knowledge_levels(n: int) -> list[dict]:
    """g1_l44 型: atom_constraints/verb_config は全 Lv で空（静的シグネチャは同一）。"""
    return [
        {
            "lv": lv,
            "description": f"説明文{lv}",
            "atom_constraints": {},
            "blueprint_params": {"knowledge_hint": f"hint_{lv}"},
            "verb_config": {},
        }
        for lv in range(1, n + 1)
    ]


def _knowledge_ground_truth(hint: str) -> dict:
    """実際の `/inspect` knowledge 出力形状（router.py の knowledge_check 分岐）を模す。

    knowledge_hint 文言は answer.extras にではなく、prompt_hint / narration_hint /
    logic_steps[].operands に verbatim で現れる（実装確認済み）。
    """
    return {
        "lesson_id": "g1_l44",
        "lesson_title": "テストレッスン",
        "blueprint_id": "KnowledgeBaseStructure",
        "problem_form": "knowledge",
        "difficulty_score": 8.5,
        "selected_tags": [],
        "seed": 1,
        "sampled_atoms": {},
        "sub_questions": [
            {
                "label": "",
                "prompt_hint": f"次の問いに答えなさい：{hint}",
                "answer": {"type": "knowledge", "sympy_form": "None", "text_form": "（概念説明・用語定義）"},
                "logic_steps": [
                    {
                        "operation_name": "knowledge_check",
                        "operands": [f"次の問いに答えなさい：{hint}"],
                        "sympy_expr": "1",
                        "narration_hint": f"次の問いに答えなさい：{hint}",
                    }
                ],
            }
        ],
    }


def test_distinctness_pass_generation_based_when_knowledge_hint_differs():
    """静的シグネチャは同一でも、生成物（knowledge_hint 文言）が Lv ごとに異なれば PASS。

    knowledge/visual(construction) 系の偽陽性が生成ベース化で解消される、というタスクの主眼。
    実際の `/inspect` 出力同様、hint 文言は narration_hint/operands に verbatim で乗る。
    """
    levels = _knowledge_levels(5)

    def sample_fn(lesson_id: str, form: str, lv: int) -> dict:
        # 各 Lv は常に固有の knowledge_hint 文言を生成する（seed に依らず区別可能）。
        return _knowledge_ground_truth(f"hint_{lv}")

    result = check_distinctness("g1_l44", "knowledge", levels, sample_fn=sample_fn, n_samples=3)
    assert result.verdict == "PASS"
    assert result.details["mode"] == "generation_based"


def test_distinctness_fail_generation_based_when_output_truly_identical():
    """静的シグネチャが同一 かつ 生成物も M回生成して一度も区別できないなら真の崩壊 = FAIL。

    (例: g1_l33 calc のように全Lvが同じ BasicCalculationStructure フォールバックで、
    レベル間の差異が一切生成物に反映されないケース)。
    """
    levels = [
        {
            "lv": lv,
            "description": f"説明文{lv}",
            "atom_constraints": {},
            "blueprint_params": {},
            "verb_config": {},
        }
        for lv in range(1, 4)
    ]

    def sample_fn(lesson_id: str, form: str, lv: int) -> dict:
        # Lv に関係なく全く同じ問題内容を返す（真の崩壊）。
        return make_ground_truth(operands=[5, 3], answer_text_form="8")

    result = check_distinctness("g1_l33", "calculation", levels, sample_fn=sample_fn, n_samples=3)
    assert result.verdict == "FAIL"
    assert result.details["mode"] == "generation_based"
    assert result.details["collapsed_groups"] == [[1, 2, 3]]


def test_distinctness_generation_based_skips_pairs_with_distinct_static_signature():
    """静的シグネチャが最初から異なる Lv は生成を待たずに PASS（sample_fn は呼ばれない）。"""
    levels = [
        _lv(1, atom_constraints={"NumberAtom": {"allow_negative": False}}),
        _lv(2, atom_constraints={"NumberAtom": {"allow_negative": True}}),
    ]
    calls = []

    def sample_fn(lesson_id: str, form: str, lv: int) -> dict:
        calls.append(lv)
        return make_ground_truth()

    result = check_distinctness("g1_l3", "calculation", levels, sample_fn=sample_fn, n_samples=3)
    assert result.verdict == "PASS"
    assert calls == []  # プレフィルタで候補に上がらないため生成は一度も呼ばれない


def test_distinctness_generation_based_inconclusive_when_generation_fails_for_one_level():
    """候補グループ内の一方の Lv が1件も生成できない場合は判定不能として除外し FAIL にしない。

    (偽FAILを出さない・精度優先の原則)。
    """
    levels = _knowledge_levels(2)

    def sample_fn(lesson_id: str, form: str, lv: int) -> dict:
        if lv == 2:
            raise RuntimeError("NoCompatibleBlueprintError: 未実装")
        return make_ground_truth(answer_text_form=f"hint_{lv}")

    result = check_distinctness("g1_lX", "knowledge", levels, sample_fn=sample_fn, n_samples=3)
    assert result.verdict != "FAIL"
    assert result.details["inconclusive_groups"] == [[1, 2]]


def test_build_generation_fingerprint_ignores_numeric_operand_values():
    """数値オペランドの具体値・符号は乱数由来のノイズとして無視する（意図的な設計）。

    符号や大きさが違うだけの2サンプルは同一フィンガープリントになる。乱数ノイズだけで
    「区別できた」と誤判定しない（=真の崩壊を見逃さない）ための核心の設計判断。
    allow_negative/max_value 等の数値制約の適否は G6-a（conformance）の管轄。
    """
    gt_a = make_ground_truth(operands=[5, 3], answer_text_form="8")
    gt_b = make_ground_truth(operands=[5, 3], answer_text_form="8")
    gt_c = make_ground_truth(operands=[-5, 3], answer_text_form="-2")
    assert build_generation_fingerprint(gt_a) == build_generation_fingerprint(gt_b)
    assert build_generation_fingerprint(gt_a) == build_generation_fingerprint(gt_c)


def test_build_generation_fingerprint_differs_on_non_numeric_operand_or_narration():
    """非数値オペランド（construction_type等の固定文字列）や narration_hint の違いは区別する。"""
    gt_a = make_ground_truth(
        operands=[5, 3],
        extra_sub_question_answers=None,
    )
    gt_a["sub_questions"][0]["logic_steps"][0]["narration_hint"] = "垂線の作図"
    gt_b = make_ground_truth(operands=[5, 3])
    gt_b["sub_questions"][0]["logic_steps"][0]["narration_hint"] = "垂直二等分線の作図"
    assert build_generation_fingerprint(gt_a) != build_generation_fingerprint(gt_b)


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
