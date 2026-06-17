"""LineAngleAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.line_angle_atom import LineAngleAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def _c(custom: dict, seed: int = 42) -> AtomConstraints:
    return AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=seed,
        custom=custom,
    )


def test_line_angle_atom_alternate_equal() -> None:
    rng = random.Random(42)
    c = _c({"relation_type": "alternate", "angle_range": (30, 150)})
    a = LineAngleAtom().sample(c, rng)
    assert 30 <= int(a.known_angle) <= 150
    # 錯角は等しい
    assert sympy.simplify(a.target_angle_expr - a.known_angle) == 0


def test_line_angle_atom_co_interior_supplementary() -> None:
    rng = random.Random(5)
    c = _c({"relation_type": "co_interior", "angle_range": (40, 140)}, seed=5)
    a = LineAngleAtom().sample(c, rng)
    # 同側内角の和 = 180
    total = sympy.simplify(a.known_angle + a.target_angle_expr)
    assert total == 180


def test_line_angle_atom_corresponding_equal() -> None:
    rng = random.Random(7)
    a = LineAngleAtom().sample(_c({"relation_type": "corresponding"}, seed=7), rng)
    assert sympy.simplify(a.target_angle_expr - a.known_angle) == 0


def test_line_angle_atom_seed_reproducibility() -> None:
    c = _c({"relation_type": "alternate"}, seed=123)
    a1 = LineAngleAtom().sample(c, random.Random(123))
    a2 = LineAngleAtom().sample(c, random.Random(123))
    assert str(a1.known_angle) == str(a2.known_angle)


def test_line_angle_atom_get_symbols() -> None:
    rng = random.Random(9)
    a = LineAngleAtom().sample(_c({}), rng)
    syms = a.get_symbols()
    assert "known_angle" in syms
    assert "target_angle" in syms
