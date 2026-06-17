"""Educational Appropriateness: 禁止語彙リストとの突合（§12.5）"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

_DEFAULT_PATH = Path("master_data/forbidden_words.txt")


def load_forbidden_words(path: Optional[Path] = None) -> list[str]:
    p = path or _DEFAULT_PATH
    if not p.exists():
        return []
    words: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return words


def is_appropriate(text: str, forbidden_words: Optional[Iterable[str]] = None) -> bool:
    """禁止語彙が含まれていなければ True"""
    words = list(forbidden_words) if forbidden_words is not None else load_forbidden_words()
    for w in words:
        if not w:
            continue
        if w in text:
            return False
    return True
