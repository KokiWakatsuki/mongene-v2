"""G3 答え正当性ゲートの単体テスト（合成フィクスチャ、LLM不要・SymPyのみ）。"""
from __future__ import annotations

from scripts.eval_gates.g3_answer_correctness import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_pass_when_recomputed_matches_ground_truth():
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-17", answer_text_form="-17")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_recomputed_does_not_match():
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-99", answer_text_form="-99")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_na_for_non_calculation_form():
    gt = make_ground_truth(problem_form="word_problem", answer_sympy_form="24")
    product = make_product(content_problem_text="工場である製品を24個作った。")
    result = check(product, gt)
    assert result.verdict == "N/A"


def test_na_when_no_extractable_expression():
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-17")
    product = make_product(content_problem_text="この問題には数式がありません")
    result = check(product, gt)
    assert result.verdict == "N/A"


def test_pass_with_fraction_expression():
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="1/2", answer_text_form="1/2")
    product = make_product(content_problem_text=r"次の計算をしなさい $\dfrac{1}{4} + \dfrac{1}{4}$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_pass_when_expression_only_in_sub_question_prompt_text():
    """実LLM生成でよくある形: content は指示文のみ、実際の式は prompt_text にある。

    例: g1_l5_calc_mid。content_problem_text="次の計算をしなさい。" で
    式 "$8 + (-8)$" が sub_questions[0].prompt_text にある場合、
    従来の content 単独スコープでは抽出不可 N/A（偽N/A）になっていた。
    """
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="0", answer_text_form="0")
    product = make_product(
        content_problem_text="次の計算をしなさい。",
        prompt_texts=[r"$8 + (-8)$"],
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_expression_in_prompt_text_does_not_match_ground_truth():
    """prompt_text に式があり、再計算結果が ground truth と不一致なら FAIL であるべき。"""
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-99", answer_text_form="-99")
    product = make_product(
        content_problem_text="次の計算をしなさい。",
        prompt_texts=[r"$8 + (-8)$"],
    )
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_na_when_no_expression_in_content_or_any_prompt_text():
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-17")
    product = make_product(
        content_problem_text="次の計算をしなさい。",
        prompt_texts=["この問題には数式がありません"],
    )
    result = check(product, gt)
    assert result.verdict == "N/A"


def test_content_expression_takes_precedence_when_both_present():
    """content にも prompt_text にも式がある場合、content を先に試す（既存挙動の維持確認）。"""
    gt = make_ground_truth(problem_form="calculation", answer_sympy_form="-17", answer_text_form="-17")
    product = make_product(
        content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$",
        prompt_texts=[r"$999 + 1$"],
    )
    result = check(product, gt)
    assert result.verdict == "PASS"
