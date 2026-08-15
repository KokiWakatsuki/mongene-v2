"""InverseFuncAtom のユニットテスト"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.inverse_func_atom import InverseFuncAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_inverse_func_atom_respects_max_constant() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=42,
        custom={"max_constant": 6, "integer_only": True, "allow_negative": False},
    )
    f = InverseFuncAtom().sample(c, rng)
    assert f.constant.is_Integer
    assert 1 <= int(f.constant) <= 6


def test_inverse_func_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=3,
        custom={"max_constant": 12, "integer_only": True},
    )
    f1 = InverseFuncAtom().sample(c, random.Random(3))
    f2 = InverseFuncAtom().sample(c, random.Random(3))
    assert str(f1.constant) == str(f2.constant)


def test_inverse_func_atom_expression_property() -> None:
    f = InverseFuncAtom(constant=sympy.Integer(6))
    syms = f.get_symbols()
    x = sympy.Symbol("x")
    assert sympy.simplify(syms["expression"] - 6 / x) == 0
    assert syms["constant"] == sympy.Integer(6)
