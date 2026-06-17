"""DataSetAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

import sympy

from apps.api.src.atoms.noun.data_set_atom import DataSetAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_data_set_atom_sample_constraints() -> None:
    rng = random.Random(42)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=42,
        custom={
            "data_size": 20,
            "value_range": (0, 50),
            "distribution_type": "uniform",
        },
    )
    atom = DataSetAtom().sample(c, rng)
    assert len(atom.values) == 20
    for v in atom.values:
        assert 0 <= int(v) <= 50
    assert atom.distribution_type == "uniform"
    assert len(atom.frequency_distribution) == 5
    # 度数合計はデータ数と一致
    total = sum(count for _, _, count in atom.frequency_distribution)
    assert total == 20


def test_data_set_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=7,
        custom={"data_size": 15, "value_range": (1, 30), "distribution_type": "normal"},
    )
    a1 = DataSetAtom().sample(c, random.Random(7))
    a2 = DataSetAtom().sample(c, random.Random(7))
    assert [int(v) for v in a1.values] == [int(v) for v in a2.values]
    assert sympy.simplify(a1.mean - a2.mean) == 0


def test_data_set_atom_get_symbols_and_stats() -> None:
    rng = random.Random(3)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=3,
        custom={"data_size": 11, "value_range": (1, 20), "distribution_type": "uniform"},
    )
    atom = DataSetAtom().sample(c, rng)
    symbols = atom.get_symbols()
    assert {"mean", "median", "mode", "q1", "q3", "size"} <= set(symbols.keys())
    assert int(symbols["size"]) == 11
    # mean は値域内に収まる
    assert 1 <= float(symbols["mean"]) <= 20
    # q1 <= median <= q3
    assert float(symbols["q1"]) <= float(symbols["median"]) <= float(symbols["q3"])
