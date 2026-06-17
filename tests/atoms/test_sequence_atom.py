"""SequenceAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.sequence_atom import SequenceAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_sequence_atom_arithmetic_first_term_matches() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=42,
        custom={"pattern_type": "arithmetic"},
    )
    atom = SequenceAtom().sample(c, rng)
    assert atom.pattern_type == "arithmetic"
    n = sympy.Symbol("n", positive=True, integer=True)
    # nth_term(n=1) == first_term
    val_at_1 = sympy.simplify(atom.nth_term_expr.subs(n, 1) - atom.first_term)
    assert val_at_1 == 0
    assert atom.step_rule["type"] == "arithmetic"
    assert "common_difference" in atom.step_rule


def test_sequence_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=7,
        custom={"pattern_type": "geometric"},
    )
    a1 = SequenceAtom().sample(c, random.Random(7))
    a2 = SequenceAtom().sample(c, random.Random(7))
    assert sympy.simplify(a1.nth_term_expr - a2.nth_term_expr) == 0
    assert sympy.simplify(a1.first_term - a2.first_term) == 0
    assert a1.step_rule == a2.step_rule


def test_sequence_atom_get_symbols() -> None:
    rng = random.Random(3)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=3,
        custom={"pattern_type": "figurate"},
    )
    atom = SequenceAtom().sample(c, rng)
    symbols = atom.get_symbols()
    assert {"nth_term_expr", "first_term"} <= set(symbols.keys())
    assert symbols["nth_term_expr"] == atom.nth_term_expr
    assert atom.min_terms_required >= 3


def test_sequence_atom_fraction_pattern() -> None:
    rng = random.Random(5)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=5,
        custom={"pattern_type": "fraction_seq"},
    )
    atom = SequenceAtom().sample(c, rng)
    assert atom.pattern_type == "fraction_seq"
    assert atom.step_rule["type"] == "fraction_seq"
