"""MovingPointAreaVerb の moat テスト（動点による三角形面積の時間変化）。

- 3 query（area_at_t / area_function / max_area）が同一図形・同一速さで整合すること。
- bbox ベースで一般三角形でも有理数の面積になること。
- SymPy が実際に面積を計算していること（moat）。
"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.moving_point_atom import MovingPointAtom
from apps.api.src.atoms.noun.polygon_atom import PolygonAtom
from apps.api.src.atoms.verb.moving_point_area_verb import MovingPointAreaVerb

RNG = random.Random(0)
T = sympy.Symbol("t", nonnegative=True)


def _rect(w, h):
    return PolygonAtom(
        polygon_type="rectangle",
        vertices=[
            (sympy.Integer(0), sympy.Integer(0)),
            (sympy.Integer(w), sympy.Integer(0)),
            (sympy.Integer(w), sympy.Integer(h)),
            (sympy.Integer(0), sympy.Integer(h)),
        ],
        n_sides=4,
    )


def _mover(v):
    return MovingPointAtom(velocity=sympy.Integer(v))


def test_area_function_is_linear_in_t():
    # 長方形 base=6, 速さ v=2 → S(t) = (1/2)*6*2*t = 6t
    step = MovingPointAreaVerb("area_function").solve(_rect(6, 4), _mover(2), rng=RNG)
    assert sympy.simplify(step.sympy_expr - 6 * T) == 0


def test_max_area_is_half_base_times_height():
    # max = (1/2)*base*H = (1/2)*6*4 = 12（速さに依存しない）
    step = MovingPointAreaVerb("max_area").solve(_rect(6, 4), _mover(2), rng=RNG)
    assert step.sympy_expr == 12


def test_area_at_t_consistent_with_function():
    # area_function=6t, travel_time=H/v=4/2=2 → t0=1, S(1)=6
    rect, mover = _rect(6, 4), _mover(2)
    at_t = MovingPointAreaVerb("area_at_t").solve(rect, mover, rng=RNG).sympy_expr
    func = MovingPointAreaVerb("area_function").solve(rect, mover, rng=RNG).sympy_expr
    # area_at_t は func に t0 を代入した値と一致（内部整合＝coherence）
    assert at_t == 6  # S(1)
    assert func.subs(T, 1) == 6


def test_three_queries_are_distinct():
    rect, mover = _rect(6, 4), _mover(2)
    a = MovingPointAreaVerb("area_at_t").solve(rect, mover, rng=RNG).sympy_expr
    f = MovingPointAreaVerb("area_function").solve(rect, mover, rng=RNG).sympy_expr
    m = MovingPointAreaVerb("max_area").solve(rect, mover, rng=RNG).sympy_expr
    assert len({str(a), str(f), str(m)}) == 3


def test_general_triangle_area_is_rational():
    # bbox ベースなので底辺が水平でない一般三角形でも有理数（√ が出ない）
    tri = PolygonAtom(
        polygon_type="triangle",
        vertices=[
            (sympy.Integer(1), sympy.Integer(2)),
            (sympy.Integer(4), sympy.Integer(0)),
            (sympy.Integer(0), sympy.Integer(5)),
        ],
        n_sides=3,
    )
    step = MovingPointAreaVerb("max_area").solve(tri, _mover(1), rng=RNG)
    # bbox: 幅=4-0=4, 高さ=5-0=5 → max=(1/2)*4*5=10
    assert step.sympy_expr == 10
    assert step.sympy_expr.is_rational


def test_speed_scales_time_not_max_area():
    # 速さが変わっても最大面積は不変（形状で決まる）、S(t) の傾きは変わる
    m1 = MovingPointAreaVerb("max_area").solve(_rect(6, 4), _mover(1), rng=RNG).sympy_expr
    m2 = MovingPointAreaVerb("max_area").solve(_rect(6, 4), _mover(3), rng=RNG).sympy_expr
    assert m1 == m2 == 12
    f1 = MovingPointAreaVerb("area_function").solve(_rect(6, 4), _mover(1), rng=RNG).sympy_expr
    f3 = MovingPointAreaVerb("area_function").solve(_rect(6, 4), _mover(3), rng=RNG).sympy_expr
    assert sympy.simplify(f1 - 3 * T) == 0
    assert sympy.simplify(f3 - 9 * T) == 0
