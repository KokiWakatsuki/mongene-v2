"""QuadraticFuncAtom のユニットテスト"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.quadratic_func_atom import QuadraticFuncAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_quadratic_func_atom_respects_constraints() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 7),
        forbidden_tags=[],
        seed=42,
        custom={
            "max_a_value": 3,
            "allow_negative_a": False,
            "is_pure_form": True,
            "force_integer": True,
        },
    )
    f = QuadraticFuncAtom().sample(c, rng)
    assert f.coefficient_a.is_Integer
    assert 1 <= int(f.coefficient_a) <= 3


def test_quadratic_func_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 7),
        forbidden_tags=[],
        seed=9,
        custom={"max_a_value": 4, "force_integer": True},
    )
    f1 = QuadraticFuncAtom().sample(c, random.Random(9))
    f2 = QuadraticFuncAtom().sample(c, random.Random(9))
    assert str(f1.coefficient_a) == str(f2.coefficient_a)


def test_quadratic_func_atom_expression_property() -> None:
    f = QuadraticFuncAtom(coefficient_a=sympy.Rational(1, 2))
    syms = f.get_symbols()
    x = sympy.Symbol("x")
    assert sympy.simplify(syms["expression"] - sympy.Rational(1, 2) * x**2) == 0
    assert syms["coefficient_a"] == sympy.Rational(1, 2)
