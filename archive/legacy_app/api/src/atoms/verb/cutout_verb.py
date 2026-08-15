"""CutoutVerb（§22.1 完全実装）

立体 A から立体 B をくり抜く操作。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Optional, Tuple

import sympy
from sympy import Rational

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep


@register_verb
class CutoutVerb(VerbAtom):
    arity: ClassVar = 2
    accepted_noun_types: ClassVar[List[str]] = ["PrismAtom", "PyramidAtom", "SphereAtom"]
    tags: ClassVar[List[str]] = ["cutout_operation", "volume_difference"]

    def validate(self, solid_a: NounAtom, *rest: NounAtom) -> Tuple[bool, Optional[str]]:
        if not rest:
            return False, "CutoutVerb は 2 つの立体を要求"
        solid_b = rest[0]
        if type(solid_a).__name__ not in self.accepted_noun_types:
            return False, f"solid_a の型 {type(solid_a).__name__} は不可"
        if type(solid_b).__name__ not in self.accepted_noun_types:
            return False, f"solid_b の型 {type(solid_b).__name__} は不可"

        symbols_a = solid_a.get_symbols()
        symbols_b = solid_b.get_symbols()
        try:
            a_dims = self._get_bounding_dims(solid_a, symbols_a)
            b_dims = self._get_bounding_dims(solid_b, symbols_b)
        except KeyError as e:
            return False, f"必要な寸法シンボルが不足: {e}"

        for dim_name in ("width", "depth", "height"):
            try:
                a_val = float(sympy.nsimplify(a_dims[dim_name]).evalf())
                b_val = float(sympy.nsimplify(b_dims[dim_name]).evalf())
                if b_val >= a_val:
                    return False, f"solid_b の {dim_name}={b_val} >= solid_a={a_val}"
            except Exception:
                continue

        try:
            vol_a = float(sympy.nsimplify(symbols_a["volume_expr"]).evalf())
            vol_b = float(sympy.nsimplify(symbols_b["volume_expr"]).evalf())
            if vol_b >= vol_a:
                return False, "solid_b の体積が solid_a を超過"
        except Exception:
            pass
        return True, None

    def solve(self, solid_a: NounAtom, solid_b: NounAtom, *, rng: random.Random) -> LogicStep:
        symbols_a = solid_a.get_symbols()
        symbols_b = solid_b.get_symbols()
        remaining_volume = sympy.simplify(symbols_a["volume_expr"] - symbols_b["volume_expr"])
        return LogicStep(
            operation_name="cutout",
            operands=[type(solid_a).__name__, type(solid_b).__name__],
            sympy_expr=remaining_volume,
            narration_hint=f"{type(solid_a).__name__}から{type(solid_b).__name__}をくり抜いた残体積",
        )

    def _get_bounding_dims(self, solid: NounAtom, symbols: dict) -> dict:
        name = type(solid).__name__
        if name == "PrismAtom":
            return {
                "width": symbols["width"],
                "depth": symbols["depth"],
                "height": symbols["height"],
            }
        if name == "PyramidAtom":
            side = symbols.get("base_side", Rational(0))
            return {"width": side, "depth": side, "height": symbols["height"]}
        if name == "SphereAtom":
            r = symbols["radius"]
            return {"width": 2 * r, "depth": 2 * r, "height": 2 * r}
        raise KeyError(f"未対応の立体型: {name}")
