"""LinearFuncAtom のユニットテスト"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.linear_func_atom import LinearFuncAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_linear_func_atom_force_proportion_makes_b_zero() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=42,
        custom={"force_proportion": True, "max_slope": 5, "force_integer_slope": True},
    )
    f = LinearFuncAtom().sample(c, rng)
    assert f.intercept == sympy.Integer(0)
    assert f.slope != sympy.Integer(0)
    assert abs(int(f.slope)) <= 5


def test_linear_func_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 5),
        forbidden_tags=[],
        seed=11,
        custom={"max_slope": 6, "force_integer_slope": True},
    )
    f1 = LinearFuncAtom().sample(c, random.Random(11))
    f2 = LinearFuncAtom().sample(c, random.Random(11))
    assert str(f1.slope) == str(f2.slope)
    assert str(f1.intercept) == str(f2.intercept)


def test_linear_func_atom_expression_property() -> None:
    f = LinearFuncAtom(slope=sympy.Integer(2), intercept=sympy.Integer(3))
    syms = f.get_symbols()
    x = sympy.Symbol("x")
    assert sympy.simplify(syms["expression"] - (2 * x + 3)) == 0
    assert syms["slope"] == sympy.Integer(2)
    assert syms["intercept"] == sympy.Integer(3)
