"""SampleAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.sample_atom import SampleAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_sample_atom_sample_constraints() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=42,
        custom={
            "population_size": 2000,
            "sample_size": 100,
            "target_attribute": "不良品割合",
        },
    )
    atom = SampleAtom().sample(c, rng)
    assert atom.population_size == 2000
    assert atom.sample_size == 100
    assert atom.target_attribute == "不良品割合"
    assert 0 <= atom.sample_count <= atom.sample_size
    # population_estimate = population_size * sample_count / sample_size
    expected = sympy.Rational(2000 * atom.sample_count, 100)
    assert sympy.simplify(atom.population_estimate - expected) == 0


def test_sample_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=11,
        custom={"population_size": 5000, "sample_size": 200},
    )
    a1 = SampleAtom().sample(c, random.Random(11))
    a2 = SampleAtom().sample(c, random.Random(11))
    assert a1.sample_count == a2.sample_count
    assert sympy.simplify(a1.population_estimate - a2.population_estimate) == 0


def test_sample_atom_get_symbols() -> None:
    rng = random.Random(9)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=9,
        custom={"population_size": 1000, "sample_size": 50, "sample_count": 5},
    )
    atom = SampleAtom().sample(c, rng)
    symbols = atom.get_symbols()
    assert {"population_size", "sample_size", "sample_count", "population_estimate"} <= set(
        symbols.keys()
    )
    assert int(symbols["population_size"]) == 1000
    assert int(symbols["sample_size"]) == 50
    assert int(symbols["sample_count"]) == 5
    # 1000 * 5 / 50 = 100
    assert int(symbols["population_estimate"]) == 100
