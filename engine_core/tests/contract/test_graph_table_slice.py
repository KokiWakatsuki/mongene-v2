"""Task8: graph_table 縦串 contract テスト（実物エンジンで図つきセルが全ゲートを通過）。

`math.g2_l25.graph_table` Lv2（visual=required）が `bootstrap()` 後に複数 seed で
Problem を返し、visual_svg が生成され、答え座標が図・本文に漏洩しないことを固定する。
"""
from __future__ import annotations

import re

import pytest

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Problem
from engine.core.pipeline import generate
from engine.core.verify.quality_gates import reset_fp_cache


@pytest.fixture(autouse=True)
def _engine() -> None:
    bootstrap()
    reset_fp_cache()


def _req(seed: int) -> GenerateRequest:
    return GenerateRequest(subject="math", unit="g2_l25", form="graph_table", level=2, seed=seed)


@pytest.mark.parametrize("seed", [1, 2, 3, 5, 8, 13, 21])
def test_graph_table_generates_with_figure(seed: int) -> None:
    result = generate(_req(seed))
    assert isinstance(result, Problem), (
        f"seed={seed}: {getattr(result, 'code', '?')} {getattr(result, 'detail', '')}"
    )
    # visual=required なので図が生成される
    assert result.visual_svg is not None
    assert result.visual_svg.startswith("<svg")
    # 読み取り問題: 1小問・問い文あり（asked は MR 内部属性で Problem 出力には載らない）
    assert len(result.sub_questions) == 1
    assert result.sub_questions[0].prompt_text


@pytest.mark.parametrize("seed", [1, 2, 3, 5, 8, 13, 21])
def test_graph_table_answer_not_leaked(seed: int) -> None:
    """答えの座標ペアが本文にも図の点ラベルにも現れない（G-Q5t / G-Q5v の実効）。"""
    result = generate(_req(seed))
    assert isinstance(result, Problem)
    answer_display = result.sub_questions[0].answer.display  # 例 "(0, 3), (3, 6)"
    # 本文に答え座標ペアが無い
    assert answer_display not in result.problem_text
    # 図の <text> は軸目盛の単独数値のみ（カンマを含む座標表記が無い）
    svg = result.visual_svg or ""
    for t in re.findall(r"<text[^>]*>([^<]*)</text>", svg):
        assert "," not in t


def test_graph_table_no_false_positive_over_seed_range() -> None:
    """連続 seed 全域で生成不能が出ない（cherry-pick で偽陽性を隠さないための回帰防止）。

    かつて G-Q5t が答え座標の数値とテンプレ「2つの格子点」の "2" を衝突させ約19%の
    seed を偽陽性で弾いていた（助数詞除外で解消）。生成不能0（N-5）を広域で固定する。
    """
    fails = []
    for seed in range(1, 61):
        r = generate(_req(seed))
        if not isinstance(r, Problem):
            fails.append((seed, getattr(r, "code", "?"), getattr(r, "detail", "")))
    assert not fails, f"生成不能が発生: {fails[:5]}"


def test_graph_table_reproducible() -> None:
    r1 = generate(_req(777))
    r2 = generate(_req(777))
    assert isinstance(r1, Problem) and isinstance(r2, Problem)
    assert r1.problem_ref == r2.problem_ref
    assert r1.visual_svg == r2.visual_svg
