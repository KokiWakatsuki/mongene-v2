"""セッション内多様性ローテーション（§12.6.1）"""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Type

from apps.api.src.core.abc.atoms import NounAtom


class DiversityRotation:
    """セッション内で同じ Noun が連続選択されるのを防ぐ"""

    def __init__(self, max_consecutive: int = 3) -> None:
        self.max_consecutive = max_consecutive
        self.recent_picks: Dict[str, int] = defaultdict(int)
        self.last_class: Dict[str, Optional[str]] = {}

    def filter_candidates(
        self,
        slot_name: str,
        candidates: List[Type[NounAtom]],
        last_pick: Optional[str] = None,
    ) -> List[Type[NounAtom]]:
        if last_pick is None:
            last_pick = self.last_class.get(slot_name)
        if last_pick is None:
            return list(candidates)
        if self.recent_picks.get(slot_name, 0) >= self.max_consecutive:
            return [c for c in candidates if c.__name__ != last_pick]
        return list(candidates)

    def record_pick(
        self,
        slot_name: str,
        atom_class_name: str,
        last_pick: Optional[str] = None,
    ) -> None:
        if last_pick is None:
            last_pick = self.last_class.get(slot_name)
        if atom_class_name == last_pick:
            self.recent_picks[slot_name] += 1
        else:
            self.recent_picks[slot_name] = 1
        self.last_class[slot_name] = atom_class_name
