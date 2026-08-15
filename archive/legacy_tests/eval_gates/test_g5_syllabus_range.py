"""G5 範囲逸脱ゲートの単体テスト（合成フィクスチャ、LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g5_syllabus_range import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_pass_with_clean_text():
    gt = make_ground_truth()
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_forbidden_word_present():
    gt = make_ground_truth()
    product = make_product(content_problem_text="次の計算をしなさい。誰かを殺す場面を想像しなさい。")
    result = check(product, gt)
    assert result.verdict == "FAIL"
    assert "殺す" in result.details.get("forbidden_hits", [])


def test_fail_when_unlearned_vocab_present():
    gt = make_ground_truth(lesson_id="g1_l1")
    product = make_product(content_problem_text="平方根を用いて次の値を求めなさい。")
    result = check(product, gt)
    assert result.verdict == "FAIL"
    assert "平方根" in result.details.get("unlearned_hits", [])


def test_na_when_text_is_empty():
    gt = make_ground_truth()
    product = make_product(content_problem_text="")
    result = check(product, gt)
    assert result.verdict == "N/A"
