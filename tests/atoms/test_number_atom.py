"""NumberAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

from apps.api.src.atoms.noun.number_atom import NumberAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_number_atom_sample_returns_integer() -> None:
    rng = random.Random(42)
    constraints = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=42,
        custom={"allow_negative": False, "max_value": 100},
    )
    noun = NumberAtom().sample(constraints, rng)
    symbols = noun.get_symbols()
    assert bool(symbols["value"].is_integer) is True
    assert 0 <= int(symbols["value"]) <= 100


def test_number_atom_seed_reproducibility() -> None:
    c = AtomConstraints(difficulty_band=(1, 10), forbidden_tags=[], seed=42, custom={"max_value": 30})
    n1 = NumberAtom().sample(c, random.Random(42))
    n2 = NumberAtom().sample(c, random.Random(42))
    assert str(n1.get_symbols()["value"]) == str(n2.get_symbols()["value"])


def test_number_atom_force_fraction() -> None:
    rng = random.Random(7)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=7,
        custom={"force_fraction": True, "max_value": 20, "allow_negative": False},
    )
    noun = NumberAtom().sample(c, rng)
    val = noun.get_symbols()["value"]
    assert val.is_Rational
    assert val.q != 1  # 真の分数（分母 != 1）
