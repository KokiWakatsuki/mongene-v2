"""CalculateArithmeticVerb のテスト（§34.2）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.verb.calculate_arithmetic_verb import CalculateArithmeticVerb


def _num(value: int) -> NumberAtom:
    return NumberAtom(value=sympy.Integer(value))


def test_validate_rejects_single_operand() -> None:
    ok, reason = CalculateArithmeticVerb().validate(_num(1))
    assert ok is False
    assert reason is not None


def test_validate_rejects_division_by_zero() -> None:
    verb = CalculateArithmeticVerb(operation="/")
    ok, reason = verb.validate(_num(10), _num(0))
    assert ok is False
    assert "ゼロ" in (reason or "")


def test_solve_addition_returns_correct_sum() -> None:
    verb = CalculateArithmeticVerb(operation="+")
    step = verb.solve(_num(3), _num(4), rng=random.Random(0))
    assert sympy.simplify(step.sympy_expr - 7) == 0


def test_solve_subtraction_returns_correct_difference() -> None:
    verb = CalculateArithmeticVerb(operation="-")
    step = verb.solve(_num(10), _num(3), rng=random.Random(0))
    assert sympy.simplify(step.sympy_expr - 7) == 0
