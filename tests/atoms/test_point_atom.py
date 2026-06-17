"""PointAtom のユニットテスト"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.point_atom import PointAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_point_atom_respects_range_constraint() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=42,
        custom={"range_x": (-5, 5), "range_y": (0, 10), "integer_only": True, "label": "P"},
    )
    p = PointAtom().sample(c, rng)
    syms = p.get_symbols()
    assert bool(syms["x"].is_integer) is True
    assert bool(syms["y"].is_integer) is True
    assert -5 <= int(syms["x"]) <= 5
    assert 0 <= int(syms["y"]) <= 10
    assert p.label == "P"


def test_point_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=7,
        custom={"range_x": (-10, 10), "range_y": (-10, 10), "integer_only": True},
    )
    p1 = PointAtom().sample(c, random.Random(7))
    p2 = PointAtom().sample(c, random.Random(7))
    assert (str(p1.x), str(p1.y)) == (str(p2.x), str(p2.y))


def test_point_atom_get_symbols_has_x_y_label() -> None:
    p = PointAtom(x=sympy.Integer(3), y=sympy.Integer(-2), label="Q")
    syms = p.get_symbols()
    assert syms["x"] == sympy.Integer(3)
    assert syms["y"] == sympy.Integer(-2)
    assert "label" in syms
