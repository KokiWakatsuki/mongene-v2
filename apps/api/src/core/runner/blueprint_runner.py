"""Blueprint runner メインループ（§37）"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apps.api.src.core.abc.atoms import NounAtom
from apps.api.src.core.abc.blueprint import BlueprintDefinition
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.evaluation.solvability import is_clean
from apps.api.src.core.exceptions import (
    CleanSolutionExhaustedError,
    LLMTranslationFailedError,
    NoCompatibleBlueprintError,
    VerbValidationError,
)
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.representation.middle_representation import (
    LogicStep,
    MiddleRepresentation,
)
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.difficulty_reconciler import reconcile_difficulty
from apps.api.src.core.runner.subquestion_builder import build_sub_questions


class _FallbackAtomNeeded(Exception):
    def __init__(self, slot: str) -> None:
        self.slot = slot


@dataclass
class GenerationRequest:
    """BlueprintRunner.run の入力（API 層から渡される簡易版）"""

    target_difficulty: int
    problem_form: str
    lesson_id: str
    unlearned_lesson_ids: List[str] = field(default_factory=list)


@dataclass
class GeneratedProblem:
    middle_representation: MiddleRepresentation
    problem_text: str
    sub_question_texts: List[Dict]
    explanation_text: str
    diagram_url: Optional[str]


class BlueprintRunner:
    def __init__(
        self,
        dedup: DuplicationGuard,
        diversity: DiversityRotation,
        translator: LLMTranslator,
        atom_selector: AtomSelector,
        blueprint_loader: Any,
        scenario_bank: Any = None,
        max_retries: int = 50,
    ) -> None:
        self.dedup = dedup
        self.diversity = diversity
        self.translator = translator
        self.atom_selector = atom_selector
        self.blueprint_loader = blueprint_loader
        self.scenarios = scenario_bank
        self.max_retries = max_retries

    def run(self, request: GenerationRequest, mapping: Dict[str, Any]) -> GeneratedProblem:
        blueprint = self.blueprint_loader(mapping["execute_blueprint"])

        plan = reconcile_difficulty(
            target=request.target_difficulty,
            y_base=int(mapping.get("y_base", 50)),
            blueprint=blueprint,
            problem_form=request.problem_form,
        )
        if plan.unsatisfiable:
            raise NoCompatibleBlueprintError(plan.reason or "難易度が達成不能")

        blueprint = plan.blueprint
        atom_constraints = mapping.get("atom_constraints", {})

        base_seed = random.randint(1000, 9999)
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            seed = base_seed + attempt
            rng = random.Random(seed)

            try:
                sampled_nouns = self.atom_selector.select(
                    blueprint=blueprint,
                    atom_constraints=atom_constraints,
                    rng=rng,
                    diversity=self.diversity,
                )

                selected_tags = self._aggregate_tags(sampled_nouns, mapping)

                logic_steps_by_slot: Dict[str, LogicStep] = {}
                for invocation in blueprint.verb_invocations:
                    inputs = [
                        self._resolve_slot(s, sampled_nouns, logic_steps_by_slot)
                        for s in invocation.input_slots
                    ]
                    ok, reason = invocation.verb.validate(*inputs)
                    if not ok:
                        if invocation.on_failure == "retry_seed":
                            raise VerbValidationError(
                                type(invocation.verb).__name__, reason
                            )
                        if invocation.on_failure == "fallback_atom":
                            raise _FallbackAtomNeeded(invocation.input_slots[-1])
                        raise NoCompatibleBlueprintError(reason or "verb 検証失敗")
                    step = invocation.verb.solve(*inputs, rng=rng)
                    logic_steps_by_slot[invocation.output_slot] = step

                if not logic_steps_by_slot:
                    raise VerbValidationError("BlueprintRunner", "logic_steps が空")

                final_step = list(logic_steps_by_slot.values())[-1]
                clean_config = dict(mapping.get("is_clean_override", {}))
                disabled = clean_config.pop("disabled", False)
                if not disabled and not is_clean(final_step.sympy_expr, **clean_config):
                    continue

                sub_questions = build_sub_questions(
                    strategy=blueprint.subquestion_strategy,
                    sampled_nouns=sampled_nouns,
                    logic_steps_all=list(logic_steps_by_slot.values()),
                )

                from apps.api.src.visuals.builder import build_visual_dsl

                visual_dsl = build_visual_dsl(blueprint, sampled_nouns, logic_steps_by_slot)

                mr = MiddleRepresentation(
                    problem_structure_type=blueprint.blueprint_id,
                    selected_tags=selected_tags,
                    difficulty_score=float(plan.computed_difficulty),
                    problem_form=request.problem_form,  # type: ignore[arg-type]
                    sub_questions=sub_questions,
                    visual_dsl=visual_dsl,
                    seed=seed,
                    blueprint_id=blueprint.blueprint_id,
                    blueprint_version=blueprint.blueprint_version,
                )

                if not mapping.get("dedup_disabled", False) and self.dedup.is_duplicate(mr):
                    continue

                # WordProblemStructure 等で story_required な場合は ScenarioBank から StoryContext を取得
                story = None
                if blueprint.story_required and self.scenarios is not None:
                    try:
                        story = self.scenarios.select_for_lesson(
                            mapping.get("target_lesson_id", request.lesson_id),
                            rng,
                        )
                    except Exception:
                        story = None

                problem_text, sub_texts, explanation = self.translator.translate(
                    mr=mr,
                    story=story,
                    lesson_grade=int(mapping.get("grade", 1)),
                )

                self.dedup.register(mr, problem_text)

                return GeneratedProblem(
                    middle_representation=mr,
                    problem_text=problem_text,
                    sub_question_texts=sub_texts,
                    explanation_text=explanation,
                    diagram_url=None,
                )

            except (VerbValidationError, _FallbackAtomNeeded) as e:
                last_error = e
                continue
            except LLMTranslationFailedError as e:
                last_error = e
                if attempt >= 3:
                    break
                continue

        raise CleanSolutionExhaustedError(
            f"Blueprint {blueprint.blueprint_id} を {self.max_retries} 回試行しても綺麗な問題を生成できませんでした。Last error: {last_error}"
        )

    def _aggregate_tags(
        self,
        sampled_nouns: Dict[str, NounAtom],
        mapping: Dict[str, Any],
    ) -> List[str]:
        tags: set[str] = set(mapping.get("required_tags", []))
        for noun in sampled_nouns.values():
            tags.update(getattr(noun, "tags", []))
        return sorted(tags)

    def _resolve_slot(
        self,
        slot_name: str,
        sampled_nouns: Dict[str, NounAtom],
        logic_steps_by_slot: Dict[str, LogicStep],
    ) -> Any:
        if slot_name in sampled_nouns:
            return sampled_nouns[slot_name]
        if slot_name in logic_steps_by_slot:
            return logic_steps_by_slot[slot_name]
        raise KeyError(f"未知のスロット: {slot_name}")
