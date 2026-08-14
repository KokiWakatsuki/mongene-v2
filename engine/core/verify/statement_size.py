"""問題文に出る数の大きさを**単位ごとに**測る。`answer_size` の対になる面。

`answer_size` は答えだけを測る。問題文の数には一律の上限を置けない——標本調査の
「76000人」・有効数字の「615cm」・内角の和の「5040°」は、どれも大きくて正しい。

**しかし単位を見れば話が変わる。** 「1辺339cmの正三角形」「対角線174cmのひし形」
「3辺が 55cm, 300cm, 305cm の三角形」は、数そのものではなく
**その単位でその大きさの図形はありえない**という欠陥である（教科書の図形は
数cm〜数十cm。3mの正三角形は作図もできない）。

だから上限は**単位ごと**に置く。上限は実測（`scratchpad/measure_statement_numbers.py`）で
「正しい側の最大」に合わせて決めた。超えるセルは `answer_size` と同じく family YAML に
理由つきで宣言する（`statement_size_max` / `statement_size_reason`）。

**単位の無い裸の数は測らない**（式の係数・番号・度数など、大きさの意味が定まらない）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - 型のためだけ
    from engine.core.contracts import SpecLevel

# 単位ごとの上限。実測の分布から「正しい側の最大」に合わせた。
# 長さ（cm/mm）だけが実際の欠陥源で、ほかは現状の最大に余裕を足した見張り用。
DEFAULT_UNIT_LIMITS: dict[str, int] = {
    # 図形の寸法。教科書の図形は数cm〜数十cm（体育の記録・身長は宣言で通す）
    "cm": 100, "mm": 100,
    # 道のり・広さ（池の周 3000m・空き地 80m² が実測の最大）
    "m": 3000, "km": 200, "m²": 1000, "m³": 100,
    "cm²": 2000, "cm³": 5000,
    # 角。内角の和は 30角形で 5040°（それ以上の多角形は教材に出ない）
    "度": 5040, "°": 5040,
    # 量・値段
    "円": 100000, "g": 5000, "kg": 100, "L": 100, "mL": 2000,
    "%": 100,
    # 時間・回数
    "秒": 300, "分": 300, "分間": 300, "時間": 24, "時": 24, "回": 10000,
    # 個数。**標本調査は母集団が大きいのが正しい**（76000人・49500個）
    "人": 100000, "個": 100000, "匹": 100000, "羽": 100000, "冊": 100000,
    "枚": 1000, "本": 1000, "台": 1000, "袋": 1000, "箱": 1000,
    "点": 100, "問": 100,
}

# 長いものから並べる（`cm²` を `cm` と読み違えない）。
_UNIT_ALT = "|".join(sorted(DEFAULT_UNIT_LIMITS, key=len, reverse=True))
_NUM_UNIT = re.compile(rf"(\d+(?:\.\d+)?)\s*({_UNIT_ALT})")


@dataclass
class UnitHit:
    unit: str
    value: float
    limit: int
    sample: str

    def __str__(self) -> str:  # pragma: no cover - 表示だけ
        return f"{self.value:g}{self.unit}（上限 {self.limit}）:: {self.sample}"


def statement_hits(text: str, limits: dict[str, int]) -> list[UnitHit]:
    """問題文のうち、単位つきの数が上限を超えているもの。"""
    out: list[UnitHit] = []
    for m in _NUM_UNIT.finditer(text):
        value, unit = float(m.group(1)), m.group(2)
        limit = limits.get(unit)
        if limit is not None and value > limit:
            start = max(0, m.start() - 25)
            out.append(UnitHit(unit, value, limit, text[start : m.end() + 20].replace("\n", " ")))
    return out


def limits_for(spec_level: "SpecLevel | Any | None") -> dict[str, int]:
    """そのセルに宣言された単位ごとの上限（無ければ既定）。"""
    declared = getattr(spec_level, "statement_size_max", None) if spec_level else None
    if not declared:
        return dict(DEFAULT_UNIT_LIMITS)
    return dict(DEFAULT_UNIT_LIMITS) | {k: int(v) for k, v in declared.items()}


def statement_is_too_big(text: str, limits: dict[str, int]) -> bool:
    """問題文の数が上限を超えているか（recipe が組み直しを決める判定）。"""
    return bool(statement_hits(text, limits))


__all__ = [
    "DEFAULT_UNIT_LIMITS",
    "UnitHit",
    "limits_for",
    "statement_hits",
    "statement_is_too_big",
]
