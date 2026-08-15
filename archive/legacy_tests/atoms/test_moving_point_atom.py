"""MovingPointAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.moving_point_atom import MovingPointAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_moving_point_atom_respects_speed_range() -> None:
    rng = random.Random(42)
    constraints = AtomConstraints(
        difficulty_band=(6, 9),
        forbidden_tags=[],
        seed=42,
        custom={
            "path_type": "linear",
            "num_points": 2,
            "speed_range": (1, 4),
            "max_init": 8,
        },
    )
    mp = MovingPointAtom().sample(constraints, rng)
    assert 1 <= int(mp.velocity) <= 4
    assert mp.path_type == "linear"
    assert 1 <= mp.num_points <= 3


def test_moving_point_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(6, 9),
        forbidden_tags=[],
        seed=13,
        custom={"path_type": "linear", "speed_range": (2, 6), "max_init": 5},
    )
    m1 = MovingPointAtom().sample(c, random.Random(13))
    m2 = MovingPointAtom().sample(c, random.Random(13))
    assert str(m1.velocity) == str(m2.velocity)
    assert m1.initial_position == m2.initial_position


def test_moving_point_atom_position_callable_and_symbols() -> None:
    # 初期位置 (0, 0)、速度 3、方向 (1, 0) の等速直線運動を直接構築
    mp = MovingPointAtom(
        initial_position=(sympy.Integer(0), sympy.Integer(0)),
        velocity=sympy.Integer(3),
        path_type="linear",
        direction=(sympy.Integer(1), sympy.Integer(0)),
    )
    t = sympy.Symbol("t")
    px, py = mp.position_at_t(t)
    assert sympy.simplify(px - 3 * t) == 0
    assert sympy.simplify(py) == 0

    sym = mp.get_symbols()
    for key in ("x0", "y0", "velocity", "time_var", "position_x", "position_y"):
        assert key in sym
