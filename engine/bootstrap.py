"""エンジン初期化（実装設計 §4.2 統合）— 単一の入口。

`bootstrap()` は
  1. 数学パック（`engine.packs.math`）を import して recipe/solver/frame/template/
     checker をグローバル REGISTRY に登録し、
  2. `install_quality_gates()` でフル Q ゲート（G-SIG/G-FP/G-Q1/G-Q2/G-Q7[+Q7r]/
     G-Q5t/G-GND/G-STY/G-Q5v）を同じ registry に導入する。

CLI（制作ツール Task7）・contract テスト・将来の FastAPI ラッパ（M1）は generate() を
呼ぶ前にこれを一度呼ぶ。install はべき等なので複数回呼んでも安全。

依存規律（§3）: core は本モジュールを import しない（本モジュールが pack と core/verify を
束ねる合流点であり、依存の向きは bootstrap → {packs, core} の一方向）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY, _Registry
from engine.core.verify.quality_gates import install_quality_gates


def bootstrap(registry: _Registry = REGISTRY) -> None:
    """数学パックを登録し、品質ゲートを install する（べき等）。"""
    import engine.packs.math  # noqa: F401  登録の副作用（frame/solver/recipe/template/checker）

    install_quality_gates(registry)


__all__ = ["bootstrap"]
