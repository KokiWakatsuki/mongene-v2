"""CircleAngleAtom（§17.1, §18.1）

円周角の環境を表す Noun Atom。中心角・円周角・内接四角形・接弦角・方べきに対応。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class CircleAngleAtom(NounAtom):
    tags: ClassVar[List[str]] = ["circle_angles", "angles"]

    def __init__(
        self,
        central_angle: sympy.Expr | None = None,
        inscribed_quadrilateral: bool = False,
        tangent_chord_angle: bool = False,
        power_of_point: bool = False,
        extra_tags: List[str] | None = None,
    ) -> None:
        # 中心角を基本パラメータとして保持し、円周角 = 中心角 / 2
        self.central_angle: sympy.Expr = (
            sympy.Integer(60) if central_angle is None else central_angle
        )
        self.inscribed_quadrilateral: bool = inscribed_quadrilateral
        self.tangent_chord_angle: bool = tangent_chord_angle
        self.power_of_point: bool = power_of_point
        # tags はインスタンス属性として動的に拡張
        base_tags = list(type(self).tags)
        if extra_tags:
            for t in extra_tags:
                if t not in base_tags:
                    base_tags.append(t)
        self.tags: List[str] = base_tags

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "CircleAngleAtom":
        custom = constraints.custom or {}
        inscribed_quadrilateral: bool = bool(custom.get("inscribed_quadrilateral", False))
        tangent_chord_angle: bool = bool(custom.get("tangent_chord_angle", False))
        power_of_point: bool = bool(custom.get("power_of_point", False))

        # 中心角は偶数（円周角を整数にするため）
        # 2 〜 358 度の偶数
        central = sympy.Integer(rng.randint(1, 179) * 2)

        extra: List[str] = []
        if inscribed_quadrilateral:
            extra.append("inscribed_quadrilateral")
        if tangent_chord_angle:
            extra.append("tangent_chord")
        if power_of_point:
            extra.append("power_of_point")

        return CircleAngleAtom(
            central_angle=central,
            inscribed_quadrilateral=inscribed_quadrilateral,
            tangent_chord_angle=tangent_chord_angle,
            power_of_point=power_of_point,
            extra_tags=extra,
        )

    @property
    def inscribed_angle_expr(self) -> sympy.Expr:
        # 円周角 = 中心角 / 2
        return sympy.Rational(1, 2) * self.central_angle

    @property
    def central_angle_expr(self) -> sympy.Expr:
        return self.central_angle

    @property
    def opposite_inscribed_angle_expr(self) -> sympy.Expr:
        """内接四角形の対角（和が 180）"""
        return sympy.Integer(180) - self.inscribed_angle_expr

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        inscribed = self.inscribed_angle_expr
        return {
            "inscribed_angle": inscribed,
            "inscribed_angle_expr": inscribed,  # FindAngleVerb が参照するキー
            "central_angle": self.central_angle_expr,
            "opposite_inscribed_angle": self.opposite_inscribed_angle_expr,
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        # 中心角の偶数：179 通り
        base = 179
        custom = constraints.custom or {}
        flags = sum(
            1
            for k in ("inscribed_quadrilateral", "tangent_chord_angle", "power_of_point")
            if bool(custom.get(k, False))
        )
        return base * (flags + 1)
