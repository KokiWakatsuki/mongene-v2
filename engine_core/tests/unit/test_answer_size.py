"""答えの大きさの測り方（`engine.core.verify.answer_size`）の単体テスト。

この関数は **recipe（組み直しの判定）と eval（歯止め）の両方**が通る単一の真実なので、
正規表現がずれると「生成側が通す形」と「検査側が落とす形」が食い違う。
実際に踏んだ形（単位の中の `/`・かっこの分母・平方因数の残り）を固定する。
"""
from __future__ import annotations

import pytest

from engine.core.contracts import SpecLevel
from engine.core.verify.answer_size import (
    DEFAULT_LIMITS,
    answer_is_too_big,
    answer_magnitudes,
    limits_for,
    squarefree_part,
)


@pytest.mark.parametrize(
    ("text", "den", "num", "rad"),
    [
        ("-107/12", 12, 107, 0),
        ("671/1296", 1296, 671, 0),
        ("√1202 cm", 0, 0, 1202),
        ("2√385/11", 11, 385, 385),          # 分母はかっこ無しでも拾う
        ("x = (2 - 3√2)/2", 2, 0, 2),        # かっこの分母（分子は式なので測らない）
        ("13.5", 0, 0, 0),                   # 小数は分数ではない
        ("112.5 cm³", 0, 0, 0),
        ("分速 80 m/分", 0, 0, 0),             # 単位の中の `/` は分数ではない
        ("(1) 2√7 ／ (2) 5.3", 0, 0, 7),
        ("正の数", 0, 0, 0),
    ],
)
def test_answer_magnitudes(text: str, den: int, num: int, rad: int) -> None:
    m = answer_magnitudes(text)
    assert (m.denominator, m.numerator, m.radicand) == (den, num, rad)


def test_default_limits_reject_and_accept() -> None:
    # 既定（分母12・分子100・根号の中60）で落ちる形・通る形。
    assert answer_is_too_big("1/1728", DEFAULT_LIMITS)
    assert answer_is_too_big("√1202 cm", DEFAULT_LIMITS)
    assert answer_is_too_big("-107/12", DEFAULT_LIMITS)  # 分子100超（実際に落ちた形）
    assert answer_is_too_big("-97/12", DEFAULT_LIMITS) is False
    assert answer_is_too_big("4√26 cm", DEFAULT_LIMITS) is False
    assert answer_is_too_big("20000個", DEFAULT_LIMITS) is False  # 整数は測らない


def test_declared_limit_overrides_default() -> None:
    level = SpecLevel(
        level=3, signature="s", recipe="r",
        answer_size_max={"denominator": 1296, "numerator": 1296},
        answer_size_reason="確率の分母は場合の数そのもの",
    )
    limits = limits_for(level)
    assert limits["denominator"] == 1296
    assert limits["radicand"] == DEFAULT_LIMITS["radicand"]  # 宣言しない項目は既定のまま
    assert answer_is_too_big("671/1296", limits) is False


def test_declaration_requires_reason() -> None:
    with pytest.raises(ValueError, match="answer_size_reason"):
        SpecLevel(level=1, signature="s", recipe="r", answer_size_max={"denominator": 99})


def test_squarefree_part() -> None:
    # 根号の中は「辺を小さくすること」では下がらない＝開ける形かどうかで決まる。
    assert squarefree_part(362) == 362        # 7,12,13 の直方体の対角線
    assert squarefree_part(169) == 1          # 3,4,12 なら根号が消える
    assert squarefree_part(416) == 26         # √416 = 4√26
    assert squarefree_part(0) == 0
