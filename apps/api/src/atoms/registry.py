"""Atom 自動登録レジストリ（§38.1）"""
from __future__ import annotations

from typing import Dict, List, Type

from apps.api.src.core.abc.atoms import NounAtom, VerbAtom

_NOUN_REGISTRY: Dict[str, Type[NounAtom]] = {}
_VERB_REGISTRY: Dict[str, Type[VerbAtom]] = {}


def register_noun(cls: Type[NounAtom]) -> Type[NounAtom]:
    _NOUN_REGISTRY[cls.__name__] = cls
    return cls


def register_verb(cls: Type[VerbAtom]) -> Type[VerbAtom]:
    _VERB_REGISTRY[cls.__name__] = cls
    return cls


def find_nouns_by_tags(
    required: List[str],
    forbidden: List[str] | None = None,
) -> List[Type[NounAtom]]:
    forbidden = forbidden or []
    result: List[Type[NounAtom]] = []
    for cls in _NOUN_REGISTRY.values():
        cls_tags = getattr(cls, "tags", [])
        if not all(t in cls_tags for t in required):
            continue
        if any(t in cls_tags for t in forbidden):
            continue
        result.append(cls)
    return result


def get_noun_class(name: str) -> Type[NounAtom]:
    if name not in _NOUN_REGISTRY:
        raise KeyError(f"未登録の NounAtom: {name}")
    return _NOUN_REGISTRY[name]


def get_verb_class(name: str) -> Type[VerbAtom]:
    if name not in _VERB_REGISTRY:
        raise KeyError(f"未登録の VerbAtom: {name}")
    return _VERB_REGISTRY[name]


def list_noun_names() -> List[str]:
    return sorted(_NOUN_REGISTRY.keys())


def list_verb_names() -> List[str]:
    return sorted(_VERB_REGISTRY.keys())
