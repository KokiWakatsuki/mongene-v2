"""Atom 抽選アルゴリズム（§38）"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Type

from apps.api.src.atoms.registry import find_nouns_by_tags, get_noun_class
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom
from apps.api.src.core.abc.blueprint import BlueprintDefinition, NounSlot
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.exceptions import NoCompatibleAtomError


class AtomSelector:
    """NounSlot に対して適合する Atom を抽選する"""

    def select(
        self,
        blueprint: BlueprintDefinition,
        atom_constraints: Dict[str, Any],
        rng: random.Random,
        diversity: DiversityRotation,
    ) -> Dict[str, NounAtom]:
        result: Dict[str, NounAtom] = {}
        for slot_name, slot in blueprint.noun_slots.items():
            atom_cls = self._select_one(slot, rng, diversity)
            constraints = self._build_atom_constraints(atom_cls, atom_constraints, rng)
            instance = atom_cls().sample(constraints, rng)
            result[slot_name] = instance
            diversity.record_pick(slot_name, atom_cls.__name__)
        return result

    def _select_one(
        self,
        slot: NounSlot,
        rng: random.Random,
        diversity: DiversityRotation,
    ) -> Type[NounAtom]:
        if slot.accepted_noun_types:
            candidates_by_type: List[Type[NounAtom]] = []
            for name in slot.accepted_noun_types:
                try:
                    candidates_by_type.append(get_noun_class(name))
                except KeyError:
                    continue
        else:
            candidates_by_type = find_nouns_by_tags([], [])

        candidates = [
            c
            for c in candidates_by_type
            if all(t in getattr(c, "tags", []) for t in slot.accepted_tags)
        ]
        if not candidates:
            raise NoCompatibleAtomError(slot.slot_name)

        filtered = diversity.filter_candidates(slot.slot_name, candidates)
        if not filtered:
            filtered = candidates

        return rng.choice(filtered)

    def _build_atom_constraints(
        self,
        atom_cls: Type[NounAtom],
        mapping_atom_constraints: Dict[str, Any],
        rng: random.Random,
    ) -> AtomConstraints:
        custom = dict(mapping_atom_constraints.get(atom_cls.__name__, {}))
        return AtomConstraints(
            difficulty_band=(1, 100),
            forbidden_tags=[],
            seed=rng.randint(0, 1_000_000),
            custom=custom,
        )
