"""樹形図セルの double_solve checker（G-Q1・§6.2）。

独立性: params が持つのは**場面が与えているもの**（選択肢の名前・取り出す回数・
もとに戻すかどうか）だけで、答え（場合の列・総数）は features 側にしかない。
checker はその3つから solver を呼び直して列挙し直す。
"""
from __future__ import annotations

from typing import cast

from engine.core.contracts import MR, Solution
from engine.core.registry import REGISTRY, register_checker


@register_checker("math.tree_diagram.double_solve")
def double_solve_tree_diagram(mr: MR) -> Solution:
    p = mr.params
    return cast(
        Solution,
        REGISTRY.solver("math.tree_diagram_outcomes")(
            p["items"], p["draws"], p["with_replacement"]
        ),
    )
