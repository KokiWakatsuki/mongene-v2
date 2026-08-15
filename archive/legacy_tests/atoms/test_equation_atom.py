"""EquationAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.equation_atom import EquationAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_equation_atom_linear_sample() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=42,
        custom={"degree": 1, "is_integer_solution": True, "max_coefficient": 5},
    )
    noun = EquationAtom().sample(c, rng)
    assert noun.degree == 1
    symbols = noun.get_symbols()
    assert isinstance(symbols["lhs"], sympy.Expr)
    assert isinstance(symbols["rhs"], sympy.Expr)


def test_equation_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=9,
        custom={"degree": 2, "is_integer_solution": True, "max_coefficient": 4},
    )
    n1 = EquationAtom().sample(c, random.Random(9))
    n2 = EquationAtom().sample(c, random.Random(9))
    assert str(n1.lhs) == str(n2.lhs)
    assert str(n1.rhs) == str(n2.rhs)


def test_equation_atom_quadratic_degree() -> None:
    rng = random.Random(3)
    c = AtomConstraints(
        difficulty_band=(5, 8),
        forbidden_tags=[],
        seed=3,
        custom={"degree": 2, "is_integer_solution": True, "max_coefficient": 4},
    )
    noun = EquationAtom().sample(c, rng)
    assert noun.degree == 2
    assert int(noun.get_symbols()["degree"]) == 2


def test_equation_atom_diophantine_adds_tag() -> None:
    rng = random.Random(5)
    c = AtomConstraints(
        difficulty_band=(5, 8),
        forbidden_tags=[],
        seed=5,
        custom={"diophantine_form": True, "max_coefficient": 5},
    )
    noun = EquationAtom().sample(c, rng)
    assert "diophantine" in noun.tags
