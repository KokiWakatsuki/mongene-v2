"""`scripts/run_gates.py` の G6走査ロジック（+ 既存の1:1ゲート読み込み）の単体テスト。

G6-b は `master_data/mapping.json` 相当の合成 dict を直接渡して判定する（生成不要）。
G6-a は生成を要するため、ここでは `run_g6a_conformance` 本体ではなく、その内部で使う
`check_conformance` 呼び出し部分の配線を確認する薄いテストに留める（実生成は
`scripts/build_ground_truth_corpus.py` 等の統合実行で確認する）。

LLM は使わない。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.run_gates import (
    load_ground_truth_corpus,
    run_g6b_distinctness,
)
from tests.eval_gates.conftest import make_ground_truth


def _write_gt(out_dir: Path, lesson: str, form: str, level: str, data: dict[str, Any]) -> None:
    path = out_dir / f"{lesson}_{form}_{level}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_load_ground_truth_corpus_groups_by_lesson_and_form(tmp_path: Path) -> None:
    gt = make_ground_truth()
    _write_gt(tmp_path, "g1_l1", "calculation", "min", gt)
    _write_gt(tmp_path, "g1_l1", "calculation", "mid", gt)
    _write_gt(tmp_path, "g1_l1", "calculation", "max", gt)
    _write_gt(tmp_path, "g1_l1", "word_problem", "min", gt)

    grouped = load_ground_truth_corpus(tmp_path)

    assert set(grouped.keys()) == {("g1_l1", "calculation"), ("g1_l1", "word_problem")}
    assert set(grouped[("g1_l1", "calculation")].keys()) == {"min", "mid", "max"}
    assert set(grouped[("g1_l1", "word_problem")].keys()) == {"min"}


def test_load_ground_truth_corpus_ignores_non_matching_files(tmp_path: Path) -> None:
    _write_gt(tmp_path, "g1_l1", "calculation", "min", make_ground_truth())
    (tmp_path / "ground_truth_build_failures.json").write_text("[]", encoding="utf-8")

    grouped = load_ground_truth_corpus(tmp_path)

    assert list(grouped.keys()) == [("g1_l1", "calculation")]


def test_load_ground_truth_corpus_empty_dir_returns_empty(tmp_path: Path) -> None:
    empty_dir = tmp_path / "does_not_exist"
    grouped = load_ground_truth_corpus(empty_dir)
    assert grouped == {}


# ---------------------------------------------------------------------------
# G6-b: mapping.json 相当の合成 dict を直接走査する
# ---------------------------------------------------------------------------


def _mapping_with_levels(lesson_id: str, form: str, level_defs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        lesson_id: {
            "grade": 1,
            "supported_forms": [form],
            "atom_constraints": {},
            "difficulty_levels": {form: level_defs},
        }
    }


def test_run_g6b_distinctness_pass_for_all_distinct_levels() -> None:
    mapping = _mapping_with_levels(
        "g1_l3",
        "calculation",
        [
            {"lv": 1, "atom_constraints": {"NumberAtom": {"allow_negative": False}}, "verb_config": {}},
            {"lv": 2, "atom_constraints": {"NumberAtom": {"allow_negative": True}}, "verb_config": {}},
        ],
    )
    results = run_g6b_distinctness(mapping)
    assert len(results) == 1
    assert results[0]["lesson_id"] == "g1_l3"
    assert results[0]["form"] == "calculation"
    assert results[0]["verdict"] == "PASS"


def test_run_g6b_distinctness_fail_for_collapsed_levels() -> None:
    """spec 回帰アンカーの縮小版: 同一シグネチャの Lv 群は FAIL。"""
    mapping = _mapping_with_levels(
        "g1_l33",
        "calculation",
        [
            {"lv": 1, "atom_constraints": {}, "verb_config": {}},
            {"lv": 2, "atom_constraints": {}, "verb_config": {}},
            {"lv": 3, "atom_constraints": {}, "verb_config": {}},
        ],
    )
    results = run_g6b_distinctness(mapping)
    assert len(results) == 1
    assert results[0]["verdict"] == "FAIL"


def test_run_g6b_distinctness_na_when_no_difficulty_levels() -> None:
    mapping = {
        "g1_lX": {
            "grade": 1,
            "supported_forms": ["calculation"],
            "atom_constraints": {},
            # difficulty_levels 未定義
        }
    }
    results = run_g6b_distinctness(mapping)
    assert len(results) == 1
    assert results[0]["verdict"] == "N/A"


def test_run_g6b_distinctness_handles_multiple_lessons_independently() -> None:
    mapping = {
        "g1_l3": {
            "grade": 1,
            "supported_forms": ["calculation"],
            "atom_constraints": {},
            "difficulty_levels": {
                "calculation": [
                    {"lv": 1, "atom_constraints": {"NumberAtom": {"allow_negative": False}}, "verb_config": {}},
                    {"lv": 2, "atom_constraints": {"NumberAtom": {"allow_negative": True}}, "verb_config": {}},
                ]
            },
        },
        "g1_l33": {
            "grade": 1,
            "supported_forms": ["calculation"],
            "atom_constraints": {},
            "difficulty_levels": {
                "calculation": [
                    {"lv": 1, "atom_constraints": {}, "verb_config": {}},
                    {"lv": 2, "atom_constraints": {}, "verb_config": {}},
                ]
            },
        },
    }
    results = run_g6b_distinctness(mapping)
    verdicts = {(r["lesson_id"], r["form"]): r["verdict"] for r in results}
    assert verdicts[("g1_l3", "calculation")] == "PASS"
    assert verdicts[("g1_l33", "calculation")] == "FAIL"


def test_run_g6b_distinctness_covers_all_supported_forms_per_lesson() -> None:
    """1 lesson が複数 form をサポートする場合、form ごとに個別の (lesson,form) 判定を出す。"""
    mapping = {
        "g1_l3": {
            "grade": 1,
            "supported_forms": ["calculation", "word_problem"],
            "atom_constraints": {},
            "difficulty_levels": {
                "calculation": [
                    {"lv": 1, "atom_constraints": {"NumberAtom": {"allow_negative": False}}, "verb_config": {}},
                    {"lv": 2, "atom_constraints": {"NumberAtom": {"allow_negative": True}}, "verb_config": {}},
                ],
                # word_problem は difficulty_levels 未定義 → N/A
            },
        }
    }
    results = run_g6b_distinctness(mapping)
    by_form = {r["form"]: r["verdict"] for r in results}
    assert by_form["calculation"] == "PASS"
    assert by_form["word_problem"] == "N/A"
