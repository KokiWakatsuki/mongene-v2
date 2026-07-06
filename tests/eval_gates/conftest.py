"""eval_gates 単体テスト共通フィクスチャ。

`/problems/inspect`（ground truth）と `/problems/generate` の
`ProblemGenerationResponse`（product）の実データ形状に合わせた合成フィクスチャを提供する。
実LLM・実コーパスは使わない。
"""
from __future__ import annotations

from typing import Any

import pytest


def make_ground_truth(
    *,
    lesson_id: str = "g1_l1",
    problem_form: str = "calculation",
    answer_sympy_form: str = "-17",
    answer_text_form: str = "-17",
    operands: list[Any] | None = None,
    sampled_atoms: dict[str, Any] | None = None,
    extra_sub_question_answers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """`/problems/inspect` の返り値と同じ形の ground truth dict を作る。"""
    if operands is None:
        operands = [-27, 10]
    sub_questions = [
        {
            "label": "(1)",
            "answer": {
                "type": "numeric",
                "sympy_form": answer_sympy_form,
                "text_form": answer_text_form,
            },
            "logic_steps": [
                {
                    "operation_name": "add",
                    "operands": operands,
                    "sympy_expr": answer_sympy_form,
                    "narration_hint": "",
                }
            ],
        }
    ]
    for extra in extra_sub_question_answers or []:
        sub_questions.append(extra)

    return {
        "lesson_id": lesson_id,
        "lesson_title": "テストレッスン",
        "blueprint_id": "BasicCalculationStructure",
        "problem_form": problem_form,
        "difficulty_score": 10.0,
        "selected_tags": [],
        "seed": 1,
        "sampled_atoms": sampled_atoms or {},
        "sub_questions": sub_questions,
    }


def make_product(
    *,
    content_problem_text: str = r"次の計算をしなさい $\left(-27\right) + 10$",
    prompt_texts: list[str] | None = None,
    explanation_texts: list[str] | None = None,
    problem_diagram_url: str | None = None,
) -> dict[str, Any]:
    """`ProblemGenerationResponse` と同じ形の product dict を作る。"""
    prompt_texts = prompt_texts if prompt_texts is not None else [""]
    explanation_texts = explanation_texts if explanation_texts is not None else [""]
    sub_questions = []
    for i, prompt in enumerate(prompt_texts):
        sub_questions.append(
            {
                "label": f"({i + 1})",
                "prompt_text": prompt,
                "answer": {"type": "numeric", "sympy_form": None, "text_form": ""},
                "explanation_text": explanation_texts[i] if i < len(explanation_texts) else "",
            }
        )
    return {
        "content_problem_text": content_problem_text,
        "sub_questions": sub_questions,
        "visuals": {"problem_diagram_url": problem_diagram_url},
        "metadata": {
            "base_difficulty": 10,
            "adjustment_delta": 0,
            "used_atoms": [],
            "seed": 1,
            "blueprint_id": "BasicCalculationStructure",
            "blueprint_version": "1.0",
        },
    }


@pytest.fixture
def gt_factory():
    return make_ground_truth


@pytest.fixture
def product_factory():
    return make_product
