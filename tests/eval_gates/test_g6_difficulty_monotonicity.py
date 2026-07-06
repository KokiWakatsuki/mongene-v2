"""G6 難易度単調性ゲートの単体テスト（ground truthのみ・product不要・LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g6_difficulty_monotonicity import check, check_monotonicity
from tests.eval_gates.conftest import make_ground_truth


def _gt_with_steps(step_count: int, max_operand: int, has_sqrt: bool = False) -> dict:
    gt = make_ground_truth(answer_sympy_form="sqrt(2)" if has_sqrt else "10")
    logic_steps = [
        {"operation_name": "op", "operands": [max_operand, 1], "sympy_expr": "10"}
        for _ in range(step_count)
    ]
    gt["sub_questions"][0]["logic_steps"] = logic_steps
    return gt


def test_pass_when_monotonically_increasing():
    gt_min = _gt_with_steps(step_count=1, max_operand=5)
    gt_mid = _gt_with_steps(step_count=2, max_operand=20)
    gt_max = _gt_with_steps(step_count=3, max_operand=50, has_sqrt=True)
    result = check_monotonicity(gt_min, gt_mid, gt_max)
    assert result.verdict == "PASS"


def test_fail_when_not_monotonically_increasing():
    """min/mid/maxで難易度特徴が単調でないケースを FAIL にできること（spec必須回帰）。"""
    gt_min = _gt_with_steps(step_count=3, max_operand=50, has_sqrt=True)  # 本来 max より難しい
    gt_mid = _gt_with_steps(step_count=2, max_operand=20)
    gt_max = _gt_with_steps(step_count=1, max_operand=5)  # 本来 min より易しい
    result = check_monotonicity(gt_min, gt_mid, gt_max)
    assert result.verdict == "FAIL"


def test_fail_when_mid_equals_min():
    gt_min = _gt_with_steps(step_count=1, max_operand=5)
    gt_mid = _gt_with_steps(step_count=1, max_operand=5)
    gt_max = _gt_with_steps(step_count=3, max_operand=50)
    result = check_monotonicity(gt_min, gt_mid, gt_max)
    assert result.verdict == "FAIL"


def test_check_wrapper_uses_min_mid_max_keys():
    gt_min = _gt_with_steps(step_count=1, max_operand=5)
    gt_mid = _gt_with_steps(step_count=2, max_operand=20)
    gt_max = _gt_with_steps(step_count=3, max_operand=50)
    combined_gt = {"min": gt_min, "mid": gt_mid, "max": gt_max}
    result = check(None, combined_gt)
    assert result.verdict == "PASS"


def test_check_wrapper_na_when_keys_missing():
    result = check(None, make_ground_truth())
    assert result.verdict == "N/A"
