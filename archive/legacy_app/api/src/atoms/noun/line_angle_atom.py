"""LineAngleAtom（§17.1, §18.1）

平行線と交線（錯角・同位角・同側内角）を表す Noun Atom。
known_angle から target_angle_expr を導出する。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_VALID_RELATIONS = {"alternate", "corresponding", "co_interior"}


@register_noun
class LineAngleAtom(NounAtom):
    tags: ClassVar[List[str]] = ["parallel_lines", "angles"]

    def __init__(
        self,
        known_angle: sympy.Expr | None = None,
        relation_type: str = "alternate",
    ) -> None:
        self.known_angle: sympy.Expr = (
            sympy.Integer(60) if known_angle is None else known_angle
        )
        self.relation_type: str = (
            relation_type if relation_type in _VALID_RELATIONS else "alternate"
        )

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "LineAngleAtom":
        custom = constraints.custom or {}
        relation_type: str = str(custom.get("relation_type", "alternate"))
        if relation_type not in _VALID_RELATIONS:
            relation_type = "alternate"
        angle_range = custom.get("angle_range", (30, 150))
        lo = int(angle_range[0])
        hi = int(angle_range[1])
        if lo > hi:
            lo, hi = hi, lo
        if lo < 1:
            lo = 1
        if hi > 179:
            hi = 179

        known = sympy.Integer(rng.randint(lo, hi))
        return LineAngleAtom(known_angle=known, relation_type=relation_type)

    @property
    def target_angle_expr(self) -> sympy.Expr:
        if self.relation_type == "alternate":
            # 錯角は等しい
            return self.known_angle
        if self.relation_type == "corresponding":
            # 同位角は等しい
            return self.known_angle
        if self.relation_type == "co_interior":
            # 同側内角は補角（和が 180）
            return sympy.Integer(180) - self.known_angle
        return self.known_angle

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        return {
            "known_angle": self.known_angle,
            "target_angle": self.target_angle_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        angle_range = custom.get("angle_range", (30, 150))
        lo = int(angle_range[0])
        hi = int(angle_range[1])
        if lo > hi:
            lo, hi = hi, lo
        return max(1, hi - lo + 1)
