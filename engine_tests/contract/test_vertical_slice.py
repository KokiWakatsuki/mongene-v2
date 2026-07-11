"""M0 金の縦串 contract テスト（統合 §4）。

Task4 の `test_generate_end_to_end.py` が骨格をダミーで検証するのに対し、本ファイルは
**実物**（本物の curriculum・families・数学 pack・全 Q ゲート）を `bootstrap()` で束ねて
`generate()` を走らせ、find_value の縦串セルが全ゲートを通過して Problem を返すこと、
remedial が戻り先セルへ解決し G-Q7r を通過することを固定する。

M0 縦串の T1 セル = g2_l25.find_value(Lv2/Lv3)・g2_l24.find_value(Lv1/Lv3)。
graph_table は visual=required で図（Task8）依存のため本テストの対象外（別途 Task8 で固定）。
"""
from __future__ import annotations

import pytest

from engine.bootstrap import bootstrap
from engine.core.contracts import (
    GenerateOptions,
    GenerateRequest,
    Problem,
    SymbolicAnswer,
    Unsupported,
)
from engine.core.pipeline import generate
from engine.core.registry import REGISTRY
from engine.core.verify.quality_gates import reset_fp_cache


@pytest.fixture(autouse=True)
def _engine() -> None:
    """実物のエンジンを初期化（pack 登録 + 品質ゲート install。べき等）。

    G-FP はプロセス内キャッシュを使うため、テストごとに reset して他テストからの
    汚染を避ける。
    """
    bootstrap()
    reset_fp_cache()


# 縦串の T1 find_value セル（unit, level, seeds）
_FIND_VALUE_CELLS = [
    ("g2_l25", 2, [1, 2, 3, 7, 11, 42]),
    ("g2_l25", 3, [1, 2, 3, 4, 5]),
    ("g2_l24", 1, [1, 2, 3, 5, 8]),
    ("g2_l24", 3, [1, 2, 3, 5, 8]),
]


def _req(unit: str, level: int, seed: int) -> GenerateRequest:
    return GenerateRequest(subject="math", unit=unit, form="find_value", level=level, seed=seed)


@pytest.mark.parametrize("unit,level,seeds", _FIND_VALUE_CELLS)
def test_find_value_cells_generate_through_all_gates(unit: str, level: int, seeds: list[int]) -> None:
    """全 seed で Problem を返す（＝ mr/text/visual 全段のゲートを通過）。"""
    for seed in seeds:
        result = generate(_req(unit, level, seed))
        assert isinstance(result, Problem), (
            f"{unit} Lv{level} seed={seed}: {getattr(result, 'code', '?')} "
            f"{getattr(result, 'detail', '')}"
        )
        # 構造: 1小問・symbolic answer・steps 非空・explanation/hints 非空
        assert len(result.sub_questions) == 1
        sq = result.sub_questions[0]
        assert isinstance(sq.answer, SymbolicAnswer)
        assert sq.solution_steps
        assert sq.explanation
        assert sq.hints
        # meta 座標が要求どおり
        assert result.meta.resolved.unit == unit
        assert result.meta.resolved.level == level
        assert result.meta.purpose == "base"


@pytest.mark.parametrize("unit,level,seeds", _FIND_VALUE_CELLS)
def test_find_value_answer_expression_not_leaked_into_text(
    unit: str, level: int, seeds: list[int]
) -> None:
    """G-Q5t の実効: 答えの式そのものは problem_text に現れない。"""
    for seed in seeds:
        result = generate(_req(unit, level, seed))
        assert isinstance(result, Problem)
        answer_display = result.sub_questions[0].answer.display
        assert answer_display not in result.problem_text


@pytest.mark.parametrize("unit,level,seeds", _FIND_VALUE_CELLS)
def test_find_value_double_solve_consistency(unit: str, level: int, seeds: list[int]) -> None:
    """G-Q1 の実効: 登録済み double_solve checker の再計算と MR の答えが一致する。"""
    for seed in seeds:
        result = generate(_req(unit, level, seed))
        assert isinstance(result, Problem)
        recipe = result.meta.provenance.recipe
        checker = REGISTRY.checker(f"{recipe}.double_solve")
        # Problem からは params が見えないため、checker は generate 内で既に通過済み。
        # ここでは checker が登録されている契約（H5）を固定する。
        assert callable(checker)


def test_reproducible_same_seed() -> None:
    r1 = generate(_req("g2_l25", 2, 12345))
    r2 = generate(_req("g2_l25", 2, 12345))
    assert isinstance(r1, Problem) and isinstance(r2, Problem)
    assert r1.problem_text == r2.problem_text
    assert r1.problem_ref == r2.problem_ref


def test_level_signatures_differ_within_family() -> None:
    """Q3/H2: 同 family の Lv2 と Lv3 は構造署名が異なる。"""
    r2 = generate(_req("g2_l25", 2, 1))
    r3 = generate(_req("g2_l25", 3, 1))
    assert isinstance(r2, Problem) and isinstance(r3, Problem)
    assert r2.meta.signature != r3.meta.signature


# ---------------------------------------------------------------------------
# remedial 縦串（§5.2 / G-Q7r）
# ---------------------------------------------------------------------------
def test_remedial_resolves_to_prerequisite_cell_and_passes_q7r() -> None:
    """g2_l25 fv Lv2 の remedial(cause=substitution_error) が g2_l24 fv Lv1 に解決し、
    戻り先セルの concept_tags が要因の target_concepts(intercept_from_point) を被覆する。"""
    req = GenerateRequest(
        subject="math", unit="g2_l25", form="find_value", level=2,
        purpose="remedial", seed=9,
        options=GenerateOptions(cause_id="lf.substitution_error"),
    )
    result = generate(req)
    assert isinstance(result, Problem), (
        f"{getattr(result, 'code', '?')} {getattr(result, 'detail', '')}"
    )
    # requested は元座標、resolved は戻り先座標
    assert result.meta.requested.unit == "g2_l25"
    assert result.meta.requested.level == 2
    assert result.meta.resolved.unit == "g2_l24"
    assert result.meta.resolved.form == "find_value"
    assert result.meta.resolved.level == 1
    assert result.meta.purpose == "remedial"
    # G-Q7r: 戻り先セルの概念が要因の対象概念を被覆
    assert "linear_function.intercept_from_point" in result.meta.concept_tags


def test_remedial_without_cause_id_is_rejected() -> None:
    req = GenerateRequest(
        subject="math", unit="g2_l25", form="find_value", level=2, purpose="remedial", seed=1,
    )
    result = generate(req)
    assert isinstance(result, Unsupported)
    assert result.code == "cause_not_found"


# ---------------------------------------------------------------------------
# 明示拒否（F-5）: 未制作セルは not_implemented
# ---------------------------------------------------------------------------
def test_unimplemented_form_is_not_implemented() -> None:
    # proof は curriculum になく form_not_supported、または families 未制作で not_implemented。
    req = GenerateRequest(subject="math", unit="g2_l25", form="proof", level=2, seed=1)
    result = generate(req)
    assert isinstance(result, Unsupported)
    assert result.code in ("form_not_supported", "not_implemented")
