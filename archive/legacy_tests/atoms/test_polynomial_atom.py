"""PolynomialAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.polynomial_atom import PolynomialAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_polynomial_atom_sample_respects_max_degree() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(4, 6),
        forbidden_tags=[],
        seed=42,
        custom={"max_degree": 2, "num_variables": 1, "max_coefficient": 5},
    )
    noun = PolynomialAtom().sample(c, rng)
    assert noun.degree <= 2
    assert len(noun.variables) == 1


def test_polynomial_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(4, 6),
        forbidden_tags=[],
        seed=42,
        custom={"max_degree": 2, "num_variables": 1, "max_coefficient": 5},
    )
    n1 = PolynomialAtom().sample(c, random.Random(42))
    n2 = PolynomialAtom().sample(c, random.Random(42))
    assert str(n1.get_symbols()["expression"]) == str(n2.get_symbols()["expression"])


def test_polynomial_atom_get_symbols_returns_expr() -> None:
    rng = random.Random(3)
    c = AtomConstraints(
        difficulty_band=(4, 6),
        forbidden_tags=[],
        seed=3,
        custom={"max_degree": 2, "num_variables": 2, "max_coefficient": 4},
    )
    noun = PolynomialAtom().sample(c, rng)
    symbols = noun.get_symbols()
    assert isinstance(symbols["expression"], sympy.Expr)
    assert isinstance(symbols["degree"], sympy.Expr)
