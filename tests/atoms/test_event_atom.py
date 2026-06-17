"""EventAtom のユニットテスト（§34.1）"""
from __future__ import annotations

import random

from apps.api.src.atoms.noun.event_atom import EventAtom
from apps.api.src.core.abc.atoms import AtomConstraints


def test_event_atom_sample_dice_constraints() -> None:
    rng = random.Random(42)
    constraints = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=42,
        custom={"event_type": "dice", "num_trials": 2, "with_replacement": True},
    )
    atom = EventAtom().sample(constraints, rng)
    assert atom.event_type == "dice"
    assert atom.num_trials == 2
    assert atom.with_replacement is True
    # 6 面サイコロを 2 回（復元）= 36
    assert atom.sample_space_size == 36
    assert len(atom.event_descriptors) == 2
    assert "nodes" in atom.tree_dsl and "edges" in atom.tree_dsl


def test_event_atom_seed_reproducibility() -> None:
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=7,
        custom={"event_type": "ball_draw", "num_trials": 2, "with_replacement": False},
    )
    a1 = EventAtom().sample(c, random.Random(7))
    a2 = EventAtom().sample(c, random.Random(7))
    assert a1.sample_space_size == a2.sample_space_size
    assert a1.event_descriptors == a2.event_descriptors


def test_event_atom_get_symbols() -> None:
    rng = random.Random(123)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=123,
        custom={"event_type": "coin", "num_trials": 3},
    )
    atom = EventAtom().sample(c, rng)
    symbols = atom.get_symbols()
    assert "sample_space_size" in symbols
    assert "num_trials" in symbols
    # 2^3 = 8
    assert int(symbols["sample_space_size"]) == 8
    assert int(symbols["num_trials"]) == 3


def test_event_atom_non_replacement_decreases_size() -> None:
    rng = random.Random(2)
    c = AtomConstraints(
        difficulty_band=(1, 10),
        forbidden_tags=[],
        seed=2,
        custom={
            "event_type": "ball_draw",
            "num_trials": 2,
            "with_replacement": False,
            "red_balls": 3,
            "white_balls": 2,
        },
    )
    atom = EventAtom().sample(c, rng)
    # 5 * 4 = 20
    assert atom.sample_space_size == 20
