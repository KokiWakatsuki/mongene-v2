"""命題の逆・反例セルの double_solve checker（G-Q1・§6.2）。

独立性: params が持つのは命題の型と数値だけで、答え（逆の文・反例）は入っていない。
checker はそこから solver を呼び直して2小問ぶんの答えを組み直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.proposition_converse.double_solve")
def double_solve_proposition_converse(mr: MR) -> list[Solution]:
    p = mr.params
    args = (p["kind"], p["var"], p["a"], p["b"])
    return [
        cast(Solution, REGISTRY.solver("math.proposition_converse_choice")(*args)),
        cast(Solution, REGISTRY.solver("math.proposition_counterexample_choice")(*args)),
    ]
