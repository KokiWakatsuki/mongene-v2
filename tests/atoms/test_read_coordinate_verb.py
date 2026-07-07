"""ReadCoordinateVerb のテスト（座標読み取り・moat）。"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.noun.point_atom import PointAtom
from apps.api.src.atoms.verb.read_coordinate_verb import ReadCoordinateVerb


def test_validate_rejects_non_point_atom() -> None:
    ok, reason = ReadCoordinateVerb().validate(NumberAtom(value=sympy.Integer(1)))
    assert ok is False and reason is not None


def test_solve_returns_point_coordinates() -> None:
    atom = PointAtom(x=sympy.Integer(3), y=sympy.Integer(-2), label="A")
    step = ReadCoordinateVerb().solve(atom, rng=random.Random(0))
    assert step.sympy_expr == sympy.Tuple(sympy.Integer(3), sympy.Integer(-2))
    assert step.operands[0] == "A"
