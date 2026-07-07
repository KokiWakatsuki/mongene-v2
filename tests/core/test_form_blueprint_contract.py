"""form/blueprint 契約強制のテスト（LLMフリー・SymPy固定）。

BlueprintRunner.run() は、mapping.json が要求する problem_form を、
選ばれた blueprint が supported_forms に持たない場合、黙って別の form 用
blueprint（典型的には calculation 用の BasicCalculationStructure）に
退化してはならず、正直に NoCompatibleBlueprintError を投げる必要がある。

g1_l1 は good な題材:
  - execute_blueprint = "BasicCalculationStructure" (supported_forms=["calculation"])
  - execute_blueprint_by_form = {"knowledge": "KnowledgeBaseStructure"}
  - mapping.supported_forms = ["word_problem", "knowledge"]

  → word_problem を要求すると、候補は BasicCalculationStructure のみで、
    これは supported_forms に word_problem を含まないため契約違反
    （実際に scripts/validate_form_blueprint_contract.py が検出する既知の違反）。
  → knowledge を要求すると、execute_blueprint_by_form 経由で
    KnowledgeBaseStructure が選ばれ、これは supported_forms=["knowledge"]
    を満たすため正常に生成される（退化しない）。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.api.src.atoms.noun import linear_func_atom, number_atom  # noqa: F401
from apps.api.src.atoms.verb import (  # noqa: F401
    calculate_arithmetic_verb,
    knowledge_check_verb,
)
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.exceptions import NoCompatibleBlueprintError
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest

MAPPING_PATH = Path(__file__).resolve().parents[2] / "master_data" / "mapping.json"
LESSON_ID = "g1_l1"


def _lesson_mapping() -> dict:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    return mapping[LESSON_ID]


def _make_runner(tmp_db: Path) -> BlueprintRunner:
    return BlueprintRunner(
        dedup=DuplicationGuard(db_path=str(tmp_db)),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=10,
    )


# 「宣言 form を候補 blueprint が supported_forms に持たない → 静かなフォールバックせず
# NoCompatibleBlueprintError」の機構テスト用。実データの契約違反は全解消したため、
# g2_l29（候補=MovingPointStructure）に **MovingPointStructure が対応しない proof** を
# 合成注入して未対応 form を再現する（MovingPointStructure.supported_forms=
# [calculation, word_problem, visual]）。
VIOLATION_LESSON_ID = "g2_l29"
VIOLATION_FORM = "proof"


def _violation_lesson_mapping() -> dict:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    m = dict(mapping[VIOLATION_LESSON_ID])
    # proof を supported_forms に宣言注入（候補 blueprint は proof 非対応 → 契約違反を再現）
    m["supported_forms"] = list(m.get("supported_forms", [])) + ["proof"]
    return m


def test_unsupported_form_raises_no_compatible_blueprint_error(tmp_path: Path) -> None:
    """mapping が要求する form を候補 blueprint が supported_forms に持たない場合、
    黙って calculation に退化せず NoCompatibleBlueprintError を投げること。
    """
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(
        problem_form=VIOLATION_FORM,
        lesson_id=VIOLATION_LESSON_ID,
        target_difficulty=6,
    )
    with pytest.raises(NoCompatibleBlueprintError) as excinfo:
        runner.run(request, _violation_lesson_mapping())

    message = str(excinfo.value)
    assert VIOLATION_LESSON_ID in message
    assert VIOLATION_FORM in message
    assert "MovingPointStructure" in message


def test_supported_form_generates_without_degradation(tmp_path: Path) -> None:
    """form を実際に supported_forms に持つ blueprint が候補にあれば、
    退化せずその blueprint で正常に生成されること。
    """
    runner = _make_runner(tmp_path / "dedup.db")
    request = GenerationRequest(
        problem_form="knowledge",
        lesson_id=LESSON_ID,
        target_difficulty=6,
    )
    result = runner.run(request, _lesson_mapping())

    assert result.middle_representation.blueprint_id == "KnowledgeBaseStructure"
    assert result.middle_representation.problem_form == "knowledge"
    assert result.middle_representation.sub_questions
