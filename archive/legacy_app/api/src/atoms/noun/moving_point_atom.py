"""MovingPointAtom（§18.1）

動点（初期座標・速さ・経路型）を表す Noun Atom。時間 $t$ の関数として位置を返す。
"""
from __future__ import annotations

import random
from typing import Callable, ClassVar, Dict, List, Tuple

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


@register_noun
class MovingPointAtom(NounAtom):
    tags: ClassVar[List[str]] = ["moving_point", "time_function"]

    def __init__(
        self,
        initial_position: Tuple[sympy.Expr, sympy.Expr] | None = None,
        velocity: sympy.Expr | None = None,
        path_type: str = "linear",
        num_points: int = 1,
        direction: Tuple[sympy.Expr, sympy.Expr] | None = None,
        time_var: sympy.Symbol | None = None,
    ) -> None:
        self.initial_position: Tuple[sympy.Expr, sympy.Expr] = (
            (sympy.Integer(0), sympy.Integer(0)) if initial_position is None else initial_position
        )
        self.velocity: sympy.Expr = sympy.Integer(1) if velocity is None else velocity
        self.path_type: str = path_type
        self.num_points: int = num_points
        self.direction: Tuple[sympy.Expr, sympy.Expr] = (
            (sympy.Integer(1), sympy.Integer(0)) if direction is None else direction
        )
        self.time_var: sympy.Symbol = sympy.Symbol("t") if time_var is None else time_var

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "MovingPointAtom":
        custom = constraints.custom or {}
        path_type: str = str(custom.get("path_type", "linear"))
        if path_type not in ("edge_traversal", "circular", "linear"):
            path_type = "linear"
        num_points: int = int(custom.get("num_points", 1))
        num_points = max(1, min(3, num_points))
        speed_lo, speed_hi = custom.get("speed_range", (1, 5))
        speed_lo = int(speed_lo)
        speed_hi = int(speed_hi)
        max_init: int = int(custom.get("max_init", 10))

        velocity = sympy.Integer(rng.randint(max(1, speed_lo), max(speed_lo, speed_hi)))
        x0 = sympy.Integer(rng.randint(0, max_init))
        y0 = sympy.Integer(rng.randint(0, max_init))

        # 方向ベクトル
        if path_type == "linear":
            dx = rng.choice([-1, 1])
            dy = rng.choice([-1, 0, 1])
            direction = (sympy.Integer(dx), sympy.Integer(dy))
        elif path_type == "edge_traversal":
            # 辺の上を移動：最初は x 軸方向
            direction = (sympy.Integer(1), sympy.Integer(0))
        else:  # circular
            # 円運動：方向は角速度の符号のみ
            direction = (sympy.Integer(1), sympy.Integer(0))

        return MovingPointAtom(
            initial_position=(x0, y0),
            velocity=velocity,
            path_type=path_type,
            num_points=num_points,
            direction=direction,
            time_var=sympy.Symbol("t"),
        )

    @property
    def position_at_t(self) -> Callable[[sympy.Expr], Tuple[sympy.Expr, sympy.Expr]]:
        """時刻 t における位置を返す Callable。"""
        x0, y0 = self.initial_position
        v = self.velocity
        dx, dy = self.direction
        path = self.path_type

        if path == "circular":
            # 円運動：半径 = 初期位置と原点の距離（簡易）
            r = sympy.sqrt(x0 ** 2 + y0 ** 2)
            if r == 0:
                r = sympy.Integer(1)

            def f_circ(t: sympy.Expr) -> Tuple[sympy.Expr, sympy.Expr]:
                omega = v / r if r != 0 else v
                return (r * sympy.cos(omega * t), r * sympy.sin(omega * t))

            return f_circ

        # linear / edge_traversal：等速直線
        norm_sq = dx ** 2 + dy ** 2
        norm = sympy.sqrt(norm_sq) if norm_sq != 0 else sympy.Integer(1)

        def f_lin(t: sympy.Expr) -> Tuple[sympy.Expr, sympy.Expr]:
            return (x0 + v * dx / norm * t, y0 + v * dy / norm * t)

        return f_lin

    def get_symbols(self) -> Dict[str, sympy.Expr]:
        x0, y0 = self.initial_position
        pos = self.position_at_t(self.time_var)
        return {
            "x0": x0,
            "y0": y0,
            "velocity": self.velocity,
            "time_var": self.time_var,
            "position_x": sympy.simplify(pos[0]),
            "position_y": sympy.simplify(pos[1]),
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        speed_lo, speed_hi = custom.get("speed_range", (1, 5))
        max_init = int(custom.get("max_init", 10))
        speed_n = max(1, int(speed_hi) - int(speed_lo) + 1)
        return speed_n * (max_init + 1) ** 2
