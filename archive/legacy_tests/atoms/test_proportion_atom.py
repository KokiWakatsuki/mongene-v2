"""ProportionAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.proportion_atom import ProportionAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_proportion_atom_integer_solution() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(3, 4),
        forbidden_tags=[],
        seed=42,
        custom={"is_integer_solution": True, "max_ratio_value": 6},
    )
    noun = ProportionAtom().sample(c, rng)
    a, b = noun.lhs_ratio
    cc, d = noun.rhs_ratio
    # 整数解条件 => a*d == b*c
    assert int(a) * int(d) == int(b) * int(cc)


def test_proportion_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(3, 4),
        forbidden_tags=[],
        seed=10,
        custom={"is_integer_solution": True, "max_ratio_value": 8},
    )
    n1 = ProportionAtom().sample(c, random.Random(10))
    n2 = ProportionAtom().sample(c, random.Random(10))
    assert n1.lhs_ratio == n2.lhs_ratio
    assert n1.rhs_ratio == n2.rhs_ratio


def test_proportion_atom_get_symbols_returns_expr() -> None:
    rng = random.Random(4)
    c = AtomConstraints(
        difficulty_band=(3, 4),
        forbidden_tags=[],
        seed=4,
        custom={"is_integer_solution": True, "max_ratio_value": 5},
    )
    noun = ProportionAtom().sample(c, rng)
    symbols = noun.get_symbols()
    for key in ("lhs_a", "lhs_b", "rhs_c", "rhs_d"):
        assert isinstance(symbols[key], sympy.Expr)
