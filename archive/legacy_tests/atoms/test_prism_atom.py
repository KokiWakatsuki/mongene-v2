"""PrismAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.prism_atom import PrismAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_prism_atom_cube_constraint() -> None:
    rng = random.Random(42)
    constraints = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=42,
        custom={"is_cube": True, "max_dim": 6},
    )
    prism = PrismAtom().sample(constraints, rng)
    assert prism.is_cube is True
    assert prism.width == prism.depth == prism.height
    # 体積 = s^3
    s = prism.width
    assert sympy.simplify(prism.volume_expr - s ** 3) == 0


def test_prism_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=7,
        custom={"base_shape_type": "triangle", "max_dim": 8},
    )
    p1 = PrismAtom().sample(c, random.Random(7))
    p2 = PrismAtom().sample(c, random.Random(7))
    assert str(p1.get_symbols()["volume_expr"]) == str(p2.get_symbols()["volume_expr"])
    assert p1.base_shape_type == p2.base_shape_type == "triangle"


def test_prism_atom_get_symbols_keys() -> None:
    rng = random.Random(3)
    c = AtomConstraints(
        difficulty_band=(4, 7),
        forbidden_tags=[],
        seed=3,
        custom={"base_shape_type": "square", "max_dim": 5},
    )
    prism = PrismAtom().sample(c, rng)
    sym = prism.get_symbols()
    for key in ("width", "depth", "height", "volume_expr", "surface_area_expr", "base_area_expr"):
        assert key in sym
    # 直方体の体積 = w*d*h を確認
    expected = prism.width * prism.depth * prism.height
    assert sympy.simplify(sym["volume_expr"] - expected) == 0
