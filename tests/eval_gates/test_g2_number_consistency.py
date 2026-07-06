"""G2 数値整合ゲートの単体テスト（合成フィクスチャ、LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g2_number_consistency import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_pass_when_all_required_numbers_present():
    gt = make_ground_truth(operands=[-27, 10], answer_sympy_form="-17")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_required_number_missing():
    gt = make_ground_truth(operands=[-27, 10], answer_sympy_form="-17")
    # LLM が数値を書き換えてしまったケース: 10 が 15 になっている
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 15$")
    result = check(product, gt)
    assert result.verdict == "FAIL"
    assert "missing" in result.details


def test_pass_with_dimension_numbers_from_sampled_atoms():
    gt = make_ground_truth(
        operands=[],
        answer_sympy_form="30",
        sampled_atoms={"shape1": {"atom_type": "PrismAtom", "dimensions_cm": {"width": "5", "height": "6"}}},
    )
    gt["sub_questions"][0]["logic_steps"] = [
        {"operation_name": "multiply", "operands": [], "sympy_expr": "30"}
    ]
    product = make_product(content_problem_text="縦5cm、横6cmの長方形の面積を求めなさい。$5 \\times 6$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_dimension_number_missing():
    gt = make_ground_truth(
        operands=[],
        answer_sympy_form="30",
        sampled_atoms={"shape1": {"atom_type": "PrismAtom", "dimensions_cm": {"width": "5", "height": "6"}}},
    )
    gt["sub_questions"][0]["logic_steps"] = [
        {"operation_name": "multiply", "operands": [], "sympy_expr": "30"}
    ]
    product = make_product(content_problem_text="縦5cmの長方形の面積を求めなさい。")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_warn_when_unattributed_number_present():
    gt = make_ground_truth(operands=[-27, 10], answer_sympy_form="-17")
    product = make_product(
        content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$ (999番の問題)"
    )
    result = check(product, gt)
    assert result.verdict == "WARN"
    assert "999" in str(result.details.get("unknown_numbers"))


def test_allowed_unattributed_numbers_do_not_warn():
    gt = make_ground_truth(operands=[-27, 10], answer_sympy_form="-17")
    # 図番号のような許容数値 (1) はWARNにならない
    product = make_product(
        content_problem_text=r"(1) 次の計算をしなさい $\left(-27\right) + 10$"
    )
    result = check(product, gt)
    assert result.verdict == "PASS"
