"""G7 レンダリング健全性ゲートの単体テスト（合成フィクスチャ、LLM不要）。"""
from __future__ import annotations

from scripts.eval_gates.g7_render_sanity import check
from tests.eval_gates.conftest import make_ground_truth, make_product


def test_pass_with_balanced_inline_math():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10$")
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_fail_when_block_math_used():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $$\left(-27\right) + 10$$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_fail_when_dollar_unbalanced():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $\left(-27\right) + 10")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_fail_when_brace_unbalanced():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $\frac{1}{2$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_fail_when_unknown_latex_command():
    gt = make_ground_truth(problem_form="calculation")
    product = make_product(content_problem_text=r"次の計算をしなさい $\foobarcommand{1}{2}$")
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_visual_pass_with_wellformed_svg():
    gt = make_ground_truth(problem_form="visual")
    svg = "<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"
    product = make_product(
        content_problem_text="右の図を見なさい。",
        problem_diagram_url=svg,
    )
    result = check(product, gt)
    assert result.verdict == "PASS"


def test_visual_fail_with_malformed_svg():
    gt = make_ground_truth(problem_form="visual")
    svg = "<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'>"  # 閉じタグ無し
    product = make_product(
        content_problem_text="右の図を見なさい。",
        problem_diagram_url=svg,
    )
    result = check(product, gt)
    assert result.verdict == "FAIL"


def test_visual_fail_when_url_empty():
    gt = make_ground_truth(problem_form="visual")
    product = make_product(content_problem_text="右の図を見なさい。", problem_diagram_url=None)
    result = check(product, gt)
    assert result.verdict == "FAIL"
