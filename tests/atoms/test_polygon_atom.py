"""PolygonAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.polygon_atom import PolygonAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def _make_constraints(custom: dict, seed: int = 42) -> AtomConstraints:
    return AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=seed,
        custom=custom,
    )


def test_polygon_atom_right_triangle_respects_max_side() -> None:
    rng = random.Random(42)
    c = _make_constraints({"polygon_type": "right_triangle", "max_side_length": 5})
    p = PolygonAtom().sample(c, rng)
    assert p.polygon_type == "right_triangle"
    assert len(p.vertices) == 3
    for x, y in p.vertices:
        assert 0 <= int(x) <= 5
        assert 0 <= int(y) <= 5
    # 面積式が正
    assert sympy.simplify(p.area_expr) > 0


def test_polygon_atom_square_geometry() -> None:
    rng = random.Random(7)
    c = _make_constraints({"polygon_type": "square", "max_side_length": 6}, seed=7)
    p = PolygonAtom().sample(c, rng)
    assert len(p.vertices) == 4
    sides = p.side_lengths
    # 全 4 辺が等しい
    assert all(sympy.simplify(s - sides[0]) == 0 for s in sides)
    # 面積 = 辺^2
    assert sympy.simplify(p.area_expr - sides[0] ** 2) == 0


def test_polygon_atom_seed_reproducibility() -> None:
    c = _make_constraints({"polygon_type": "triangle", "max_side_length": 8}, seed=99)
    p1 = PolygonAtom().sample(c, random.Random(99))
    p2 = PolygonAtom().sample(c, random.Random(99))
    assert [(str(x), str(y)) for x, y in p1.vertices] == [
        (str(x), str(y)) for x, y in p2.vertices
    ]
    assert str(p1.area_expr) == str(p2.area_expr)


def test_polygon_atom_get_symbols_contains_area_and_perimeter() -> None:
    rng = random.Random(3)
    c = _make_constraints({"polygon_type": "rectangle", "max_side_length": 5}, seed=3)
    p = PolygonAtom().sample(c, rng)
    syms = p.get_symbols()
    assert "area" in syms
    assert "perimeter" in syms
    assert sympy.simplify(syms["area"]) > 0
    assert sympy.simplify(syms["perimeter"]) > 0


def test_polygon_atom_estimate_param_space_positive() -> None:
    c = _make_constraints({"polygon_type": "square", "max_side_length": 10})
    assert PolygonAtom.estimate_param_space(c) > 0
