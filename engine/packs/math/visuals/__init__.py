"""数学パックの visual ビルダ群（実装設計 §6.4・Task8）。

サブモジュールを import することで `@register_visual` の副作用を発火させ、
registry に登録する。
"""
from __future__ import annotations

from engine.packs.math.visuals import graph  # noqa: F401  (register_visual の副作用のため import)
from engine.packs.math.visuals import number_line  # noqa: F401  (register_visual の副作用のため import)

__all__: list[str] = []
