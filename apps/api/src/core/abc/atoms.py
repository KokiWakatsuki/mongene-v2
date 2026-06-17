"""Noun / Verb Atom の ABC（§12.1）"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple, Union

import sympy


@dataclass
class AtomConstraints:
    difficulty_band: Tuple[int, int]
    forbidden_tags: List[str]
    seed: int
    custom: Dict[str, Any] = field(default_factory=dict)


class NounAtom(ABC):
    tags: ClassVar[List[str]] = []

    @abstractmethod
    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "NounAtom":
        ...

    @abstractmethod
    def get_symbols(self) -> Dict[str, sympy.Expr]:
        ...


class VerbAtom(ABC):
    arity: ClassVar[Union[int, Literal["n-ary"]]] = 2
    accepted_noun_types: ClassVar[List[str]] = []
    tags: ClassVar[List[str]] = []

    @abstractmethod
    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        ...

    @abstractmethod
    def solve(self, *nouns: NounAtom, rng: random.Random):
        """LogicStep を返す（型は circular import を避けるためここでは未指定）"""
        ...
