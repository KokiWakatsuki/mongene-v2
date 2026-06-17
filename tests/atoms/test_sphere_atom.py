"""SphereAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.sphere_atom import SphereAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_sphere_atom_integer_radius_within_bounds() -> None:
    rng = random.Random(42)
    constraints = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=42,
        custom={"max_radius": 8, "integer_radius": True},
    )
    sphere = SphereAtom().sample(constraints, rng)
    r = sphere.radius
    assert bool(r.is_integer) is True
    assert 1 <= int(r) <= 8


def test_sphere_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=99,
        custom={"max_radius": 10},
    )
    s1 = SphereAtom().sample(c, random.Random(99))
    s2 = SphereAtom().sample(c, random.Random(99))
    assert str(s1.radius) == str(s2.radius)


def test_sphere_atom_volume_and_surface_formula() -> None:
    sphere = SphereAtom(radius=sympy.Integer(3))
    sym = sphere.get_symbols()
    # V = 4/3 * pi * r^3 = 36 pi
    assert sympy.simplify(sym["volume_expr"] - 36 * sympy.pi) == 0
    # S = 4 * pi * r^2 = 36 pi
    assert sympy.simplify(sym["surface_area_expr"] - 36 * sympy.pi) == 0
    assert "radius" in sym
