"""相似の規則カタログ（相似条件・相似の性質・平行線と線分の比・中点連結定理）。

対象単元: g3_l41（相似条件）・g3_l42/l43（平行線と線分の比）・g3_l44（中点連結定理）・
exam_l6（融合問題の中で相似を示す）。

**書き方は `rules_congruence.py` に合わせる。** `reason` は教科書の言い回しに固定する
（「2組の角がそれぞれ等しい」など）。
"""
from __future__ import annotations

from engine.packs.math.geometry.rule_base import Rule

SIMILARITY_RULES: tuple[Rule, ...] = ()

__all__ = ["SIMILARITY_RULES"]
