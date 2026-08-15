"""SquareRootAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.square_root_atom import SquareRootAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_square_root_atom_sample_base_in_range() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=42,
        custom={"max_base": 20, "max_coefficient": 3},
    )
    noun = SquareRootAtom().sample(c, rng)
    symbols = noun.get_symbols()
    assert 2 <= int(symbols["base"]) <= 20
    assert 1 <= int(symbols["coefficient"]) <= 3


def test_square_root_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=7,
        custom={"max_base": 30, "max_coefficient": 5},
    )
    n1 = SquareRootAtom().sample(c, random.Random(7))
    n2 = SquareRootAtom().sample(c, random.Random(7))
    assert str(n1.get_symbols()["expression"]) == str(n2.get_symbols()["expression"])


def test_square_root_atom_get_symbols_returns_expr() -> None:
    rng = random.Random(11)
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=11,
        custom={"max_base": 30, "max_coefficient": 4},
    )
    noun = SquareRootAtom().sample(c, rng)
    symbols = noun.get_symbols()
    assert isinstance(symbols["expression"], sympy.Expr)
    assert isinstance(symbols["coefficient"], sympy.Expr)
    assert isinstance(symbols["base"], sympy.Expr)


def test_square_root_atom_force_denominator_root() -> None:
    rng = random.Random(2)
    c = AtomConstraints(
        difficulty_band=(5, 7),
        forbidden_tags=[],
        seed=2,
        custom={"force_denominator_root": True, "max_base": 10, "max_coefficient": 1},
    )
    noun = SquareRootAtom().sample(c, rng)
    expr = noun.get_symbols()["expression"]
    # 分母に sqrt が残る形（1/sqrt(n)）
    assert sympy.sqrt(noun.base) in expr.atoms(sympy.Pow) or expr.has(sympy.sqrt(noun.base))
