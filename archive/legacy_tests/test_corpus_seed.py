"""`scripts/corpus_seed.pinned_seed` の決定論性の検証（LLMフリー）。"""
from __future__ import annotations

from scripts.corpus_seed import pinned_seed


def test_same_key_produces_same_seed() -> None:
    a = pinned_seed("g1_l1", "word_problem", "min")
    b = pinned_seed("g1_l1", "word_problem", "min")
    assert a == b


def test_different_level_label_usually_produces_different_seed() -> None:
    seeds = {
        pinned_seed("g1_l1", "word_problem", "min"),
        pinned_seed("g1_l1", "word_problem", "mid"),
        pinned_seed("g1_l1", "word_problem", "max"),
    }
    assert len(seeds) == 3


def test_different_form_usually_produces_different_seed() -> None:
    seeds = {
        pinned_seed("g1_l1", "word_problem", "min"),
        pinned_seed("g1_l1", "calculation", "min"),
        pinned_seed("g1_l1", "knowledge", "min"),
    }
    assert len(seeds) == 3


def test_different_lesson_usually_produces_different_seed() -> None:
    seeds = {
        pinned_seed("g1_l1", "word_problem", "min"),
        pinned_seed("g1_l2", "word_problem", "min"),
        pinned_seed("g2_l1", "word_problem", "min"),
    }
    assert len(seeds) == 3


def test_seed_is_within_generation_request_bounds() -> None:
    # ProblemGenerationRequest.seed は ge=1 制約。pinned_seed は必ず 1 以上を返すこと。
    for lesson, form, level in [
        ("g1_l1", "word_problem", "min"),
        ("exam_l1", "calculation", "max"),
        ("g3_l30", "proof", "mid"),
    ]:
        seed = pinned_seed(lesson, form, level)
        assert seed >= 1
        assert isinstance(seed, int)
