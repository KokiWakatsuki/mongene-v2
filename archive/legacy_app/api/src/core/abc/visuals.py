"""Visual Component の ABC（§12.1）"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple


@dataclass
class VisualDSL:
    render_type: str
    elements: List[Dict]
    viewport: Tuple[float, float, float, float] = (0.0, 0.0, 10.0, 10.0)
    color_mode: Literal["mono", "color"] = "mono"
    show_grid: bool = False
    show_labels: bool = True


@dataclass
class VisualSlot:
    component_type: str
    compatible_noun_types: List[str] = field(default_factory=list)
    required: bool = True


class VisualComponent(ABC):
    @abstractmethod
    def render(self, dsl: VisualDSL) -> str:
        """SVG 文字列または画像パスを返す。NullRenderer は空文字列を返す。"""
        ...
