"""ProveAngleRelationVerb のテスト（平行線の角の証明・moat）。"""
from __future__ import annotations

import json
import random

import sympy

from apps.api.src.atoms.noun.line_angle_atom import LineAngleAtom
from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.atoms.verb.prove_angle_relation_verb import ProveAngleRelationVerb


def test_validate_rejects_non_line_angle_atom() -> None:
    ok, reason = ProveAngleRelationVerb().validate(NumberAtom(value=sympy.Integer(1)))
    assert ok is False and reason is not None


def _proof(relation: str, angle: int) -> dict:
    atom = LineAngleAtom(known_angle=sympy.Integer(angle), relation_type=relation)
    step = ProveAngleRelationVerb().solve(atom, rng=random.Random(0))
    assert step.operation_name == f"prove_angle_{relation}"
    return json.loads(step.operands[-1])


def test_alternate_and_corresponding_conclude_equal() -> None:
    for rel in ("alternate", "corresponding"):
        po = _proof(rel, 72)
        assert "等しい" in po["to_prove"]
        assert "72" in po["conclusion"]
        assert len(po["steps"]) >= 2


def test_co_interior_sums_to_180() -> None:
    po = _proof("co_interior", 110)
    assert "180" in po["to_prove"]
    # 補角 70 が現れ、和が 180
    assert "70" in po["conclusion"] or any("70" in s["statement"] for s in po["steps"])


def test_moat_rejects_tampered_atom() -> None:
    """target_angle が relation と矛盾する不正な atom は AssertionError で弾く（moat）。"""
    class _Bad(LineAngleAtom):
        def get_symbols(self):
            return {"known_angle": sympy.Integer(60), "target_angle": sympy.Integer(61)}

    bad = _Bad(known_angle=sympy.Integer(60), relation_type="alternate")
    try:
        ProveAngleRelationVerb().solve(bad, rng=random.Random(0))
        raise AssertionError("moat が働かなかった")
    except AssertionError as e:
        assert "錯角" in str(e)
