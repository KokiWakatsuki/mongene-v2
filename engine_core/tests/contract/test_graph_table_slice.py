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


def _states_an_ask(text: str) -> bool:
    """その文のどこかが指示・問いの形で終わっているか。

    engine 側（`t1_template._body_states_the_ask`）とは**別の原理で書く**。
    あちらは活用形（え段／え段＋よ／せよ／なさい）で判定するので、同じ式を
    持ち込むと検算にならない——実際、両方が同じ語尾表を共有していたために
    「並べよ」「読み取れ」「つくれ」が両方から同時に消え、169 小問の二重を
    見逃した。ここは**指示の動詞**で数える。
    """
    import re

    return bool(
        re.search(
            r"(求め|答え|書き|書け|かけ|かき|選べ|選び|示せ|示し|表せ|表し|並べ|並び"
            r"|計算せ|計算し|説明せ|説明し|証明せ|証明し|作図せ|作図し|変形し"
            r"|読み取|つくれ|とれ|解け|何といいます|どれか|いくつ|どちら"
            r"|せよ|なさい|ください)",
            text or "",
        )
    )


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
    # 読み取り問題: 1小問（asked は MR 内部属性で Problem 出力には載らない）。
    # ★**問いが非空であることを守ってはいけない。** 守りたいのは「指示が必ず1つある」
    # ことで、本文が「…を読み取れ。」と言い切っているセルでは問いは空が正しい。
    # 非空だけを見ていたので、本文と問いに同じ指示が二重に出るのを素通りさせていた。
    assert len(result.sub_questions) == 1
    assert _states_an_ask(result.sub_questions[0].prompt_text) ^ _states_an_ask(
        result.problem_text
    ), (
        f"指示は問題文と問いのどちらか一方だけに置くこと: "
        f"problem_text={result.problem_text!r} "
        f"prompt_text={result.sub_questions[0].prompt_text!r}"
    )


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
