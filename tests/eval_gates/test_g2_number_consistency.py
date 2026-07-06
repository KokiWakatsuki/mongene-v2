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


def test_pass_when_required_numbers_only_in_sub_question_prompt_text():
    """実LLM生成でよくある形: content は指示文のみ、実際の式は sub_questions[].prompt_text にある。

    例: g1_l5_calc_mid のような calculation form。
    content_problem_text="次の計算をしなさい。" で式が prompt_text にある場合、
    従来の content 単独スコープでは偽FAILになっていた。
    """
    gt = make_ground_truth(operands=[8, -8], answer_sympy_form="0")
    product = make_product(
        content_problem_text="次の計算をしなさい。",
        prompt_texts=[r"$8 + (-8)$"],
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_string_operand_not_included_in_required_numbers():
    """knowledge form などで operand が文の丸ごと文字列(数値でない)の場合、
    必要数値に混入させてはならない（混入すると必ず欠落FAILになってしまう）。
    """
    gt = make_ground_truth(operands=["次の問いに答えなさい：自然数の性質について"], answer_sympy_form="")
    gt["sub_questions"][0]["answer"] = {"type": "text", "sympy_form": None, "text_form": ""}
    product = make_product(content_problem_text="自然数の性質について説明しなさい。")
    result = check(product, gt)
    assert result.verdict == "N/A"
    assert result.details.get("required") in (None, [])


def test_fail_when_number_missing_even_though_present_in_explanation_only():
    """explanation_text はスコープに含めない。数値が explanation にしかない場合は
    欠落FAILのままであるべき（本文/設問に答えの導出数値が漏れているわけではないと誤判定しない）。
    """
    gt = make_ground_truth(operands=[8, -8], answer_sympy_form="0")
    product = make_product(
        content_problem_text="次の計算をしなさい。",
        prompt_texts=["この問題を解きなさい。"],
        explanation_texts=[r"$8 + (-8) = 0$"],
    )
    result = check(product, gt)
    assert result.verdict == "FAIL"
    assert "missing" in result.details
