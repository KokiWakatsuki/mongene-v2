"""G1 答え漏洩ゲートの単体テスト（合成フィクスチャ、LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g1_answer_leakage import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_pass_when_answer_not_in_text():
    gt = make_ground_truth(answer_sympy_form="-17", operands=[-27, 10])
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_answer_leaked_regression_24():
    """旧 reports/generated_problems.jsonl の「答え: 24」漏洩を確実に FAIL にできること（spec §3-G1 回帰）。"""
    gt = make_ground_truth(answer_sympy_form="24", answer_text_form="24", operands=[-1, 25])
    product = make_product(
        content_problem_text=r"次の計算をしなさい $\left(-1\right) + 25$" + "\n  答え: $24$"
    )
    result = check(product, gt)
    assert result.verdict == "FAIL"
    assert "24" in str(result.details.get("leaked"))


def test_warn_when_leaked_value_also_matches_operand():
    # 正解が10で、入力オペランドにも10が含まれるケース（誤検出になりうる）
    gt = make_ground_truth(answer_sympy_form="10", answer_text_form="10", operands=[10, 0])
    product = make_product(content_problem_text=r"次の計算をしなさい $10 + 0$")
    result = check(product, gt)
    assert result.verdict == "WARN"


def test_na_when_no_answer_in_ground_truth():
    gt = make_ground_truth()
    gt["sub_questions"] = [{"answer": {}, "logic_steps": []}]
    product = make_product(content_problem_text="何かの問題文")
    result = check(product, gt)
    assert result.verdict == "N/A"


def test_pass_ignores_prompt_text_without_answer():
    gt = make_ground_truth(answer_sympy_form="-17", operands=[-27, 10])
    product = make_product(
        content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$",
        prompt_texts=["(1) 上の式を計算しなさい"],
    )
    result = check(product, gt)
    assert result.verdict == "PASS"
