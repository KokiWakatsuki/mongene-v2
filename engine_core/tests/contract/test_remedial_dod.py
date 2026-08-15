"""Task9: remedial DoD の機械判定（実装設計 §5.2）。

remedial DoD = 縦串単元の**全誤答要因**について generate が成功し、戻り先セルの
concept_tags が要因の target_concepts を被覆する（G-Q7r）こと。curriculum の
error_causes を単一の正として走査するため、要因を追加すれば自動で被覆対象が増える
（対応表の穴を静的・動的の両面で塞ぐ）。
"""
from __future__ import annotations

import pytest

from engine.core.contracts import Problem
from engine.core.pipeline import generate
from engine.core.verify.quality_gates import reset_fp_cache
from engine.eval._harness import make_env, remedial_cases, remedial_request, unreferenced_causes


@pytest.fixture(scope="module")
def env():  # type: ignore[no-untyped-def]
    e = make_env()
    reset_fp_cache()
    return e


def test_all_causes_have_a_sender_cell(env) -> None:  # type: ignore[no-untyped-def]
    """全誤答要因が、それを cause_tags に持つ実在セル（送り側）から到達可能。"""
    assert unreferenced_causes(env) == [], (
        "送り側セルが存在しない誤答要因がある（対応表の穴）"
    )


def test_remedial_dod_all_causes_resolve_and_pass_q7r(env) -> None:  # type: ignore[no-untyped-def]
    """全要因 × 複数 seed で remedial が Problem を返し、G-Q7r を通る。"""
    cases = remedial_cases(env)
    assert cases, "remedial 対応表が空（縦串の要因が引けていない）"

    for case in cases:
        for seed in (1, 2, 3, 7, 11):
            result = generate(
                remedial_request(case, seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            assert isinstance(result, Problem), (
                f"cause={case.cause_id} seed={seed}: "
                f"{getattr(result, 'code', '?')} {getattr(result, 'detail', '')}"
            )
            # 戻り先座標が要因の remediation と一致
            assert result.meta.resolved.unit == case.remediation_unit
            assert result.meta.resolved.form == case.remediation_form
            assert result.meta.purpose == "remedial"
            # G-Q7r: 戻り先セルの concept_tags ⊇ 要因の target_concepts
            for tc in case.target_concepts:
                assert tc in result.meta.concept_tags, (
                    f"cause={case.cause_id}: 戻り先が target_concept {tc} を被覆しない"
                )


def test_remedial_correspondence_table_is_complete(env) -> None:  # type: ignore[no-untyped-def]
    """対応表: 各要因が (送り側セル → 戻り先座標 → 対象概念) の三つ組で引けること。"""
    cases = remedial_cases(env)
    seen_causes = {c.cause_id for c in cases}
    # curriculum の全要因が対応表に載る（送り側不在で欠落しない）
    all_causes = set(env.curriculum.error_causes)
    assert seen_causes == all_causes, f"対応表に欠落: {all_causes - seen_causes}"
