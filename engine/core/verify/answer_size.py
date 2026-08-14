"""答えの大きさ（分母・分子・根号の中）の測り方。**単一の真実**。

`engine.eval.answer_size`（歯止め）と recipe（組み直しの判定）が、同じ関数を見る。
別々に持つと「生成側が通す形」と「検査側が落とす形」がずれて、通らない seed が
出続けるか、逆に検査が空振りする。

## なぜ問題文の数ではなく答えを測るのか

標本調査の「20000個」・有効数字の「9780」のように、**問題文の数は大きくて正しい**
ものがある。一方、生徒は答えをノートに書き写して丸をつけるので、`-107/12` や
`√1202` は計算が合っていても中学の答えとして成り立たない。

測るのは3つだけ。**整数そのものの大きさは測らない**（答えが `20000個` になるのは
正しく、上限を置くと単元ごとの宣言だらけになって歯止めの意味が消える）。

| 何 | なぜ |
|---|---|
| 分母 | 約分後の分母。ここが大きいと筆算で扱えない |
| 分子 | 仮分数の分子 |
| 根号の中 | 平方因数を外に出しきったあとの数 |

## 上限の宣言

既定を超えてよい単元は family YAML の `answer_size_max` に理由つきで書く
（`SpecLevel`）。確率は約分した分数で答えるのが作法なので、**分母が大きいのが正しい**
（17個から2個で 136 分の、7通りを3回くり返して 343 分の）。そこを一律の上限で落とすと、
通すために場面を作り替えることになる——`dup_rate` で「正348角形」を生んだのと同じ失敗。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - 型のためだけ（core は pack に依存しない）
    from engine.core.contracts import SpecLevel

# 既定の上限。単元ごとの実測（`scratchpad/measure_answer_size.py` ／
# `python -m engine.eval.answer_size --seeds 30`）から、「教材として書き写せる形」の
# 側の最大に合わせて決めた。超える単元は YAML で宣言する。
DEFAULT_LIMITS: dict[str, int] = {"denominator": 12, "numerator": 100, "radicand": 60}

# `3/4`・`-21/10`。前が数字や小数点なら桁の切れ目なので拾わない。
_FRACTION = re.compile(r"(?<![\d.])(\d+)\s*/\s*(\d+)(?![\d.])")
# `(2 - 3√2)/2`・`(-3√13 - 3√3)/5` の分母。分子は式なので測らない。
_PAREN_DENOM = re.compile(r"\)\s*/\s*(\d+)(?![\d.])")
# `√44`・`3√7`。
_RADICAL = re.compile(r"√\s*(\d+)")
# 単位の中の `/`（分数ではない）。`km/h` `m/分` `円/個` など。
_UNIT_SLASH = re.compile(r"\d\s*(?:[a-zA-Zｍ-ｚ㎡㎥]+|[一-龥]+)\s*/")


def squarefree_part(n: int) -> int:
    """√n を簡単にしたあとの根号の中（平方因数を外に出しきった残り）。

    根号の中は**辺を小さくすることでは下がらない**。7,12,13 の直方体は辺が小さくても
    対角線が √362 になり、3,4,12 なら √169 = 13 で根号が消える。だから上限は
    「辺の大きさ」ではなく「開ける形か」を選ぶ＝定義域を狭めずに効く。
    """
    if n <= 0:
        return 0
    r = n
    for d in range(2, math.isqrt(n) + 1):
        while r % (d * d) == 0:
            r //= d * d
    return r


@dataclass
class AnswerMagnitudes:
    denominator: int = 0
    numerator: int = 0
    radicand: int = 0
    sample: str = ""

    def over(self, limits: dict[str, int]) -> list[str]:
        """上限を超えた項目の名前（超えていなければ空）。"""
        return [name for name, limit in limits.items() if getattr(self, name, 0) > limit]


def answer_magnitudes(text: str) -> AnswerMagnitudes:
    """答えの表示文字列から、分母・分子・根号の中の最大を取る。"""
    m = AnswerMagnitudes(sample=text[:80])
    for num, den in _FRACTION.findall(text):
        m.numerator = max(m.numerator, int(num))
        m.denominator = max(m.denominator, int(den))
    for den in _PAREN_DENOM.findall(text):
        m.denominator = max(m.denominator, int(den))
    for rad in _RADICAL.findall(text):
        m.radicand = max(m.radicand, int(rad))
    if _UNIT_SLASH.search(text):
        # 単位の中の `/` を分数と取り違えている恐れがあるので、分数側は捨てる。
        m.numerator = m.denominator = 0
        for den in _PAREN_DENOM.findall(text):
            m.denominator = max(m.denominator, int(den))
    return m


def limits_for(spec_level: "SpecLevel | Any | None") -> dict[str, int]:
    """そのセルに宣言された上限（無ければ既定）。"""
    declared = getattr(spec_level, "answer_size_max", None) if spec_level else None
    if not declared:
        return dict(DEFAULT_LIMITS)
    return dict(DEFAULT_LIMITS) | {k: int(v) for k, v in declared.items()}


def answer_is_too_big(display: str, limits: dict[str, int]) -> bool:
    """答えの表示が上限を超えているか（recipe が組み直しを決める判定）。"""
    return bool(answer_magnitudes(display).over(limits))


__all__ = [
    "DEFAULT_LIMITS",
    "AnswerMagnitudes",
    "answer_is_too_big",
    "answer_magnitudes",
    "limits_for",
    "squarefree_part",
]
