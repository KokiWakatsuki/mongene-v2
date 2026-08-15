"""答え漏洩検証器（generate-then-verify 反転の骨格）の単体テスト。

- `apps/api/src/core/evaluation/leakage.py` の共有コアを敵対的入力で固める。
- オフライン G1 ゲートとランタイム翻訳器が同一コアを使う（evaluator=verifier）ことを確認。
- LLM は使わない（決定論）。
"""
from __future__ import annotations

import sympy

from apps.api.src.core.evaluation.leakage import (
    detect_leaked_values,
    find_problem_answer_leak,
)
from apps.api.src.core.representation.middle_representation import (
    AnswerObject,
    LogicStep,
    MiddleRepresentation,
    SubQuestion,
)


def _mr(answer_sympy, text_form, operands, prompt_hint="次を求めなさい", form="calculation"):
    step = LogicStep(
        operation_name="op",
        operands=list(operands),
        sympy_expr=answer_sympy,
        narration_hint="",
    )
    return MiddleRepresentation(
        problem_structure_type="X",
        selected_tags=[],
        difficulty_score=10.0,
        problem_form=form,
        sub_questions=[
            SubQuestion(
                label="(1)",
                prompt_hint=prompt_hint,
                logic_steps=[step],
                answer=AnswerObject(
                    type="numeric" if answer_sympy is not None else "proof",
                    sympy_form=answer_sympy,
                    text_form=text_form,
                ),
            )
        ],
        visual_dsl=None,
        seed=1,
        blueprint_id="X",
        blueprint_version="v1",
    )


# ── 共有コア detect_leaked_values ─────────────────────────────────

def test_plain_integer_answer_hard_leak():
    hard, amb = detect_leaked_values("答えは 144 cm² です", ["144"], ["12"])
    assert hard == ["144"]
    assert amb == []


def test_answer_equal_to_operand_is_ambiguous_not_hard():
    # 正解値が入力オペランドと一致するときは誤検出の可能性 → 棄却しない
    hard, amb = detect_leaked_values("縦 12 cm の長方形", ["12"], ["12", "5"])
    assert hard == []
    assert amb == ["12"]


def test_latex_fraction_answer_detected():
    # 正解 1/2 が LaTeX 分数として問題文に出れば検出（正規化突合）
    hard, _ = detect_leaked_values(r"$\dfrac{1}{2}$ を利用して", ["1/2"], ["3"])
    assert hard == ["1/2"]


def test_sign_variant_minus_detected():
    # U+2212 (−) の答えを ASCII マイナス正解値と突合できる
    hard, _ = detect_leaked_values("結果は −3 になる", ["-3"], ["7"])
    assert hard == ["-3"]


def test_numeric_only_skips_non_numeric_answer():
    # proof 等の非数値 text_form は numeric_only で対象外（誤棄却回避）
    hard, amb = detect_leaked_values(
        "△ABC ≡ △DEF を証明せよ", ["△ABC ≡ △DEF"], [], numeric_only=True
    )
    assert hard == [] and amb == []
    # numeric_only=False なら文字列一致で拾える
    hard2, _ = detect_leaked_values(
        "△ABC ≡ △DEF を証明せよ", ["△ABC ≡ △DEF"], [], numeric_only=False
    )
    assert hard2 == ["△ABC ≡ △DEF"]


# ── ランタイム MR ヘルパ find_problem_answer_leak ────────────────

def test_find_leak_in_problem_text():
    mr = _mr(sympy.Integer(144), "144", operands=["12"])
    leaked = find_problem_answer_leak("正方形の面積は 144 cm² である。", [], mr)
    assert leaked == ["144"]


def test_no_leak_when_answer_absent():
    mr = _mr(sympy.Integer(144), "144", operands=["12"])
    leaked = find_problem_answer_leak("一辺 12 cm の正方形の面積を求めなさい。", [], mr)
    assert leaked == []


def test_leak_detected_in_sub_prompt():
    mr = _mr(sympy.Integer(144), "144", operands=["12"])
    leaked = find_problem_answer_leak(
        "次の問いに答えなさい。", ["(1) 144 を答えよ"], mr
    )
    assert leaked == ["144"]


def test_operand_value_in_problem_is_not_leak():
    # 入力値（オペランド 12）は問題文に出て当然 → 漏洩ではない
    mr = _mr(sympy.Integer(144), "144", operands=["12"])
    leaked = find_problem_answer_leak("一辺 12 cm の正方形について。", [], mr)
    assert leaked == []


# ── G1 ゲートと同一コアを使う（evaluator = verifier） ─────────────

def test_g1_gate_uses_shared_core():
    from scripts.eval_gates.g1_answer_leakage import check

    ground_truth = {
        "sub_questions": [
            {
                "answer": {"sympy_form": "144", "text_form": "144"},
                "logic_steps": [{"operands": ["12"], "sympy_expr": "144"}],
            }
        ]
    }
    leaked_product = {"content_problem_text": "面積は 144 である", "sub_questions": []}
    clean_product = {"content_problem_text": "一辺 12 の正方形", "sub_questions": []}
    assert check(leaked_product, ground_truth).verdict == "FAIL"
    assert check(clean_product, ground_truth).verdict == "PASS"
