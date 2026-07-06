"""`scripts/build_product_corpus.py` の LLM フリー単体テスト。

- product ファイル名が run_gates.py の `_GT_FILENAME_RE` / `load_product_corpus` と
  互換であること（合成 product JSON を一時ディレクトリに置いて読めることを確認）。
- claude engine の `parse_claude_response`（合成 response JSON → product JSON 組み立て）が
  期待形状になること。answer は常に GT(SymPy) の値を使うこと。
"""
from __future__ import annotations

import json
from pathlib import Path

from scripts.build_product_corpus import load_gt_keys, parse_claude_response
from scripts.run_gates import load_product_corpus


def _write_product(path: Path, content_problem_text: str = "テスト問題") -> None:
    product = {
        "content_problem_text": content_problem_text,
        "sub_questions": [
            {
                "label": "(1)",
                "prompt_text": "計算しなさい。",
                "answer": {"type": "numeric", "sympy_form": "13", "text_form": "13", "extras": {}},
                "explanation_text": "解説。",
            }
        ],
        "visuals": {"problem_diagram_url": None, "explanation_diagram_url": None},
        "metadata": {
            "base_difficulty": 0,
            "adjustment_delta": 0,
            "used_atoms": [],
            "seed": 1,
            "blueprint_id": "BasicCalculationStructure",
            "blueprint_version": "1.0",
            "problem_form": "word_problem",
        },
    }
    path.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")


def test_product_filename_is_paired_by_load_product_corpus(tmp_path: Path) -> None:
    """build_product_corpus が書くファイル名規則 `{lesson}_{form}_{level}.json` が
    run_gates.load_product_corpus の _GT_FILENAME_RE と互換であることを確認する。
    """
    product_dir = tmp_path / "gemini"
    product_dir.mkdir()
    _write_product(product_dir / "g1_l1_word_problem_min.json")
    _write_product(product_dir / "g1_l1_word_problem_mid.json")
    _write_product(product_dir / "exam_l1_calculation_max.json")

    grouped = load_product_corpus(product_dir)

    assert ("g1_l1", "word_problem") in grouped
    assert set(grouped[("g1_l1", "word_problem")].keys()) == {"min", "mid"}
    assert ("exam_l1", "calculation") in grouped
    assert set(grouped[("exam_l1", "calculation")].keys()) == {"max"}


def test_unrelated_files_are_ignored_by_load_product_corpus(tmp_path: Path) -> None:
    product_dir = tmp_path / "gemini"
    product_dir.mkdir()
    _write_product(product_dir / "g1_l1_word_problem_min.json")
    (product_dir / "_staging_note.json").write_text("{}", encoding="utf-8")
    (product_dir / "not_a_valid_name.json").write_text("{}", encoding="utf-8")

    grouped = load_product_corpus(product_dir)

    assert list(grouped.keys()) == [("g1_l1", "word_problem")]


def test_load_gt_keys_reads_pinned_seed_and_parses_filename(tmp_path: Path) -> None:
    gt_dir = tmp_path / "ground_truth"
    gt_dir.mkdir()
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "word_problem",
        "seed": 12772,
        "sub_questions": [],
        "_difficulty_label": "min",
        "_target_level": 1,
        "_lesson_id": "g1_l1",
        "_problem_form": "word_problem",
        "_pinned_seed": 12772,
    }
    (gt_dir / "g1_l1_word_problem_min.json").write_text(
        json.dumps(gt_data, ensure_ascii=False), encoding="utf-8"
    )

    entries = load_gt_keys(gt_dir)

    assert len(entries) == 1
    entry = entries[0]
    assert entry["key"] == "g1_l1_word_problem_min"
    assert entry["lesson_id"] == "g1_l1"
    assert entry["form"] == "word_problem"
    assert entry["level_label"] == "min"
    assert entry["target_level"] == 1
    assert entry["pinned_seed"] == 12772


def test_load_gt_keys_falls_back_to_recomputed_seed_when_missing(tmp_path: Path) -> None:
    """旧 GT（_pinned_seed が無い）でも corpus_seed.pinned_seed と同じ式で再計算する。"""
    from scripts.corpus_seed import pinned_seed

    gt_dir = tmp_path / "ground_truth"
    gt_dir.mkdir()
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "word_problem",
        "seed": 999,
        "sub_questions": [],
        "_target_level": 1,
    }
    (gt_dir / "g1_l1_word_problem_min.json").write_text(
        json.dumps(gt_data, ensure_ascii=False), encoding="utf-8"
    )

    entries = load_gt_keys(gt_dir)
    assert entries[0]["pinned_seed"] == pinned_seed("g1_l1", "word_problem", "min")


