"""構成カタログの登録所（docs/proof_engine_design_2026-08-08.md §5）。

構成（作図手順）は**単元クラスタごとのモジュール**に置き、ここに名前で登録する。
family の params の `construction` がこの名前を指す。

**構成の関数は必ず `base` / `angle` / `offset` の3つのパラメータを受ける。**
recipe が同じ手順を別のパラメータで組み直して「図がたまたま見せている性質」を
弾く（`naturalness.accidental_coincidences`）ので、パラメータは**連続的に動かせる**
必要がある。3つに固定してあるのは、ゆらし方を1か所で決めるためである。

  base    長さの目安（recipe が 1/10 して渡す）
  angle   角度の目安（度）
  offset  もう1つの長さ・ずれの目安（recipe が 1/10 して渡す）
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from engine.packs.math.geometry.construct import Construction

Builder = Callable[[dict[str, Any]], Construction]

CONSTRUCTIONS: dict[str, Builder] = {}


def register_construction(name: str) -> Callable[[Builder], Builder]:
    """構成を名前で登録する。名前の重複は、別の単元の図を上書きするので例外にする。"""

    def deco(fn: Builder) -> Builder:
        if name in CONSTRUCTIONS:
            raise RuntimeError(f"構成名が重複している: {name}")
        CONSTRUCTIONS[name] = fn
        return fn

    return deco


# 単元クラスタごとの「使ってよい定理」（質のフィルタが単元違いの証明を弾く）。
# family の params `topic_set` で選ぶ。**単元に無い定理を使う証明を出さない**ための
# 仕掛けなので、広げるときは「その学年でその定理を習っているか」で決めること。
_BASIC = frozenset(
    {"congruence", "congruence_property", "isosceles", "midpoint", "angle", "parallel"}
)

TOPIC_SETS: dict[str, frozenset[str]] = {
    # g2_l39〜l41（合同・二等辺の証明）
    "congruence": _BASIC,
    # g2_l42/l43/l45（二等辺になるための条件・正三角形・直角三角形の合同条件）
    "right_triangle": _BASIC | {"right_triangle", "equilateral"},
    # g2_l46〜l49（平行四辺形とその仲間）。直角三角形の合同条件も既習である。
    "parallelogram": _BASIC | {"right_triangle", "parallelogram", "special_quad"},
    # g3_l41〜l44（相似）。3年なので2年で習った定理はすべて使える。
    "similarity": _BASIC
    | {"right_triangle", "equilateral", "parallelogram", "special_quad", "similarity", "ratio"},
}


def topics_of(name: str) -> frozenset[str]:
    if name not in TOPIC_SETS:
        raise KeyError(f"未知の topic_set: {name}（catalog.TOPIC_SETS に足す）")
    return TOPIC_SETS[name]


__all__ = ["Builder", "CONSTRUCTIONS", "TOPIC_SETS", "register_construction", "topics_of"]
