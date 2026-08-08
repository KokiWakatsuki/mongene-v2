"""平行四辺形とその仲間の構成カタログ（g2_l46/l47/l48/l49）。

**平行四辺形の性質を証明する単元では、平行だけを仮定する構成を使う。**
`constructions_congruence.py` の "parallelogram" は平行移動で作るので、対辺の長さが
等しいことが仮定に入ってしまう——それは g2_l46 で証明したいことそのものである。

登録は `@register_construction("名前")`。関数は `base` / `angle` / `offset` を受ける
（recipe が同じ手順を別のパラメータで組み直して、図がたまたま見せている性質を弾く）。
"""
from __future__ import annotations

from typing import Any  # noqa: F401  （構成を足すときに使う）

from engine.packs.math.geometry.catalog import register_construction  # noqa: F401
from engine.packs.math.geometry.construct import Construction  # noqa: F401
