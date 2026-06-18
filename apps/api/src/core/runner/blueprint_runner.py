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
        # execute_blueprints（リスト）があればランダム選択、なければ execute_blueprint を使用
        blueprints_list = mapping.get("execute_blueprints")
        if blueprints_list and isinstance(blueprints_list, list) and len(blueprints_list) > 1:
            bp_id = random.choice(blueprints_list)
        else:
            bp_id = mapping.get("execute_blueprint", blueprints_list[0] if blueprints_list else "BasicCalculationStructure")
        blueprint = self.blueprint_loader(bp_id)

        plan = reconcile_difficulty(
            target=request.target_difficulty,
            y_base=int(mapping.get("y_base", 50)),
            blueprint=blueprint,
            problem_form=request.problem_form,
        )
        if plan.unsatisfiable:
            raise NoCompatibleBlueprintError(plan.reason or "難易度が達成不能")

        blueprint = plan.blueprint
        atom_constraints = {k: dict(v) for k, v in mapping.get("atom_constraints", {}).items()}

        # §12.4 全 delta_factors を Atom constraints に反映
        factors = plan.delta_factors
        raw_delta = request.target_difficulty - int(mapping.get("y_base", 50))

        # digit_penalty: 数値の桁数を増やす（+1 / 3桁以上の計算 → Atom の max_value/max_dim を拡大）
        if factors.get("digit_penalty", 0) > 0:
            scale = 1.0 + factors["digit_penalty"] * 0.2  # +20% per penalty point
            for cdict in atom_constraints.values():
                for key in ("max_dim", "max_height", "max_base_side", "max_radius",
                            "max_side_length", "max_value", "max_slope"):
                    if key in cdict:
                        cdict[key] = max(int(cdict[key]), int(cdict[key] * scale))

        # step_depth: 演算ステップを増やす（Blueprint の subquestion 戦略で target_count を加算）
        # ProofStructure / ConstructionStructure は固定構造なので対象外
        _no_depth_blueprints = {"ProofStructure", "ConstructionStructure", "BasicCalculationStructure"}
        if (factors.get("step_depth", 0) > 0
                and blueprint.subquestion_strategy is not None
                and blueprint.blueprint_id not in _no_depth_blueprints):
            import copy as _copy
            blueprint = _copy.deepcopy(blueprint)
            old_count = blueprint.subquestion_strategy.target_count
            blueprint.subquestion_strategy.target_count = min(
                old_count + factors["step_depth"] // 2, 5  # 最大 5 小問
            )

        # hint_reduction: 図あり(-2)=制約なし / 文章のみ(+3)=最小値を引き上げ（難易度下限を上げる）
        if factors.get("hint_reduction", 0) > 0:
            # 文章のみモード: Atom の値の下限を上げて「きれいでない」数値を増やす
            for cdict in atom_constraints.values():
                if "max_value" in cdict:
                    cdict.setdefault("min_value", max(5, int(cdict["max_value"] * 0.3)))

        # unit_mix_bonus: 複合単元（+2/単元追加）→ 制約を多様化
        # 現状 Atom レベルでは直接対応困難。LLM プロンプトへの目安として計算のみ

        # 時刻ベースの XOR で衝突を防ぐ（ナノ秒精度のため再生成でも別の問題が生成される）
        import time as _time
        base_seed = (random.randint(1, 1_000_000) ^ (int(_time.time_ns()) & 0xFFFFF)) % 1_000_000 + 1
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
                    logic_steps_by_slot=logic_steps_by_slot,
                )

                from apps.api.src.visuals.builder import build_visual_dsl

                visual_dsl = build_visual_dsl(blueprint, sampled_nouns, logic_steps_by_slot)

                # Atom 型情報を MR に格納（LLM が用語と寸法を間違えないように）
                sampled_nouns_info: Dict[str, Dict[str, Any]] = {}
                for slot_name, atom in sampled_nouns.items():
                    info: Dict[str, Any] = {"atom_type": type(atom).__name__}
                    # 形状種別フラグ（hide_height を含める: LLM が問題文で高さを出さないよう指示）
                    for attr in (
                        "polygon_type", "base_shape", "base_shape_type",
                        "is_cube", "is_sector", "is_regular_pyramid",
                        "hide_height",
                    ):
                        if hasattr(atom, attr):
                            val = getattr(atom, attr)
                            # hide_height は False でも明示的に含める（LLM が確認できるように）
                            if attr == "hide_height":
                                info[attr] = str(val)
                            elif val is not None and val != "" and val is not False:
                                info[attr] = str(val)
                    # 寸法（数値）
                    dims: Dict[str, str] = {}
                    for attr in ("width", "depth", "height", "base_side", "radius", "central_angle", "slope", "intercept", "coefficient_a"):
                        if hasattr(atom, attr):
                            val = getattr(atom, attr)
                            if val is not None:
                                dims[attr] = str(val)
                    if dims:
                        info["dimensions_cm"] = dims  # PrismAtom/PyramidAtom/SphereAtom 等は cm 想定
                    sampled_nouns_info[slot_name] = info

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
                    sampled_nouns_info=sampled_nouns_info,
                )

                if not mapping.get("dedup_disabled", False) and self.dedup.is_duplicate(mr):
                    continue

                # word_problem 形式の場合は問題形式に応じて動的に StoryContext を注入
                # Blueprint.story_required は目安。request.problem_form が word_problem なら強制注入
                story = None
                needs_story = (
                    blueprint.story_required
                    or request.problem_form == "word_problem"
                )
                if needs_story and self.scenarios is not None:
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
                    lesson_title=str(mapping.get("title", "")),
                    target_difficulty=int(request.target_difficulty),
                )

                self.dedup.register(mr, problem_text)

                # SVG をレンダリングしてキャッシュに保存、URL を返す
                diagram_url = self._render_visual(blueprint, mr)

                return GeneratedProblem(
                    middle_representation=mr,
                    problem_text=problem_text,
                    sub_question_texts=sub_texts,
                    explanation_text=explanation,
                    diagram_url=diagram_url,
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

    def _render_visual(self, blueprint, mr) -> Optional[str]:
        """visual_dsl があれば対応する Renderer で SVG を生成し、
        master_data/cache/diagrams/{seed}.svg に保存して /diagrams/{seed}.svg を返す
        """
        if mr.visual_dsl is None:
            return None
        if blueprint.visual_slot is None or blueprint.visual_slot.component_type == "NullRenderer":
            return None

        try:
            component = blueprint.visual_slot.component_type
            if component == "3D_Renderer":
                from apps.api.src.visuals.three_d_renderer import ThreeDRenderer
                renderer = ThreeDRenderer()
            elif component == "2D_Geometry_Renderer":
                from apps.api.src.visuals.two_d_geometry_renderer import TwoDGeometryRenderer
                renderer = TwoDGeometryRenderer()
            elif component == "Graph_Renderer":
                from apps.api.src.visuals.graph_renderer import GraphRenderer
                renderer = GraphRenderer()
            elif component == "Tree_Renderer":
                from apps.api.src.visuals.tree_renderer import TreeRenderer
                renderer = TreeRenderer()
            elif component in {"Table_&_Chart_Renderer", "TableChart_Renderer"}:
                from apps.api.src.visuals.table_chart_renderer import TableChartRenderer
                renderer = TableChartRenderer()
            else:
                return None

            svg = renderer.render(mr.visual_dsl)
            if not svg or "<svg" not in svg:
                return None

            from pathlib import Path
            cache_dir = Path("master_data/cache/diagrams")
            cache_dir.mkdir(parents=True, exist_ok=True)
            svg_path = cache_dir / f"{mr.seed}.svg"
            svg_path.write_text(svg, encoding="utf-8")
            return f"/diagrams/{mr.seed}.svg"
        except Exception:
            return None
