"""規則カタログの束ね（docs/proof_engine_design_2026-08-08.md §5）。

**ここに載っている定理だけが証明に使われる。** だから「中学範囲の定理だけを載せる」
ことが、そのまま「出てくる証明が教科書の範囲に収まる」ことの保証になる。
単元を増やすことは、機構を触ることではなく**カタログに定理を足すこと**である。

定理の中身は単元クラスタごとのモジュールにある（このファイルは束ねるだけ）:
  rules_congruence      合同条件・合同な図形の性質・二等辺・対頂角・平行線の錯角
  rules_parallelogram   平行四辺形とその仲間（長方形・ひし形・正方形）
  rules_right_triangle  直角三角形の合同条件・正三角形・二等辺になるための条件
  rules_similarity      相似条件・平行線と線分の比・中点連結定理
  rules_circle          円周角の定理・半円の弧に対する円周角・半径

規則の**探索順は結果に影響しない**（前向き推論は飽和させるので）。ただし同じ深さの
事実が複数の規則から出る場合、先に入ったほうの導出が残る（`deduce.saturate`）ので、
教科書が主に使う規則を前に置いてある。
"""
from __future__ import annotations

from engine.packs.math.geometry.rule_base import Derivation, Rule
from engine.packs.math.geometry.rules_circle import CIRCLE_RULES
from engine.packs.math.geometry.rules_congruence import CONGRUENCE_RULES
from engine.packs.math.geometry.rules_parallelogram import PARALLELOGRAM_RULES
from engine.packs.math.geometry.rules_right_triangle import RIGHT_TRIANGLE_RULES
from engine.packs.math.geometry.rules_similarity import SIMILARITY_RULES

RULES: tuple[Rule, ...] = (
    *CONGRUENCE_RULES,
    *PARALLELOGRAM_RULES,
    *RIGHT_TRIANGLE_RULES,
    *SIMILARITY_RULES,
    *CIRCLE_RULES,
)

RULES_BY_NAME = {r.name: r for r in RULES}

if len(RULES_BY_NAME) != len(RULES):
    raise RuntimeError("規則名が重複している（op 列が衝突して level_sep が壊れる）")


__all__ = ["Derivation", "RULES", "RULES_BY_NAME", "Rule"]
