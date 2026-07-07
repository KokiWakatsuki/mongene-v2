"""MovingPointAreaVerb（動点による三角形面積の時間変化）

PolygonAtom（底面図形）＋ MovingPointAtom（動点）を結合し、点 P が図形の底辺を
基線として一定の速さ v で高さ方向に進むときの三角形面積 S(t) を **時刻 t の関数**
として求める。query で「特定時刻の面積」「t の式」「最大面積」を切り替える。

**設計（moat・coherence）**:
- モデル: 底辺 = 図形の底辺（vertices[0]→vertices[1]、水平）。点 P は高さ v·t で
  線形に上昇（0 ≤ t ≤ H/v, H=図形の高さ）。S(t) = (1/2)·base·v·t。全て有理数で clean。
- **決定論**（rng を使わない）: base/H を PolygonAtom の頂点から、v を MovingPointAtom の
  velocity から取る。3 つの query invocation が同一の sampled atom を共有するため、
  小問間で動点設定が完全に整合する（同一 P・同一運動）。
- **表示のみでない**: SymPy が実際に面積を計算する（moat）。図（動点）は別途 builder が描く。
"""
from __future__ import annotations

import random
from typing import ClassVar, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

Query = Literal["area_at_t", "area_function", "max_area"]


@register_verb
class MovingPointAreaVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = ["PolygonAtom", "MovingPointAtom"]
    tags: ClassVar[List[str]] = ["moving_point", "measure_geometry", "time_function"]

    def __init__(self, query: Query = "area_function") -> None:
        self.query: Query = query

    # --- helpers -------------------------------------------------------
    @staticmethod
    def _pick_polygon(nouns: Tuple[NounAtom, ...]) -> Optional[NounAtom]:
        for n in nouns:
            if type(n).__name__ == "PolygonAtom":
                return n
        return None

    @staticmethod
    def _pick_mover(nouns: Tuple[NounAtom, ...]) -> Optional[NounAtom]:
        for n in nouns:
            if type(n).__name__ == "MovingPointAtom":
                return n
        return None

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if self._pick_polygon(nouns) is None:
            return False, "PolygonAtom が必要"
        return True, None

    def _geometry(self, nouns: Tuple[NounAtom, ...]):
        polygon = self._pick_polygon(nouns)
        mover = self._pick_mover(nouns)
        verts = list(getattr(polygon, "vertices", []))
        if len(verts) < 3:
            raise ValueError("MovingPointAreaVerb: 頂点が不足")
        # base/H はバウンディングボックスで取る（底辺が水平でない一般三角形でも
        # 「底辺両端＋頂点 P」の実三角形として面積が有理・整合する。矩形/直角三角形/
        # 台形など底辺 y=0 の図形では従来どおり底辺幅=幅・高さ=高さに一致）。
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        base = sympy.simplify(max(xs, key=lambda e: float(e)) - min(xs, key=lambda e: float(e)))
        H = sympy.simplify(max(ys, key=lambda e: float(e)) - min(ys, key=lambda e: float(e)))
        # 速さ v（MovingPointAtom の velocity。無ければ 1）
        v = getattr(mover, "velocity", sympy.Integer(1)) if mover is not None else sympy.Integer(1)
        if v is None or (hasattr(v, "is_zero") and v.is_zero):
            v = sympy.Integer(1)
        return base, H, v

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        base, H, v = self._geometry(nouns)
        t = sympy.Symbol("t", nonnegative=True)
        # S(t) = (1/2) * base * v * t （高さ v*t が線形に増加）
        area_t = sympy.Rational(1, 2) * base * v * t

        travel_time = sympy.simplify(H / v)  # P が最上部に達する時刻

        if self.query == "area_function":
            expr = sympy.simplify(area_t)
            narration = "△の面積 S を時刻 t の式で表す"
            operands = [str(base), str(v)]
        elif self.query == "max_area":
            expr = sympy.simplify(sympy.Rational(1, 2) * base * H)
            narration = "点 P が最上部に達したときの面積の最大値"
            operands = [str(base), str(H)]
        else:  # area_at_t
            t0 = self._pick_t0(travel_time)
            expr = sympy.simplify(area_t.subs(t, t0))
            narration = f"t={sympy.nsimplify(t0)} 秒後の△の面積"
            operands = [str(base), str(v), str(t0)]

        return LogicStep(
            operation_name=f"moving_point_{self.query}",
            operands=operands,
            sympy_expr=sympy.simplify(expr),
            narration_hint=narration,
        )

    @staticmethod
    def _pick_t0(travel_time: sympy.Expr) -> sympy.Expr:
        """0 < t0 < travel_time の「きれいな」時刻を決定論的に選ぶ（運動の途中）。"""
        try:
            half = float(travel_time) / 2.0
        except Exception:
            half = 1.0
        t0_int = int(half)  # 切り捨て
        if t0_int >= 1:
            return sympy.Integer(t0_int)
        # travel_time が小さい場合は正確な半分時刻（有理数）
        return sympy.simplify(travel_time / 2)
