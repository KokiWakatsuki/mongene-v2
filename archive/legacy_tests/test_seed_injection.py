"""外部から注入した seed による決定論性の検証（LLMフリー・SymPy固定）。

GenerationRequest.seed を指定して BlueprintRunner.run() を2回呼び、
生成される中間表現（MiddleRepresentation）の seed・sampled_nouns_info・
各 sub_question の答えが完全に一致することを確認する。

seed=None のときに従来の非決定挙動が壊れていないこと（毎回 mr.seed が
決まった値に固定されてしまわないこと）も併せて確認する。
"""
from __future__ import annotations

import json
from pathlib import Path

from apps.api.src.atoms.noun import number_atom  # noqa: F401 -- register_noun 実行
from apps.api.src.atoms.verb import calculate_arithmetic_verb  # noqa: F401
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest

MAPPING_PATH = Path(__file__).resolve().parents[1] / "master_data" / "mapping.json"
LESSON_ID = "g1_l5"
FORM = "calculation"
TARGET_LEVEL = 1


def _make_runner(tmp_db: Path) -> BlueprintRunner:
    return BlueprintRunner(
        dedup=DuplicationGuard(db_path=str(tmp_db)),
        diversity=DiversityRotation(),
        translator=LLMTranslator(),
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=20,
    )


def _lesson_mapping() -> dict:
    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    return mapping[LESSON_ID]


def _run_once(tmp_path: Path, seed: int | None):
    # dedup DB を分けて衝突ガードの影響を排除する（各呼び出しが独立した runner）
    runner = _make_runner(tmp_path / f"dedup_{seed}_{id(tmp_path)}.db")
    request = GenerationRequest(
        problem_form=FORM,
        lesson_id=LESSON_ID,
        target_level=TARGET_LEVEL,
        seed=seed,
    )
    return runner.run(request, _lesson_mapping())


def _answers(result) -> list[str]:
    return [str(sq.answer.sympy_form) for sq in result.middle_representation.sub_questions]


def test_same_seed_produces_identical_middle_representation(tmp_path: Path) -> None:
    seed = 424242
    result_a = _run_once(tmp_path / "a", seed)
    result_b = _run_once(tmp_path / "b", seed)

    mr_a = result_a.middle_representation
    mr_b = result_b.middle_representation

    assert mr_a.seed == mr_b.seed
    assert mr_a.sampled_nouns_info == mr_b.sampled_nouns_info
    assert _answers(result_a) == _answers(result_b)


def test_seed_none_keeps_legacy_nondeterministic_behavior(tmp_path: Path) -> None:
    # seed=None のときは従来通り毎回異なる seed が採用されうる（後方互換の確認）。
    # ごく低確率で偶然一致することはあるため、複数回試行して少なくとも1回は
    # 異なる seed が観測されることを確認する。
    seeds_seen: set[int] = set()
    for i in range(5):
        result = _run_once(tmp_path / f"none_{i}", None)
        seeds_seen.add(result.middle_representation.seed)
    assert len(seeds_seen) >= 2
