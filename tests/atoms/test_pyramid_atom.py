"""PyramidAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.pyramid_atom import PyramidAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_pyramid_atom_respects_max_constraints() -> None:
    rng = random.Random(11)
    constraints = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=11,
        custom={
            "base_shape": "square",
            "max_base_side": 6,
            "max_height": 8,
            "is_regular_pyramid": True,
        },
    )
    py = PyramidAtom().sample(constraints, rng)
    assert 2 <= int(py.base_side) <= 6
    assert 2 <= int(py.height) <= 8
    assert py.base_shape == "square"


def test_pyramid_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=21,
        custom={"base_shape": "square", "max_base_side": 6, "max_height": 8},
    )
    p1 = PyramidAtom().sample(c, random.Random(21))
    p2 = PyramidAtom().sample(c, random.Random(21))
    assert str(p1.get_symbols()["volume_expr"]) == str(p2.get_symbols()["volume_expr"])


def test_pyramid_atom_volume_formula_square_base() -> None:
    # 正四角錐：V = (1/3) * s^2 * h
    rng = random.Random(2)
    c = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=2,
        custom={"base_shape": "square", "max_base_side": 5, "max_height": 5},
    )
    py = PyramidAtom().sample(c, rng)
    sym = py.get_symbols()
    expected = sympy.Rational(1, 3) * py.base_side ** 2 * py.height
    assert sympy.simplify(sym["volume_expr"] - expected) == 0
    # 必要なキーがそろっている
    for key in ("base_side", "height", "slant_edge", "volume_expr",
                "surface_area_expr", "base_area_expr", "lateral_area_expr"):
        assert key in sym
