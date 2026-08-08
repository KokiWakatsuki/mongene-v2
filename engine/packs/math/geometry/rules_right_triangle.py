"""直角三角形・正三角形・二等辺になるための条件の規則カタログ。

対象単元: g2_l42（二等辺になるための条件）・g2_l43（正三角形）・g2_l45（直角三角形の
合同条件）。

**書き方は `rules_congruence.py` に合わせる。** `reason` は教科書の言い回しに固定する
（「直角三角形の斜辺と1つの鋭角がそれぞれ等しい」など）。
"""
from __future__ import annotations

from engine.packs.math.geometry.rule_base import Rule

RIGHT_TRIANGLE_RULES: tuple[Rule, ...] = ()

__all__ = ["RIGHT_TRIANGLE_RULES"]
