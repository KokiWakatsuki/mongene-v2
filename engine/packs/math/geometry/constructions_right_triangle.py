"""直角三角形・正三角形・二等辺になるための条件の構成カタログ（g2_l42/l43/l45）。

登録は `@register_construction("名前")`。関数は `base` / `angle` / `offset` を受ける
（recipe が同じ手順を別のパラメータで組み直して、図がたまたま見せている性質を弾く）。
"""
from __future__ import annotations

from typing import Any  # noqa: F401  （構成を足すときに使う）

from engine.packs.math.geometry.catalog import register_construction  # noqa: F401
from engine.packs.math.geometry.construct import Construction  # noqa: F401