def test_load_gt_keys_filters_by_lesson_and_form(tmp_path: Path) -> None:
    gt_dir = tmp_path / "ground_truth"
    gt_dir.mkdir()
    for lesson, form in [("g1_l1", "word_problem"), ("g1_l1", "knowledge"), ("g1_l2", "word_problem")]:
        data = {"lesson_id": lesson, "problem_form": form, "seed": 1, "sub_questions": []}
        (gt_dir / f"{lesson}_{form}_min.json").write_text(json.dumps(data), encoding="utf-8")

    entries = load_gt_keys(gt_dir, lesson_filter="g1_l1")
    assert {e["form"] for e in entries} == {"word_problem", "knowledge"}

    entries = load_gt_keys(gt_dir, form_filter="word_problem")
    assert {e["lesson_id"] for e in entries} == {"g1_l1", "g1_l2"}


def test_parse_claude_response_builds_expected_product_shape() -> None:
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "word_problem",
        "seed": 12772,
        "blueprint_id": "BasicCalculationStructure",
        "blueprint_version": "v1",
        "selected_tags": ["integer", "number"],
        "sub_questions": [
            {
                "label": "(1)",
                "answer": {
                    "type": "numeric",
                    "sympy_form": "-7",
                    "text_form": "-7",
                    "extras": {},
                },
            }
        ],
    }
    response_data = {
        "content_problem_text": "ある工場の気温は...",
        "sub_questions": [
            {
                "label": "(1)",
                "prompt_text": "正午の気温を求めなさい。",
                "explanation_text": "解説テキスト。",
            }
        ],
    }

    product = parse_claude_response(response_data, gt_data, "word_problem")

    assert product["content_problem_text"] == "ある工場の気温は..."
    assert len(product["sub_questions"]) == 1
    sq = product["sub_questions"][0]
    assert sq["label"] == "(1)"
    assert sq["prompt_text"] == "正午の気温を求めなさい。"
    assert sq["explanation_text"] == "解説テキスト。"
    # answer は常に GT(SymPy) の値（LLM は答えを変えない）
    assert sq["answer"]["sympy_form"] == "-7"
    assert sq["answer"]["text_form"] == "-7"
    assert product["visuals"]["problem_diagram_url"] is None
    assert product["metadata"]["blueprint_id"] == "BasicCalculationStructure"
    assert product["metadata"]["seed"] == 12772
    assert product["metadata"]["problem_form"] == "word_problem"


def test_parse_claude_response_does_not_use_llm_answer_even_if_present() -> None:
    """response 側に answer らしきものが混入していても、GT の値だけが使われることを確認。"""
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "calculation",
        "seed": 1,
        "blueprint_id": "BasicCalculationStructure",
        "blueprint_version": "1.0",
        "selected_tags": [],
        "sub_questions": [
            {
                "label": "(1)",
                "answer": {"type": "numeric", "sympy_form": "42", "text_form": "42", "extras": {}},
            }
        ],
    }
    response_data = {
        "content_problem_text": "次を計算しなさい。",
        "sub_questions": [
            {"label": "(1)", "prompt_text": "計算しなさい。", "answer": "999（LLMが勝手に書いた値）"}
        ],
    }

    product = parse_claude_response(response_data, gt_data, "calculation")

    assert product["sub_questions"][0]["answer"]["sympy_form"] == "42"


def test_parse_claude_response_extracts_svg_from_visuals_field() -> None:
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "visual",
        "seed": 1,
        "blueprint_id": "BasicCalculationStructure",
        "blueprint_version": "1.0",
        "selected_tags": [],
        "sub_questions": [{"label": "(1)", "answer": {"type": "numeric", "sympy_form": "1", "text_form": "1"}}],
    }
    response_data = {
        "content_problem_text": "右の図を見て答えなさい。",
        "sub_questions": [{"label": "(1)", "prompt_text": "答えなさい。", "explanation_text": ""}],
        "visuals": {"problem_diagram_url": "<svg></svg>"},
    }

    product = parse_claude_response(response_data, gt_data, "visual")

    assert product["visuals"]["problem_diagram_url"] == "<svg></svg>"


def test_ingested_product_json_is_paired_by_run_gates(tmp_path: Path) -> None:
    """claude ingest が書く product JSON が実際に load_product_corpus でペアリングできること
    をエンドツーエンドに近い形で確認する（parse_claude_response の出力をそのまま保存）。
    """
    gt_data = {
        "lesson_id": "g1_l1",
        "problem_form": "word_problem",
        "seed": 12772,
        "blueprint_id": "BasicCalculationStructure",
        "blueprint_version": "v1",
        "selected_tags": [],
        "sub_questions": [
            {"label": "(1)", "answer": {"type": "numeric", "sympy_form": "-7", "text_form": "-7"}}
        ],
    }
    response_data = {
        "content_problem_text": "問題文。",
        "sub_questions": [{"label": "(1)", "prompt_text": "求めなさい。", "explanation_text": "解説。"}],
    }
    product = parse_claude_response(response_data, gt_data, "word_problem")

    product_dir = tmp_path / "claude"
    product_dir.mkdir()
    (product_dir / "g1_l1_word_problem_min.json").write_text(
        json.dumps(product, ensure_ascii=False), encoding="utf-8"
    )

    grouped = load_product_corpus(product_dir)
    assert grouped[("g1_l1", "word_problem")]["min"]["content_problem_text"] == "問題文。"
