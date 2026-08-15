"""NullRenderer（§17.3）

描画なし問題用のスタブ。空文字列を返す。
"""
from __future__ import annotations

from apps.api.src.core.abc.visuals import VisualComponent, VisualDSL


class NullRenderer(VisualComponent):
    """描画なし問題用のスタブ"""

    def render(self, dsl: VisualDSL) -> str:
        return ""
