"""Phase 2 Verb 群の最低限テスト（型ガード + 単純 sympy 検算）"""
from __future__ import annotations

import json
import random

import pytest
import sympy

from apps.api.src.atoms.noun.circle_atom import CircleAtom
from apps.api.src.atoms.noun.data_set_atom import DataSetAtom
from apps.api.src.atoms.noun.equation_atom import EquationAtom
from apps.api.src.atoms.noun.event_atom import EventAtom
from apps.api.src.atoms.noun.linear_func_atom import LinearFuncAtom
from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.noun.point_atom import PointAtom
from apps.api.src.atoms.noun.polygon_atom import PolygonAtom
from apps.api.src.atoms.noun.polynomial_atom import PolynomialAtom
from apps.api.src.atoms.noun.prism_atom import PrismAtom
from apps.api.src.atoms.noun.pyramid_atom import PyramidAtom
from apps.api.src.atoms.noun.sample_atom import SampleAtom
from apps.api.src.atoms.noun.sequence_atom import SequenceAtom
from apps.api.src.atoms.verb.analyze_data_verb import AnalyzeDataVerb
from apps.api.src.atoms.verb.calculate_probability_verb import CalculateProbabilityVerb
from apps.api.src.atoms.verb.construct_geometry_verb import ConstructGeometryVerb
from apps.api.src.atoms.verb.cutout_verb import CutoutVerb
from apps.api.src.atoms.verb.estimate_population_verb import EstimatePopulationVerb
from apps.api.src.atoms.verb.find_angle_verb import FindAngleVerb
from apps.api.src.atoms.verb.find_divisors_verb import FindDivisorsVerb
from apps.api.src.atoms.verb.form_shape_verb import FormShapeVerb
from apps.api.src.atoms.verb.formulate_verb import FormulateVerb
from apps.api.src.atoms.verb.generalize_formula_verb import GeneralizeFormulaVerb
from apps.api.src.atoms.verb.intersect_verb import IntersectVerb
from apps.api.src.atoms.verb.locus_verb import LocusVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.atoms.verb.prove_algebraic_verb import ProveAlgebraicVerb
from apps.api.src.atoms.verb.prove_geometry_verb import ProveGeometryVerb
from apps.api.src.atoms.verb.slice_solid_verb import SliceSolidVerb
from apps.api.src.atoms.verb.solve_eq_verb import SolveEqVerb
from apps.api.src.atoms.verb.solve_linear_diophantine_verb import SolveLinearDiophantineVerb
from apps.api.src.atoms.verb.transform_shape_verb import TransformShapeVerb
from apps.api.src.atoms.verb.unfold_net_verb import UnfoldNetVerb
from apps.api.src.core.abc.atoms import AtomConstraints


def _ac(**kw) -> AtomConstraints:
    return AtomConstraints(difficulty_band=(1, 50), forbidden_tags=[], seed=42, custom=kw)


def _num(v: int) -> NumberAtom:
    return NumberAtom(value=sympy.Integer(v))


def _sample(cls, **kw):
    return cls().sample(_ac(**kw), random.Random(42))


# --- SolveEqVerb ---
def test_solve_eq_validate_rejects_wrong_type() -> None:
    ok, _ = SolveEqVerb().validate(_num(3))
    assert ok is False


