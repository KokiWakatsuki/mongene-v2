"""文章題シナリオバンク（§25.2）

scenarios.yaml から StoryContext を選択して WordProblemStructure に注入する。
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from apps.api.src.core.abc.blueprint import StoryContext
from apps.api.src.core.exceptions import NoScenarioFoundError


@dataclass
class ScenarioBank:
    scenarios: List[Dict[str, Any]]

    @classmethod
    def load(cls, path: Optional[Path | str] = None) -> "ScenarioBank":
        if path is None:
            path = Path(__file__).resolve().parents[5] / "master_data" / "scenarios.yaml"
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(scenarios=list(data.get("scenarios", [])))

    def select_for_lesson(
        self,
        lesson_id: str,
        rng: random.Random,
    ) -> StoryContext:
        candidates = [
            s for s in self.scenarios if lesson_id in s.get("applicable_lesson_ids", [])
        ]
        if not candidates:
            # フォールバック: applicable_lesson_ids が無くてもカテゴリベースで適当に選ぶ
            candidates = self.scenarios
        if not candidates:
            raise NoScenarioFoundError(f"lesson_id={lesson_id} に対応するシナリオなし")

        chosen = rng.choice(candidates)
        characters = chosen.get("characters", ["太郎"])
        character_a = rng.choice(characters) if characters else "太郎"
        templates = chosen.get("narrative_templates", [""])
        return StoryContext(
            scenario_id=chosen["id"],
            characters=[character_a],
            setting=chosen.get("setting", ""),
            units=self._pick_units(chosen, rng),
            narrative_hint=rng.choice(templates) if templates else "",
        )

    def _pick_units(self, scenario: Dict[str, Any], rng: random.Random) -> Dict[str, str]:
        units_spec = scenario.get("units", {})
        result: Dict[str, str] = {}
        for k, choices in units_spec.items():
            if isinstance(choices, list) and choices:
                result[k] = rng.choice(choices)
            elif isinstance(choices, str):
                result[k] = choices
        return result
