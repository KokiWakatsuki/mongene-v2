"""Atom 抽選アルゴリズム（§38）

設計書 §38.2 の正しい実装:
  slot.accepted_tags が空のとき → mapping の required_tags で代替フィルタ
  → BasicCalculationStructure のような汎用 Blueprint で
    lesson ごとに異なる Atom（NumberAtom/PolynomialAtom/SquareRootAtom）を選べる
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Type

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
        required_tags: Optional[List[str]] = None,
        preferred_noun_types: Optional[List[str]] = None,
    ) -> Dict[str, NounAtom]:
        result: Dict[str, NounAtom] = {}
        for slot_name, slot in blueprint.noun_slots.items():
            atom_cls = self._select_one(
                slot, rng, diversity, required_tags, atom_constraints, preferred_noun_types
            )
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
        required_tags: Optional[List[str]] = None,
        atom_constraints: Optional[Dict[str, Any]] = None,
        preferred_noun_types: Optional[List[str]] = None,
    ) -> Type[NounAtom]:
        # Step 1: 型フィルタ（accepted_noun_types が空なら全 Atom を候補に）
        if slot.accepted_noun_types:
            candidates_by_type: List[Type[NounAtom]] = []
            for name in slot.accepted_noun_types:
                try:
                    candidates_by_type.append(get_noun_class(name))
                except KeyError:
                    continue
        else:
            candidates_by_type = find_nouns_by_tags([], [])

        # Step 2: タグフィルタ（§38.2 の設計書通り）
        # 優先順位:
        #   1. required_tags が非空 → 型ホワイトリスト内で OR フィルタ
        #      例: polynomial タグ lesson → PolynomialAtom（型リスト内にある場合）
        #      例: linear_equation タグ lesson → EquationAtom が型リストになければ NumberAtom にフォールバック
        #   2. required_tags が空 → slot.accepted_tags の AND フィルタ
        if required_tags:
            # 型ホワイトリスト内で required_tags の ANY にマッチする Atom
            tagged: List[Type[NounAtom]] = []
            for tag in required_tags:
                for cls in candidates_by_type:
                    if tag in getattr(cls, "tags", []) and cls not in tagged:
                        tagged.append(cls)
            if tagged:
                # 型ホワイトリスト内に対応 Atom があれば使う
                candidates = tagged
            else:
                # 型ホワイトリスト内に required_tags に合う Atom がない → accepted_tags フォールバック
                candidates = [
                    c for c in candidates_by_type
                    if all(t in getattr(c, "tags", []) for t in slot.accepted_tags)
                ] or list(candidates_by_type)
        else:
            # required_tags が空 → slot.accepted_tags の AND フィルタ
            candidates = [
                c
                for c in candidates_by_type
                if all(t in getattr(c, "tags", []) for t in slot.accepted_tags)
            ]

        if not candidates:
            raise NoCompatibleAtomError(slot.slot_name)

        # 特定 Atom 型が明示指定されていれば、その型に選択を絞る（tag駆動でCircleAtom等が
        # 混入するのを防ぐ）。優先順位:
        #   1. preferred_noun_types（レベル固有 atom_constraints のキー＝そのレベルの意図する型）。
        #      トップレベルが複数型のメニューを持っていてもレベルの意図を優先する。
        #   2. atom_constraints のキー（レベル情報が無い旧パス用フォールバック）。
        # いずれも候補内に該当型がある場合のみ適用（無ければ従来どおり）。
        for type_source in (preferred_noun_types, atom_constraints):
            if type_source:
                constrained = [c for c in candidates if c.__name__ in type_source]
                if constrained:
                    candidates = constrained
                    break

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