def test_solve_eq_solves_linear() -> None:
    eq = _sample(EquationAtom, degree=1, max_coefficient=5)
    ok, _ = SolveEqVerb().validate(eq)
    assert ok is True
    step = SolveEqVerb().solve(eq, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- FindDivisorsVerb ---
def test_find_divisors_lists() -> None:
    step = FindDivisorsVerb("divisors").solve(_num(12), rng=random.Random(0))
    s = str(step.sympy_expr)
    for d in (1, 2, 3, 4, 6, 12):
        assert str(d) in s


def test_find_divisors_gcd() -> None:
    step = FindDivisorsVerb("gcd").solve(_num(12), _num(18), rng=random.Random(0))
    assert sympy.simplify(step.sympy_expr - 6) == 0


def test_find_divisors_rejects_zero() -> None:
    ok, _ = FindDivisorsVerb().validate(_num(0))
    assert ok is False


# --- SolveLinearDiophantineVerb ---
def test_diophantine_validate_passes_for_solvable() -> None:
    # 2x + 4y = 10 → gcd(2,4)=2 | 10
    x, y = sympy.symbols("x y")
    eq = EquationAtom(lhs=2 * x + 4 * y, rhs=sympy.Integer(10), variable=x, degree=1)
    ok, _ = SolveLinearDiophantineVerb().validate(eq)
    assert ok is True


def test_diophantine_rejects_unsolvable() -> None:
    x, y = sympy.symbols("x y")
    eq = EquationAtom(lhs=2 * x + 4 * y, rhs=sympy.Integer(7), variable=x, degree=1)
    ok, _ = SolveLinearDiophantineVerb().validate(eq)
    assert ok is False


# --- ProveAlgebraicVerb ---
def test_prove_algebraic_returns_step() -> None:
    step = ProveAlgebraicVerb("even_odd").solve(_num(4), rng=random.Random(0))
    assert "偶数" in step.narration_hint or "奇数" in step.narration_hint
    assert step.operation_name.startswith("prove_algebraic_")


def test_prove_algebraic_unsupported_proof_type_raises() -> None:
    with pytest.raises(ValueError):
        ProveAlgebraicVerb("unsupported_type").solve(_num(4), rng=random.Random(0))


@pytest.mark.parametrize(
    "proof_type",
    [
        "consecutive_two_sum",
        "consecutive_three_sum",
        "consecutive_two_odds_sum",
        "square_diff_consecutive",
        "digit_two",
        "digit_three",
    ],
)
def test_prove_algebraic_extended_proof_types_return_step(proof_type: str) -> None:
    """拡張フェーズで追加した6つの proof_type が、例外なく LogicStep を返し、
    4ステップ構成の proof_output（moat 検証済み）を持つこと。"""
    step = ProveAlgebraicVerb(proof_type).solve(_num(4), rng=random.Random(0))
    assert step.operation_name == f"prove_algebraic_{proof_type}"
    assert step.narration_hint

    proof_output = json.loads(step.operands[-1])
    assert proof_output["to_prove"] == step.narration_hint
    assert len(proof_output["steps"]) == 4
    for i, s in enumerate(proof_output["steps"], start=1):
        assert s["step_number"] == i
    assert proof_output["conclusion"]


# --- FormulateVerb（立式型 word_problem） ---
def _poly(expr: sympy.Expr, variables=None) -> PolynomialAtom:
    return PolynomialAtom(expression=expr, variables=variables or [sympy.Symbol("x")])


def test_formulate_expression_returns_expression_as_answer() -> None:
    """FormulateVerb(expression) は式そのものを答え（sympy_expr）として返す（解かない）。"""
    x = sympy.Symbol("x")
    step = FormulateVerb("expression").solve(_poly(3 * x + 2), rng=random.Random(0))
    assert step.operation_name == "formulate_expression"
    assert step.sympy_expr == 3 * x + 2


def test_formulate_rejects_constant_without_variable() -> None:
    """変数を含まない式は立式題材に不適として validate が弾く（moat）。"""
    ok, _ = FormulateVerb("expression").validate(_num(5))
    assert ok is False


def test_formulate_unsupported_mode_raises() -> None:
    x = sympy.Symbol("x")
    with pytest.raises(ValueError):
        FormulateVerb("equation").solve(_poly(3 * x + 2), rng=random.Random(0))


# --- GeneralizeFormulaVerb ---
def test_generalize_formula_returns_nth_term() -> None:
    seq = _sample(SequenceAtom, pattern_type="arithmetic")
    step = GeneralizeFormulaVerb().solve(seq, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- CutoutVerb ---
def test_cutout_validate_rejects_oversized() -> None:
    big_prism = PrismAtom().sample(_ac(is_cube=True, max_height=5), random.Random(1))
    huge_pyramid = PyramidAtom().sample(_ac(max_base_side=20, max_height=20), random.Random(1))
    ok, _ = CutoutVerb().validate(big_prism, huge_pyramid)
    assert ok is False


def test_cutout_solves_volume_difference() -> None:
    prism = PrismAtom().sample(_ac(is_cube=True, max_height=10), random.Random(2))
    pyramid = PyramidAtom().sample(_ac(max_base_side=2, max_height=2), random.Random(2))
    ok, _ = CutoutVerb().validate(prism, pyramid)
    if ok:
        step = CutoutVerb().solve(prism, pyramid, rng=random.Random(0))
        assert step.sympy_expr is not None


# --- SliceSolidVerb ---
def test_slice_solid_returns_two_volumes() -> None:
    prism = PrismAtom().sample(_ac(is_cube=True, max_height=10), random.Random(3))
    step = SliceSolidVerb().solve(prism, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- UnfoldNetVerb ---
def test_unfold_net_rejects_sphere() -> None:
    prism = PrismAtom().sample(_ac(), random.Random(0))
    ok, _ = UnfoldNetVerb().validate(prism)
    assert ok is True


# --- TransformShapeVerb ---
def test_transform_shape_translates() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="square"), random.Random(0))
    step = TransformShapeVerb("translation").solve(poly, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- ConstructGeometryVerb ---
def test_construct_geometry_returns_steps() -> None:
    p1 = PointAtom().sample(_ac(), random.Random(0))
    p2 = PointAtom().sample(_ac(), random.Random(1))
    step = ConstructGeometryVerb("perp_bisector").solve(p1, p2, rng=random.Random(0))
    # 垂直二等分線の方程式が返る（sympy.Eq）
    assert step.sympy_expr is not None
    assert "perp_bisector" in step.operation_name


# --- ProveGeometryVerb ---
def test_prove_geometry_validates_two_polygons() -> None:
    a = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(0))
    b = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(1))
    ok, _ = ProveGeometryVerb().validate(a, b)
    assert ok is True


