"""Task1: core 骨格の unit テスト（contracts / rng / registry / signature）。"""
from __future__ import annotations

import pytest
import sympy

from engine.core import rng as rngmod
from engine.core.contracts import (
    Coordinate,
    GenerateRequest,
    MR,
    Provenance,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    Unsupported,
)
from engine.core.registry import _Registry
from engine.core.rng import DomainError, derive_rng, draw, draw_many, validate_domain
from engine.core.signature import dup_key, fingerprint, fingerprint_hash


# ---------------------------------------------------------------------------
# contracts
# ---------------------------------------------------------------------------
def test_request_defaults_and_extra_forbidden():
    r = GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=2)
    assert r.purpose == "base"
    assert r.seed is None
    with pytest.raises(Exception):
        GenerateRequest(subject="math", unit="x", form="f", level=1, bogus=1)  # type: ignore[call-arg]


def test_unsupported_code_validation():
    Unsupported(code="unit_not_found", detail="x")
    with pytest.raises(Exception):
        Unsupported(code="totally_unknown_code")  # type: ignore[arg-type]


def test_answer_payload_discriminated_union():
    sq = SubQuestionMR(
        label="(1)", asked="expression",
        answer=SymbolicAnswer(srepr="x", display="y = 2x + 1"),
        steps=[], concept_tags=["c"], cause_tags=[],
    )
    assert sq.answer.kind == "symbolic"


def _mk_mr(sig="s1", ops=("a", "b"), given=None):
    given = given or {"point_a": "(1, 3)"}
    return MR(
        signature=sig, family="math.g2_l25.find_value", level=2, purpose="base", seed=1,
        params={"a": 3, "b": 0}, given=given,
        sub_questions=[SubQuestionMR(
            label="(1)", asked="expression",
            answer=SymbolicAnswer(srepr="x", display="y=3x"),
            steps=[Step(op=o, result_srepr="r", result_display="d", narration="n") for o in ops],
            concept_tags=["c"], cause_tags=[],
        )],
        provenance=Provenance(recipe="r"),
    )


# ---------------------------------------------------------------------------
# rng determinism
# ---------------------------------------------------------------------------
def test_derive_rng_is_deterministic():
    seq1 = [derive_rng("fam", 2, "base", 42).randint(0, 100) for _ in range(1)]
    seq2 = [derive_rng("fam", 2, "base", 42).randint(0, 100) for _ in range(1)]
    assert seq1 == seq2


def test_purpose_separates_streams():
    a = [derive_rng("fam", 2, "base", 42).randint(0, 10**6)]
    b = [derive_rng("fam", 2, "variant", 42).randint(0, 10**6)]
    assert a != b


def test_draw_int_range_within_bounds():
    r = derive_rng("f", 1, "base", 7)
    for _ in range(200):
        v = draw({"int_range": [-4, 4]}, r)
        assert -4 <= v <= 4


def test_draw_exclude():
    r = derive_rng("f", 1, "base", 7)
    for _ in range(200):
        v = draw({"int_range": [-2, 2], "exclude": [0]}, r)
        assert v != 0


def test_frac_range_is_reduced_and_not_integer():
    r = derive_rng("f", 1, "base", 3)
    for _ in range(100):
        v = draw({"frac_range": {"num": [-5, 5], "den": [2, 3]}}, r)
        assert isinstance(v, sympy.Rational)
        assert v.q != 1  # 非整数


def test_lattice_distinct_x():
    r = derive_rng("f", 1, "base", 9)
    pts = draw_many(
        {"lattice": {"x": {"int_range": [-5, 5]}, "y": {"int_range": [-8, 8]}}, "distinct": ["x"]},
        r, k=2,
    )
    assert pts[0][0] != pts[1][0]


def test_validate_domain_rejects_unknown_vocab():
    with pytest.raises(DomainError):
        validate_domain({"magic_domain": [1, 2]})


def test_validate_domain_accepts_registered():
    validate_domain({"int_range": [1, 5]})
    validate_domain({"frac_range": {"num": [1, 3], "den": [2, 4]}})
    validate_domain({"lattice": {"x": {"int_range": [0, 1]}, "y": {"int_set": [1, 2]}}})


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
def test_registry_recipe_register_and_lookup():
    reg = _Registry()

    @reg.register_recipe("math.demo", provides_concepts=["c1", "c2"])
    def _demo(ctx, rng):  # noqa: ANN001
        return None

    assert reg.has_recipe("math.demo")
    assert reg.recipe_concepts("math.demo") == frozenset({"c1", "c2"})
    with pytest.raises(KeyError):
        reg.recipe("nope")


def test_registry_duplicate_recipe_raises():
    reg = _Registry()

    @reg.register_recipe("dup")
    def _a(ctx, rng):  # noqa: ANN001
        return None

    with pytest.raises(ValueError):
        @reg.register_recipe("dup")
        def _b(ctx, rng):  # noqa: ANN001
            return None


def test_registry_gate_order_preserved():
    reg = _Registry()

    @reg.register_gate("mr", "g1")
    def _g1(obj, ctx):  # noqa: ANN001
        return True, ""

    @reg.register_gate("mr", "g2")
    def _g2(obj, ctx):  # noqa: ANN001
        return True, ""

    names = [n for n, _ in reg.gates("mr")]
    assert names == ["g1", "g2"]


# ---------------------------------------------------------------------------
# signature / fingerprint / dup_key
# ---------------------------------------------------------------------------
def test_fingerprint_stable_for_same_structure():
    fp1 = fingerprint(_mk_mr(ops=("a", "b")))
    fp2 = fingerprint(_mk_mr(ops=("a", "b")))
    assert fp1 == fp2


def test_fingerprint_differs_for_different_op_sequence():
    fp1 = fingerprint_hash(_mk_mr(ops=("a", "b")))
    fp2 = fingerprint_hash(_mk_mr(ops=("a", "b", "c")))
    assert fp1 != fp2


def test_dup_key_same_params_collide():
    assert dup_key(_mk_mr()) == dup_key(_mk_mr())


def test_dup_key_ignores_context_slots():
    m1 = _mk_mr()
    m2 = _mk_mr()
    m2.context_slots = {"name": "太郎"}
    assert dup_key(m1) == dup_key(m2)


def test_coordinate_roundtrip():
    c = Coordinate(subject="math", unit="g2_l25", form="find_value", level=2)
    assert c.model_dump()["unit"] == "g2_l25"
