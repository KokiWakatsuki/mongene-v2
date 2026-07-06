"""`scripts/run_gates.py` のグルーピング/G6走査ロジックの単体テスト。

実コーパスは使わず、合成した3レベル(min/mid/max) ground truth JSON を一時ディレクトリに書き出し、
`load_ground_truth_corpus` + `run_g6_monotonicity` に通して、単調/非単調を正しく分類できることを
確認する。LLM は使わない。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.eval_gates.g6_difficulty_monotonicity import check_monotonicity
from scripts.run_gates import load_ground_truth_corpus, run_g6_monotonicity
from tests.eval_gates.conftest import make_ground_truth


def _gt_with_steps(step_count: int, max_operand: int, has_sqrt: bool = False) -> dict[str, Any]:
    gt = make_ground_truth(answer_sympy_form="sqrt(2)" if has_sqrt else "10")
    logic_steps = [
        {"operation_name": "op", "operands": [max_operand, 1], "sympy_expr": "10"}
        for _ in range(step_count)
    ]
    gt["sub_questions"][0]["logic_steps"] = logic_steps
    return gt


def _write_gt(out_dir: Path, lesson: str, form: str, level: str, data: dict[str, Any]) -> None:
    path = out_dir / f"{lesson}_{form}_{level}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_load_ground_truth_corpus_groups_by_lesson_and_form(tmp_path: Path) -> None:
    _write_gt(tmp_path, "g1_l1", "calculation", "min", _gt_with_steps(1, 5))
    _write_gt(tmp_path, "g1_l1", "calculation", "mid", _gt_with_steps(2, 20))
    _write_gt(tmp_path, "g1_l1", "calculation", "max", _gt_with_steps(3, 50))
    _write_gt(tmp_path, "g1_l1", "word_problem", "min", _gt_with_steps(1, 5))

    grouped = load_ground_truth_corpus(tmp_path)

    assert set(grouped.keys()) == {("g1_l1", "calculation"), ("g1_l1", "word_problem")}
    assert set(grouped[("g1_l1", "calculation")].keys()) == {"min", "mid", "max"}
    assert set(grouped[("g1_l1", "word_problem")].keys()) == {"min"}


def test_load_ground_truth_corpus_ignores_non_matching_files(tmp_path: Path) -> None:
    _write_gt(tmp_path, "g1_l1", "calculation", "min", _gt_with_steps(1, 5))
    # 命名規則に合わない補助ファイル（失敗ログ等）は無視されるべき
    (tmp_path / "ground_truth_build_failures.json").write_text("[]", encoding="utf-8")

    grouped = load_ground_truth_corpus(tmp_path)

    assert list(grouped.keys()) == [("g1_l1", "calculation")]


def test_run_g6_monotonicity_classifies_monotonic_group_as_pass(tmp_path: Path) -> None:
    grouped = {
        ("g1_l1", "calculation"): {
            "min": _gt_with_steps(1, 5),
            "mid": _gt_with_steps(2, 20),
            "max": _gt_with_steps(3, 50, has_sqrt=True),
        }
    }

    results = run_g6_monotonicity(grouped, check_monotonicity)

    assert len(results) == 1
    assert results[0]["lesson_id"] == "g1_l1"
    assert results[0]["form"] == "calculation"
    assert results[0]["verdict"] == "PASS"


def test_run_g6_monotonicity_classifies_non_monotonic_group_as_fail(tmp_path: Path) -> None:
    grouped = {
        ("g1_l2", "knowledge"): {
            # min/mid/max のスコアが全部同じ = 実データで頻出する「分離しない」パターンを再現
            "min": _gt_with_steps(1, 5),
            "mid": _gt_with_steps(1, 5),
            "max": _gt_with_steps(1, 5),
        }
    }

    results = run_g6_monotonicity(grouped, check_monotonicity)

    assert len(results) == 1
    assert results[0]["verdict"] == "FAIL"


def test_run_g6_monotonicity_marks_incomplete_group_as_na() -> None:
    grouped = {
        ("g2_l45", "visual"): {
            "min": _gt_with_steps(1, 5),
            "mid": _gt_with_steps(1, 5),
            # max が無い（例: NoCompatibleBlueprintError でground truth生成に失敗したケース）
        }
    }

    results = run_g6_monotonicity(grouped, check_monotonicity)

    assert len(results) == 1
    assert results[0]["verdict"] == "N/A"
    assert "揃っていない" in results[0]["reason"]


def test_run_g6_monotonicity_handles_multiple_groups_independently() -> None:
    grouped = {
        ("g1_l1", "calculation"): {
            "min": _gt_with_steps(1, 5),
            "mid": _gt_with_steps(2, 20),
            "max": _gt_with_steps(3, 50),
        },
        ("g1_l2", "knowledge"): {
            "min": _gt_with_steps(1, 5),
            "mid": _gt_with_steps(1, 5),
            "max": _gt_with_steps(1, 5),
        },
    }

    results = run_g6_monotonicity(grouped, check_monotonicity)

    verdicts = {(r["lesson_id"], r["form"]): r["verdict"] for r in results}
    assert verdicts[("g1_l1", "calculation")] == "PASS"
    assert verdicts[("g1_l2", "knowledge")] == "FAIL"


def test_load_ground_truth_corpus_empty_dir_returns_empty(tmp_path: Path) -> None:
    empty_dir = tmp_path / "does_not_exist"
    grouped = load_ground_truth_corpus(empty_dir)
    assert grouped == {}
