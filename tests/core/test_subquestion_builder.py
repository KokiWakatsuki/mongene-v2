"""SubQuestion builder のテスト"""
from __future__ import annotations

import sympy

from apps.api.src.core.abc.blueprint import SubQuestionStrategy
from apps.api.src.core.representation.middle_representation import LogicStep
from apps.api.src.core.runner.subquestion_builder import build_sub_questions


def _step(name: str, expr: int, narration: str = "") -> LogicStep:
    return LogicStep(
        operation_name=name,
        operands=[],
        sympy_expr=sympy.Integer(expr),
        narration_hint=narration,
    )


def test_single_strategy_returns_one_subquestion() -> None:
    strategy = SubQuestionStrategy(strategy_type="single", final_question="次の計算")
    sqs = build_sub_questions(strategy, sampled_nouns={}, logic_steps_all=[_step("a", 3)])
    assert len(sqs) == 1
    assert sqs[0].label == ""


def test_incremental_strategy_chains_subquestions() -> None:
    strategy = SubQuestionStrategy(
        strategy_type="incremental",
        target_count=2,
        intermediate_outputs=["体積を求める", "面積を求める"],
        final_question="表面積を求める",
    )
    steps = [
        _step("vol", 27, "体積を計算する"),
        _step("area", 9, "面積を計算する"),
    ]
    sqs = build_sub_questions(strategy, sampled_nouns={}, logic_steps_all=steps)
    # intermediates 2 個 + 最終 1 個 = 3
    assert len(sqs) == 3
    assert sqs[0].label == "(1)"
    assert sqs[-1].label == "(3)"
    assert sqs[-1].depends_on == ["(1)", "(2)"]


def test_guided_strategy_returns_hints_plus_final() -> None:
    strategy = SubQuestionStrategy(
        strategy_type="guided",
        target_count=2,
        intermediate_outputs=["体積を求める", "面積を求める"],
        final_question="比を求める",
    )
    steps = [_step("vol", 27, "体積を計算する"), _step("area", 9, "面積を計算する")]
    sqs = build_sub_questions(strategy, sampled_nouns={}, logic_steps_all=steps)
    assert len(sqs) == 3
    assert "ヒント" in sqs[0].prompt_hint
    # ヒントは依存なし、本題は全ヒントに依存
    assert sqs[0].depends_on == []
    assert sqs[-1].depends_on == ["(1)", "(2)"]


def test_ladder_strategy_returns_n_subquestions() -> None:
    strategy = SubQuestionStrategy(
        strategy_type="ladder",
        target_count=3,
        intermediate_outputs=[],
        final_question="次の計算",
    )
    steps = [_step(f"s{i}", i, f"step {i}") for i in range(6)]
    sqs = build_sub_questions(strategy, sampled_nouns={}, logic_steps_all=steps)
    assert len(sqs) == 3
    for i, sq in enumerate(sqs):
        assert sq.label == f"({i + 1})"
        assert "難易度" in sq.prompt_hint
