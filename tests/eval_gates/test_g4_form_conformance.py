"""G4 形式適合ゲートの単体テスト（合成フィクスチャ、LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g4_form_conformance import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_knowledge_pass_with_required_marker():
    gt = make_ground_truth(problem_form="knowledge")
    product = make_product(
        content_problem_text="次のうち、正しい計算結果はどれか。ア. -41 イ. -39"
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_knowledge_fail_when_bare_calculation():
    gt = make_ground_truth(problem_form="knowledge")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-1\right) + 25$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_proof_pass_with_structure_markers():
    gt = make_ground_truth(problem_form="proof")
    product = make_product(
        content_problem_text="次の図で△ABC≡△DEFであることを証明しなさい。仮定より∠A=∠D、結論として合同が言える。"
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_proof_fail_with_bare_calculation():
    gt = make_ground_truth(problem_form="proof")
    product = make_product(content_problem_text=r"次の計算をしなさい $3 + 4$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_word_problem_pass_with_scenario_vocab():
    gt = make_ground_truth(problem_form="word_problem")
    product = make_product(
        content_problem_text="工場である製品を1時間あたり何個作れるか、速さを求めなさい。"
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_word_problem_fail_with_bare_expression():
    """症例: 符号付き数の word_problem が素の (-1)+25=24 になるケース（診断§1.1）を検出できる。"""
    gt = make_ground_truth(problem_form="word_problem")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-1\right) + 25$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_visual_pass_with_url_and_reference():
    gt = make_ground_truth(problem_form="visual")
    product = make_product(
        content_problem_text="右の図のような三角形について、角度を求めなさい。",
        problem_diagram_url="https://example.com/diagram.svg",
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_visual_fail_when_url_missing():
    gt = make_ground_truth(problem_form="visual")
    product = make_product(
        content_problem_text="右の図のような三角形について、角度を求めなさい。",
        problem_diagram_url=None,
    )
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_calculation_pass_with_bare_expression():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_calculation_fail_when_scenario_vocab_present():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"工場で $\left(-27\right) + 10$ 個作った。")
    result = check(product, gt)
    assert result.verdict == "FAIL"
