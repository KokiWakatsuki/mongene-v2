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


def test_event_condition_favorable_is_valid_probability() -> None:
    """事象条件の適合数は必ず 1 以上・標本空間未満（自明でない確率）で、標本空間と整合する。"""
    for et in ("dice", "coin", "card_draw", "ball_draw", "lottery"):
        for nt in (1, 2):
            for seed in range(5):
                c = AtomConstraints(
                    difficulty_band=(1, 10),
                    forbidden_tags=[],
                    seed=seed,
                    custom={"event_type": et, "num_trials": nt},
                )
                atom = EventAtom().sample(c, random.Random(seed))
                fav = atom.event_condition["favorable"]
                ss = atom.sample_space_size
                assert 1 <= fav < ss, f"{et} nt={nt} seed={seed}: fav={fav} ss={ss}"
                assert atom.event_condition["description"]


def test_event_condition_dice_even_is_half() -> None:
    """1つのさいころで偶数の目の適合数は 3（=3/6）と厳密に一致する。"""
    # seed を探索して「偶数」条件を引く
    for seed in range(30):
        c = AtomConstraints(
            difficulty_band=(1, 10), forbidden_tags=[], seed=seed,
            custom={"event_type": "dice", "num_trials": 1},
        )
        atom = EventAtom().sample(c, random.Random(seed))
        if "偶数" in atom.event_condition["description"]:
            assert atom.event_condition["favorable"] == 3
            assert atom.sample_space_size == 6
            return
    raise AssertionError("偶数条件が生成されなかった")


def test_probability_verb_uses_derived_favorable() -> None:
    from apps.api.src.atoms.verb.calculate_probability_verb import CalculateProbabilityVerb

    c = AtomConstraints(
        difficulty_band=(1, 10), forbidden_tags=[], seed=3,
        custom={"event_type": "ball_draw", "num_trials": 1, "red_balls": 3, "white_balls": 1},
    )
    atom = EventAtom().sample(c, random.Random(3))
    step = CalculateProbabilityVerb().solve(atom, rng=random.Random(3))
    # 適合数 = event_condition の favorable（乱数でなく決定論的）
    import sympy
    expected = sympy.Rational(atom.event_condition["favorable"], atom.sample_space_size)
    assert step.sympy_expr == expected


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
