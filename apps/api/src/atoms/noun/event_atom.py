"""EventAtom（§18.1）

事象（サイコロ・硬貨・カード・玉・くじ）を表す Atom。樹形図 DSL を内包し、
CalculateProbabilityVerb の入力となる。
"""
from __future__ import annotations

import random
from typing import Any, ClassVar, Dict, List

import sympy

from apps.api.src.atoms.registry import register_noun
from apps.api.src.core.abc.atoms import AtomConstraints, NounAtom


_EVENT_TYPES = ("dice", "coin", "card_draw", "ball_draw", "lottery")


@register_noun
class EventAtom(NounAtom):
    tags: ClassVar[List[str]] = ["probability", "dice", "cards"]

    def __init__(
        self,
        event_type: str = "dice",
        sample_space_size: int = 6,
        event_descriptors: List[Dict[str, Any]] | None = None,
        tree_dsl: Dict[str, Any] | None = None,
        num_trials: int = 1,
        with_replacement: bool = True,
    ) -> None:
        self.event_type: str = event_type
        self.sample_space_size: int = sample_space_size
        self.event_descriptors: List[Dict[str, Any]] = event_descriptors or []
        self.tree_dsl: Dict[str, Any] = tree_dsl or {"nodes": [], "edges": []}
        self.num_trials: int = num_trials
        self.with_replacement: bool = with_replacement

    def sample(self, constraints: AtomConstraints, rng: random.Random) -> "EventAtom":
        custom = constraints.custom or {}
        event_type: str = str(custom.get("event_type", rng.choice(_EVENT_TYPES)))
        if event_type not in _EVENT_TYPES:
            event_type = "dice"
        num_trials: int = max(1, int(custom.get("num_trials", rng.randint(1, 2))))
        with_replacement: bool = bool(custom.get("with_replacement", True))

        # 単一試行のサンプル数
        if event_type == "dice":
            unit_size = 6
            outcomes: List[str] = [str(i) for i in range(1, 7)]
        elif event_type == "coin":
            unit_size = 2
            outcomes = ["表", "裏"]
        elif event_type == "card_draw":
            unit_size = int(custom.get("card_count", rng.randint(4, 10)))
            outcomes = [f"カード{i}" for i in range(1, unit_size + 1)]
        elif event_type == "ball_draw":
            red = int(custom.get("red_balls", rng.randint(1, 4)))
            white = int(custom.get("white_balls", rng.randint(1, 4)))
            unit_size = red + white
            outcomes = [f"赤{i}" for i in range(1, red + 1)] + [
                f"白{i}" for i in range(1, white + 1)
            ]
        else:  # lottery
            unit_size = int(custom.get("lottery_count", rng.randint(5, 20)))
            outcomes = [f"くじ{i}" for i in range(1, unit_size + 1)]

        # 標本空間サイズ（復元 / 非復元）
        if with_replacement:
            sample_space_size = unit_size**num_trials
        else:
            sample_space_size = 1
            for k in range(num_trials):
                size = unit_size - k
                if size <= 0:
                    size = 1
                sample_space_size *= size

        # 事象記述（各試行ごとの記述）
        event_descriptors: List[Dict[str, Any]] = [
            {"trial": i + 1, "outcomes": list(outcomes)} for i in range(num_trials)
        ]

        # 樹形図 DSL（簡易版）
        nodes: List[Dict[str, Any]] = [{"id": "root", "label": "スタート"}]
        edges: List[Dict[str, Any]] = []
        # 試行 1 のみ展開（深い場合は省略）
        for idx, outcome in enumerate(outcomes):
            nid = f"n1_{idx}"
            nodes.append({"id": nid, "label": outcome})
            edges.append({"from": "root", "to": nid, "label": f"1/{unit_size}"})
        tree_dsl: Dict[str, Any] = {
            "nodes": nodes,
            "edges": edges,
            "depth": num_trials,
        }

        return EventAtom(
            event_type=event_type,
            sample_space_size=sample_space_size,
            event_descriptors=event_descriptors,
            tree_dsl=tree_dsl,
            num_trials=num_trials,
            with_replacement=with_replacement,
        )

    def get_symbols(self) -> Dict[str, Any]:  # type: ignore[override]
        return {
            "sample_space_size": sympy.Integer(self.sample_space_size),
            "num_trials": sympy.Integer(self.num_trials),
            "event_descriptors": self.event_descriptors,  # CalculateProbabilityVerb が参照
        }

    @classmethod
    def estimate_param_space(cls, constraints: AtomConstraints) -> int:
        custom = constraints.custom or {}
        num_trials = int(custom.get("num_trials", 2))
        # 5 event_types × num_trials variations
        return len(_EVENT_TYPES) * max(1, num_trials) * 20
