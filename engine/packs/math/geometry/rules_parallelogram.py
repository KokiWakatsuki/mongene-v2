"""平行四辺形とその仲間（長方形・ひし形・正方形）の規則カタログ。

対象単元: g2_l46（性質）・g2_l47/l48（なるための条件）・g2_l49（特別な平行四辺形）。

**書き方は `rules_congruence.py` に合わせる。** 各規則は
`(結論の Fact, 前提の Fact の並び)` を yield する関数と、教科書の言い回しに固定した
`reason` を持つ。`reason` はそのまま証明文の根拠欄に出るので、市販の問題集の
模範解答と一字一句そろえること。
"""
from __future__ import annotations

from engine.packs.math.geometry.rule_base import Rule

PARALLELOGRAM_RULES: tuple[Rule, ...] = ()

__all__ = ["PARALLELOGRAM_RULES"]
