"""y_base 推論ルール（§24）"""
from __future__ import annotations

import re

GRADE_BASE = {"中学1年": 10, "中学2年": 30, "中学3年": 55}
DOMAIN_BONUS = {"数と式": 0, "関数": 5, "図形": 8, "データの活用": 3}
COGNITIVE_KEYWORDS = [
    (r"発展|難問|入試", 15),
    (r"複合|融合|総合", 12),
    (r"証明|論理", 10),
    (r"利用|活用|応用", 5),
    (r"計算|解き方", 2),
]


def compute_y_base(
    grade: str,
    domain: str,
    title: str,
    order_in_large_unit: int,
    total_in_large_unit: int,
) -> int:
    y: float = GRADE_BASE.get(grade, 0)
    y += DOMAIN_BONUS.get(domain, 0)
    y += (order_in_large_unit / max(total_in_large_unit, 1)) * 10
    for pattern, points in COGNITIVE_KEYWORDS:
        if re.search(pattern, title):
            y += points
            break
    return round(y)
