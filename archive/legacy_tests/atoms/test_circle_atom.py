"""CircleAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.circle_atom import CircleAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def _c(custom: dict, seed: int = 42) -> AtomConstraints:
    return AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=seed,
        custom=custom,
    )


def test_circle_atom_full_circle_area_and_circumference() -> None:
    rng = random.Random(42)
    c = _c({"is_sector": False, "max_radius": 5})
    atom = CircleAtom().sample(c, rng)
    r = atom.radius
    assert 1 <= int(r) <= 5
    # 面積 = pi * r^2
    assert sympy.simplify(atom.area_expr - sympy.pi * r ** 2) == 0
    # 円周 = 2 pi r
    assert sympy.simplify(atom.circumference_expr - 2 * sympy.pi * r) == 0


def test_circle_atom_sector_central_angle_choice() -> None:
    rng = random.Random(11)
    choices = [60, 90, 120]
    c = _c({"is_sector": True, "max_radius": 6, "central_angle_choices": choices}, seed=11)
    atom = CircleAtom().sample(c, rng)
    assert atom.is_sector
    assert int(atom.central_angle) in choices
    # 弧長 = 2 pi r * angle / 360
    expected = 2 * sympy.pi * atom.radius * atom.central_angle / 360
    assert sympy.simplify(atom.arc_length_expr - expected) == 0


def test_circle_atom_seed_reproducibility() -> None:
    c = _c({"is_sector": True, "max_radius": 8}, seed=33)
    a1 = CircleAtom().sample(c, random.Random(33))
    a2 = CircleAtom().sample(c, random.Random(33))
    assert str(a1.radius) == str(a2.radius)
    assert str(a1.central_angle) == str(a2.central_angle)


def test_circle_atom_get_symbols_keys() -> None:
    rng = random.Random(1)
    atom = CircleAtom().sample(_c({"max_radius": 3}), rng)
    syms = atom.get_symbols()
    for key in ("radius", "central_angle", "area", "circumference", "arc_length"):
        assert key in syms
