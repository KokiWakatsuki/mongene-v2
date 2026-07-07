"""EvaluateFunctionVerb のテスト（比例/反比例グラフ上の点の評価・moat）。

- 比例 y=ax: 任意の非ゼロ整数 x0 で y0 は整数、かつ実際に slope*x0 と一致する。
- 反比例 y=a/x: 選ばれた x0 は a を割り切り、y0 は整数。
- 受理型以外は validate で弾く。
"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.inverse_func_atom import InverseFuncAtom
from apps.api.src.atoms.noun.linear_func_atom import LinearFuncAtom
from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.verb.evaluate_function_verb import EvaluateFunctionVerb


def test_validate_rejects_non_function_atom() -> None:
    ok, reason = EvaluateFunctionVerb().validate(NumberAtom(value=sympy.Integer(3)))
    assert ok is False and reason is not None


def test_validate_rejects_zero_constant_inverse() -> None:
    ok, reason = EvaluateFunctionVerb().validate(InverseFuncAtom(constant=sympy.Integer(0)))
    assert ok is False and "0" in (reason or "")


def test_proportion_eval_is_integer_and_consistent() -> None:
    verb = EvaluateFunctionVerb()
    atom = LinearFuncAtom(slope=sympy.Integer(3), intercept=sympy.Integer(0))
    for s in range(50):
        step = verb.solve(atom, rng=random.Random(s))
        y0 = step.sympy_expr
        assert y0.is_integer  # 整数解（moat）
        # operands[1] = "x=<x0>" と slope から一貫していること
        x0 = int(step.operands[1].split("=")[1])
        assert sympy.simplify(y0 - 3 * x0) == 0
        assert x0 != 0


def test_inverse_eval_x0_divides_constant_and_integer_result() -> None:
    verb = EvaluateFunctionVerb()
    for c in (6, -8, 11, 12):
        atom = InverseFuncAtom(constant=sympy.Integer(c))
        for s in range(30):
            step = verb.solve(atom, rng=random.Random(s))
            y0 = step.sympy_expr
            assert y0.is_integer  # 整数解（moat）
            x0 = int(step.operands[1].split("=")[1])
            assert x0 != 0 and c % x0 == 0
            assert sympy.simplify(y0 - sympy.Rational(c, x0)) == 0
