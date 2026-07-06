"""ConstructGeometryVerb（§18.2）

作図手順を SymPy ベクトル計算ベースで構築する。各ステップは
{"step": N, "action": ..., "params": {...}, "sympy_result": Expr} 形式。
"""
from __future__ import annotations

import json
import random
from typing import Any, ClassVar, Dict, List, Literal, Optional, Tuple

import sympy

from apps.api.src.atoms.registry import register_verb
from apps.api.src.core.abc.atoms import NounAtom, VerbAtom
from apps.api.src.core.representation.middle_representation import LogicStep

ConstructionType = Literal[
    "perp_bisector", "angle_bisector", "perpendicular", "tangent", "copy_length"
]


@register_verb
class ConstructGeometryVerb(VerbAtom):
    arity: ClassVar = "n-ary"
    accepted_noun_types: ClassVar[List[str]] = [
        "PointAtom",
        "PolygonAtom",
        "CircleAtom",
        "LineAngleAtom",
    ]
    tags: ClassVar[List[str]] = ["construction"]

    def __init__(self, construction_type: ConstructionType = "perp_bisector") -> None:
        self.construction_type: ConstructionType = construction_type

    def validate(self, *nouns: NounAtom) -> Tuple[bool, Optional[str]]:
        if not nouns:
            return False, "少なくとも 1 つの Atom が必要"
        for n in nouns:
            if type(n).__name__ not in self.accepted_noun_types:
                return False, f"{type(n).__name__} は ConstructGeometryVerb に渡せない"

        # 各 construction_type の必要 Atom 数チェック
        need = {
            "perp_bisector": 2,    # 線分の両端点
            "angle_bisector": 3,   # 頂点 + 両辺上の点
            "perpendicular": 2,    # 直線上の点 + 直線方向の参照点
            "tangent": 2,          # 円 + 外部点
            "copy_length": 2,      # 移すべき長さの端点
        }
        n_needed = need[self.construction_type]
        if len(nouns) < n_needed:
            return False, f"{self.construction_type} には {n_needed} 個の Atom 必要"

        # perp_bisector / perpendicular / copy_length: 2点が一致すると退化（True になる）
        if self.construction_type in ("perp_bisector", "perpendicular", "copy_length"):
            ax, ay = self._get_xy(nouns[0])
            bx, by = self._get_xy(nouns[1])
            import sympy as _sp
            ab2 = (bx - ax) ** 2 + (by - ay) ** 2
            if _sp.simplify(ab2) == 0:
                return False, "2点が一致しているため作図が退化します"

        return True, None

    def solve(self, *nouns: NounAtom, rng: random.Random) -> LogicStep:
        if self.construction_type == "perp_bisector":
            steps, result_expr = self._perp_bisector(nouns)
        elif self.construction_type == "angle_bisector":
            steps, result_expr = self._angle_bisector(nouns)
        elif self.construction_type == "perpendicular":
            steps, result_expr = self._perpendicular(nouns)
        elif self.construction_type == "tangent":
            steps, result_expr = self._tangent(nouns)
        else:  # copy_length
            steps, result_expr = self._copy_length(nouns)

        return LogicStep(
            operation_name=f"construct_{self.construction_type}",
            operands=[
                type(n).__name__ for n in nouns
            ] + [json.dumps(steps, ensure_ascii=False, default=str)],
            sympy_expr=result_expr,
            narration_hint=f"{self.construction_type} の作図（{len(steps)} ステップ）",
        )

    def _get_xy(self, atom: NounAtom) -> Tuple[sympy.Expr, sympy.Expr]:
        s = atom.get_symbols()
        return s.get("x", sympy.Integer(0)), s.get("y", sympy.Integer(0))

    def _perp_bisector(self, nouns: Tuple[NounAtom, ...]) -> Tuple[List[Dict], sympy.Expr]:
        """線分 AB の垂直二等分線
        ステップ:
          1. A を中心に半径 |AB| の円を描く
          2. B を中心に半径 |AB| の円を描く
          3. 2 円の交点を結ぶ
        結果: 直線の方程式 (x - mx) * (x2-x1) + (y - my) * (y2-y1) = 0
        """
        ax, ay = self._get_xy(nouns[0])
        bx, by = self._get_xy(nouns[1])
        ab2 = (bx - ax) ** 2 + (by - ay) ** 2
        ab = sympy.sqrt(ab2)
        mx = (ax + bx) / 2
        my = (ay + by) / 2

        x, y = sympy.symbols("x y", real=True)
        line_expr = sympy.expand((x - mx) * (bx - ax) + (y - my) * (by - ay))
        equation = sympy.Eq(line_expr, 0)

        steps = [
            {"step": 1, "action": "draw_circle", "params": {"center": [str(ax), str(ay)], "radius": str(ab)}},
            {"step": 2, "action": "draw_circle", "params": {"center": [str(bx), str(by)], "radius": str(ab)}},
            {"step": 3, "action": "connect_intersections", "params": {"midpoint": [str(mx), str(my)]}},
        ]
        return steps, equation

    def _angle_bisector(self, nouns: Tuple[NounAtom, ...]) -> Tuple[List[Dict], sympy.Expr]:
        """頂点 V と両辺の参照点 A, B から角の二等分線
        ステップ:
          1. V を中心に任意半径の弧を描き、両辺との交点 A', B' を得る
          2. A', B' を中心に等しい半径の円を描く
          3. V とその交点を結ぶ
        結果: 二等分線の方向ベクトル
        """
        vx, vy = self._get_xy(nouns[0])
        ax, ay = self._get_xy(nouns[1])
        bx, by = self._get_xy(nouns[2])

        # 単位ベクトル v→a, v→b
        va = sympy.Matrix([ax - vx, ay - vy])
        vb = sympy.Matrix([bx - vx, by - vy])
        norm_a = sympy.sqrt(va.dot(va))
        norm_b = sympy.sqrt(vb.dot(vb))
        ua = va / norm_a
        ub = vb / norm_b
        bisector_dir = ua + ub  # 単位ベクトルの和が二等分線方向

        x, y = sympy.symbols("x y", real=True)
        # パラメータ表示: (x, y) = (vx, vy) + t * bisector_dir
        # 直線方程式: bisector_dir.y * (x - vx) - bisector_dir.x * (y - vy) = 0
        line_expr = sympy.simplify(
            bisector_dir[1] * (x - vx) - bisector_dir[0] * (y - vy)
        )
        equation = sympy.Eq(line_expr, 0)

        steps = [
            {"step": 1, "action": "draw_arc_from_vertex", "params": {"center": [str(vx), str(vy)]}},
            {"step": 2, "action": "draw_circles_from_arc_points"},
            {"step": 3, "action": "connect_vertex_to_intersection", "params": {"direction": [str(bisector_dir[0]), str(bisector_dir[1])]}},
        ]
        return steps, equation

    def _perpendicular(self, nouns: Tuple[NounAtom, ...]) -> Tuple[List[Dict], sympy.Expr]:
        """点 P を通り直線 PQ に垂直な直線
        ステップ:
          1. P を中心に任意半径で直線と 2 交点 A, B を作る
          2. A, B の垂直二等分線（P を通る）
        """
        px, py = self._get_xy(nouns[0])
        qx, qy = self._get_xy(nouns[1])

        # 直線 PQ の方向ベクトル
        dx = qx - px
        dy = qy - py
        # 垂直方向: (-dy, dx)
        x, y = sympy.symbols("x y", real=True)
        line_expr = sympy.expand(dx * (x - px) + dy * (y - py))  # PQ に垂直な直線は dot product=0
        equation = sympy.Eq(line_expr, 0)

        steps = [
            {"step": 1, "action": "draw_circle_around_point", "params": {"center": [str(px), str(py)]}},
            {"step": 2, "action": "construct_perp_bisector_of_segment"},
            {"step": 3, "action": "result", "params": {"normal_vec": [str(-dy), str(dx)]}},
        ]
        return steps, equation

    def _tangent(self, nouns: Tuple[NounAtom, ...]) -> Tuple[List[Dict], sympy.Expr]:
        """円外の点 P から円 (center C, radius r) への接線
        ステップ:
          1. PC の中点 M を求める
          2. M を中心に半径 |PC|/2 の円を描き、もとの円との交点 T を求める
          3. P と T を結ぶ
        接線方向: (PT)
        """
        circle = nouns[0].get_symbols()
        cx = circle.get("center_x", sympy.Integer(0))
        cy = circle.get("center_y", sympy.Integer(0))
        r = circle.get("radius", sympy.Integer(1))

        px, py = self._get_xy(nouns[1])
        pc2 = (cx - px) ** 2 + (cy - py) ** 2
        # 接線の長さ: sqrt(|PC|^2 - r^2)
        tangent_length = sympy.sqrt(pc2 - r ** 2)
        mx = (cx + px) / 2
        my = (cy + py) / 2

        x, y = sympy.symbols("x y", real=True)
        # 接点を T とすると、CT ⊥ PT。簡略化のため接線長さを result_expr に
        equation = tangent_length

        steps = [
            {"step": 1, "action": "find_midpoint_of_PC", "params": {"M": [str(mx), str(my)]}},
            {"step": 2, "action": "draw_circle", "params": {"center": [str(mx), str(my)], "radius": str(sympy.sqrt(pc2) / 2)}},
            {"step": 3, "action": "intersect_with_target_circle"},
            {"step": 4, "action": "connect_P_to_T", "params": {"tangent_length": str(tangent_length)}},
        ]
        return steps, equation

    def _copy_length(self, nouns: Tuple[NounAtom, ...]) -> Tuple[List[Dict], sympy.Expr]:
        """線分 AB の長さを別の点 C を始点として写す
        ステップ:
          1. コンパスで |AB| を測る
          2. C を中心に半径 |AB| の弧を引く
        結果: |AB| の長さ
        """
        ax, ay = self._get_xy(nouns[0])
        bx, by = self._get_xy(nouns[1])
        length = sympy.sqrt((bx - ax) ** 2 + (by - ay) ** 2)

        steps = [
            {"step": 1, "action": "open_compass_to_length", "params": {"length": str(length)}},
            {"step": 2, "action": "mark_arc_from_new_point"},
        ]
        return steps, length
