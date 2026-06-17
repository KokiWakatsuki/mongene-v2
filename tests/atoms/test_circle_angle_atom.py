"""CircleAngleAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.circle_angle_atom import CircleAngleAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def _c(custom: dict, seed: int = 42) -> AtomConstraints:
    return AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=seed,
        custom=custom,
    )


def test_circle_angle_atom_inscribed_is_half_central() -> None:
    rng = random.Random(42)
    a = CircleAngleAtom().sample(_c({}), rng)
    # 円周角 = 中心角 / 2
    assert sympy.simplify(
        a.inscribed_angle_expr - a.central_angle_expr / 2
    ) == 0


def test_circle_angle_atom_inscribed_quadrilateral_tag() -> None:
    rng = random.Random(7)
    a = CircleAngleAtom().sample(_c({"inscribed_quadrilateral": True}, seed=7), rng)
    assert a.inscribed_quadrilateral is True
    assert "inscribed_quadrilateral" in a.tags
    # 対角の和は 180
    assert sympy.simplify(
        a.inscribed_angle_expr + a.opposite_inscribed_angle_expr
    ) == 180


def test_circle_angle_atom_tangent_chord_and_power_tags() -> None:
    rng = random.Random(3)
    a = CircleAngleAtom().sample(
        _c({"tangent_chord_angle": True, "power_of_point": True}, seed=3), rng
    )
    assert "tangent_chord" in a.tags
    assert "power_of_point" in a.tags


def test_circle_angle_atom_seed_reproducibility() -> None:
    c = _c({}, seed=21)
    a1 = CircleAngleAtom().sample(c, random.Random(21))
    a2 = CircleAngleAtom().sample(c, random.Random(21))
    assert str(a1.central_angle) == str(a2.central_angle)


def test_circle_angle_atom_get_symbols() -> None:
    rng = random.Random(11)
    a = CircleAngleAtom().sample(_c({}), rng)
    syms = a.get_symbols()
    assert "inscribed_angle" in syms
    assert "central_angle" in syms
    assert "opposite_inscribed_angle" in syms
