"""Phase 2 Verb 群の追加カバレッジテスト（validate の rejection 経路）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.data_set_atom import DataSetAtom
from apps.api.src.atoms.noun.event_atom import EventAtom
from apps.api.src.atoms.noun.linear_func_atom import LinearFuncAtom
from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.noun.polygon_atom import PolygonAtom
from apps.api.src.atoms.noun.prism_atom import PrismAtom
from apps.api.src.atoms.noun.quadratic_func_atom import QuadraticFuncAtom
from apps.api.src.atoms.noun.sample_atom import SampleAtom
from apps.api.src.atoms.noun.sequence_atom import SequenceAtom
from apps.api.src.atoms.verb.analyze_data_verb import AnalyzeDataVerb
from apps.api.src.atoms.verb.calculate_probability_verb import CalculateProbabilityVerb
from apps.api.src.atoms.verb.construct_geometry_verb import ConstructGeometryVerb
from apps.api.src.atoms.verb.estimate_population_verb import EstimatePopulationVerb
from apps.api.src.atoms.verb.find_angle_verb import FindAngleVerb
from apps.api.src.atoms.verb.form_shape_verb import FormShapeVerb
from apps.api.src.atoms.verb.generalize_formula_verb import GeneralizeFormulaVerb
from apps.api.src.atoms.verb.intersect_verb import IntersectVerb
from apps.api.src.atoms.verb.locus_verb import LocusVerb
from apps.api.src.atoms.verb.measure_geometry_verb import MeasureGeometryVerb
from apps.api.src.atoms.verb.prove_algebraic_verb import ProveAlgebraicVerb
from apps.api.src.atoms.verb.prove_geometry_verb import ProveGeometryVerb
from apps.api.src.atoms.verb.slice_solid_verb import SliceSolidVerb
from apps.api.src.atoms.verb.solve_eq_verb import SolveEqVerb
from apps.api.src.atoms.verb.transform_shape_verb import TransformShapeVerb
from apps.api.src.atoms.verb.unfold_net_verb import UnfoldNetVerb
from apps.api.src.core.abc.atoms import AtomConstraints


def _ac(**kw) -> AtomConstraints:
    return AtomConstraints(difficulty_band=(1, 50), forbidden_tags=[], seed=42, custom=kw)


def _num(v: int) -> NumberAtom:
    return NumberAtom(value=sympy.Integer(v))


# validate rejection paths
def test_solve_eq_rejects_empty() -> None:
    ok, _ = SolveEqVerb().validate()
    assert ok is False


def test_slice_rejects_wrong_type() -> None:
    ok, _ = SliceSolidVerb().validate(_num(3))
    assert ok is False


def test_slice_rejects_empty() -> None:
    ok, _ = SliceSolidVerb().validate()
    assert ok is False


def test_unfold_rejects_wrong_type() -> None:
    ok, _ = UnfoldNetVerb().validate(_num(3))
    assert ok is False


def test_unfold_solve_returns_area() -> None:
    prism = PrismAtom().sample(_ac(is_cube=True, max_height=5), random.Random(0))
    step = UnfoldNetVerb().solve(prism, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_transform_rejects_wrong_type() -> None:
    ok, _ = TransformShapeVerb().validate(_num(3))
    assert ok is False


def test_transform_rotation() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="square"), random.Random(0))
    step = TransformShapeVerb("rotation").solve(poly, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_transform_reflection() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="square"), random.Random(0))
    step = TransformShapeVerb("reflection").solve(poly, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_transform_revolution_polygon() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="rectangle"), random.Random(0))
    step = TransformShapeVerb("revolution").solve(poly, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_construct_rejects_wrong_type() -> None:
    ok, _ = ConstructGeometryVerb().validate(_num(3))
    assert ok is False


def test_construct_other_types() -> None:
    from apps.api.src.atoms.noun.point_atom import PointAtom

    p = PointAtom().sample(_ac(), random.Random(0))
    for t in ("angle_bisector", "perpendicular", "tangent", "copy_length"):
        step = ConstructGeometryVerb(t).solve(p, rng=random.Random(0))
        assert int(step.sympy_expr) >= 1


def test_prove_algebraic_rejects_wrong_type() -> None:
    from apps.api.src.atoms.noun.polygon_atom import PolygonAtom

    poly = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(0))
    ok, _ = ProveAlgebraicVerb().validate(poly)
    assert ok is False


def test_prove_geometry_rejects_one_atom() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="triangle"), random.Random(0))
    ok, _ = ProveGeometryVerb().validate(poly)
    assert ok is False


def test_form_shape_rejects_few_points() -> None:
    from apps.api.src.atoms.noun.point_atom import PointAtom

    p = PointAtom().sample(_ac(), random.Random(0))
    ok, _ = FormShapeVerb().validate(p)
    assert ok is False


def test_form_shape_rejects_degenerate() -> None:
    from apps.api.src.atoms.noun.point_atom import PointAtom

    p = PointAtom(x=sympy.Integer(0), y=sympy.Integer(0))
    ok, _ = FormShapeVerb().validate(p, p, p)
    assert ok is False


def test_intersect_quadratic_and_linear() -> None:
    q = QuadraticFuncAtom().sample(_ac(max_a_value=3), random.Random(0))
    f = LinearFuncAtom().sample(_ac(max_slope=3), random.Random(1))
    ok, _ = IntersectVerb().validate(q, f)
    assert ok is True


def test_locus_rejects_empty() -> None:
    ok, _ = LocusVerb().validate()
    assert ok is False


def test_locus_rejects_wrong_type() -> None:
    ok, _ = LocusVerb().validate(_num(3))
    assert ok is False


def test_locus_single_point() -> None:
    from apps.api.src.atoms.noun.point_atom import PointAtom

    p = PointAtom().sample(_ac(), random.Random(0))
    step = LocusVerb("custom").solve(p, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_find_angle_rejects_wrong_type() -> None:
    ok, _ = FindAngleVerb().validate(_num(3))
    assert ok is False


def test_find_angle_default_branch() -> None:
    poly = PolygonAtom().sample(_ac(polygon_type="square"), random.Random(0))
    step = FindAngleVerb("tangent_chord").solve(poly, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_measure_rejects_distance_with_one_point() -> None:
    from apps.api.src.atoms.noun.point_atom import PointAtom

    p = PointAtom().sample(_ac(), random.Random(0))
    ok, _ = MeasureGeometryVerb("distance").validate(p)
    assert ok is False


def test_measure_rejects_wrong_type() -> None:
    ok, _ = MeasureGeometryVerb().validate(_num(3))
    assert ok is False


def test_probability_rejects_wrong_type() -> None:
    ok, _ = CalculateProbabilityVerb().validate(_num(3))
    assert ok is False


def test_probability_default_favorable() -> None:
    event = EventAtom().sample(_ac(event_type="coin", num_trials=1), random.Random(0))
    step = CalculateProbabilityVerb().solve(event, rng=random.Random(0))
    assert step.sympy_expr.is_Rational


def test_analyze_rejects_small_data() -> None:
    ds = DataSetAtom().sample(_ac(data_size=20), random.Random(0))
    ok, _ = AnalyzeDataVerb().validate(ds)
    assert ok is True


def test_analyze_iqr() -> None:
    ds = DataSetAtom().sample(_ac(data_size=10), random.Random(0))
    step = AnalyzeDataVerb("iqr").solve(ds, rng=random.Random(0))
    assert step.sympy_expr is not None


def test_estimate_rejects_wrong_type() -> None:
    ok, _ = EstimatePopulationVerb().validate(_num(3))
    assert ok is False


def test_generalize_rejects_wrong_type() -> None:
    ok, _ = GeneralizeFormulaVerb().validate(_num(3))
    assert ok is False


def test_generalize_rejects_no_nth() -> None:
    class Bogus(SequenceAtom):
        def get_symbols(self):  # type: ignore[override]
            return {}

    ok, _ = GeneralizeFormulaVerb().validate(Bogus())
    assert ok is False