# --- LocusVerb ---
def test_locus_returns_expr() -> None:
    p1 = PointAtom().sample(_ac(), random.Random(0))
    p2 = PointAtom().sample(_ac(), random.Random(1))
    step = LocusVerb().solve(p1, p2, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- FindAngleVerb ---
def test_find_angle_polygon_interior_sum() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(0))
    step = FindAngleVerb("interior_angle_sum").solve(poly, rng=random.Random(0))
    # 三角形の内角和は 180°
    assert sympy.simplify(step.sympy_expr - 180) == 0


# --- MeasureGeometryVerb ---
def test_measure_distance_between_points() -> None:
    p1 = PointAtom(x=sympy.Integer(0), y=sympy.Integer(0))
    p2 = PointAtom(x=sympy.Integer(3), y=sympy.Integer(4))
    step = MeasureGeometryVerb("distance").solve(p1, p2, rng=random.Random(0))
    assert sympy.simplify(step.sympy_expr - 5) == 0


def test_measure_circle_area() -> None:
    c = CircleAtom().sample(_ac(is_sector=False, max_radius=5), random.Random(0))
    step = MeasureGeometryVerb("area").solve(c, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- FormShapeVerb ---
def test_form_shape_triangle_area() -> None:
    p1 = PointAtom(x=sympy.Integer(0), y=sympy.Integer(0))
    p2 = PointAtom(x=sympy.Integer(4), y=sympy.Integer(0))
    p3 = PointAtom(x=sympy.Integer(0), y=sympy.Integer(3))
    step = FormShapeVerb().solve(p1, p2, p3, rng=random.Random(0))
    # 3-4-5 直角三角形の面積 = 6
    assert sympy.simplify(step.sympy_expr - 6) == 0


# --- IntersectVerb ---
def test_intersect_rejects_parallel_lines() -> None:
    f1 = LinearFuncAtom(slope=sympy.Integer(2), intercept=sympy.Integer(1))
    f2 = LinearFuncAtom(slope=sympy.Integer(2), intercept=sympy.Integer(3))
    ok, _ = IntersectVerb().validate(f1, f2)
    assert ok is False


# --- CalculateProbabilityVerb ---
def test_probability_returns_rational() -> None:
    event = EventAtom().sample(_ac(event_type="dice", num_trials=1), random.Random(0))
    step = CalculateProbabilityVerb(favorable=3).solve(event, rng=random.Random(0))
    assert step.sympy_expr.is_Rational


# --- AnalyzeDataVerb ---
def test_analyze_mean_returns_value() -> None:
    ds = DataSetAtom().sample(_ac(data_size=10, value_range=(0, 50)), random.Random(0))
    step = AnalyzeDataVerb("mean").solve(ds, rng=random.Random(0))
    assert step.sympy_expr is not None


# --- EstimatePopulationVerb ---
def test_estimate_population_returns_value() -> None:
    s = SampleAtom().sample(_ac(population_size=1000, sample_size=50), random.Random(0))
    step = EstimatePopulationVerb("total_count").solve(s, rng=random.Random(0))
    assert step.sympy_expr is not None
