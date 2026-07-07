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


# DSL が宣言した render_type を正としてレンダラを選ぶ。既存の全 DSL は
# render_type ↔ component_type が一致するので挙動不変。展開図(net)だけ
# component_type=3D_Renderer のまま render_type=2D_Geometry に流れる。
_RENDER_TYPE_TO_COMPONENT = {
    "3D": "3D_Renderer",
    "2D_Geometry": "2D_Geometry_Renderer",
    "Graph": "Graph_Renderer",
    "Tree": "Tree_Renderer",
    "Table": "Table_&_Chart_Renderer",
}


class _FallbackAtomNeeded(Exception):
    def __init__(self, slot: str) -> None:
        self.slot = slot


@dataclass
class GenerationRequest:
    """BlueprintRunner.run の入力（API 層から渡される簡易版）"""

    problem_form: str
    lesson_id: str
    target_difficulty: Optional[int] = None  # 旧設計フォールバック用
    target_level: Optional[int] = None       # 新設計（離散レベル制）
    unlearned_lesson_ids: List[str] = field(default_factory=list)
    seed: Optional[int] = None  # 外部から注入する再現用シード（None なら従来の非決定挙動）


def get_level_config(lesson_mapping: Dict[str, Any], form: str, level: int) -> Dict[str, Any]:
    """mapping.json から指定フォーム・レベルの設定を返す。"""
    levels = lesson_mapping.get("difficulty_levels", {}).get(form, [])
    for lv_def in levels:
        if lv_def["lv"] == level:
            return lv_def
    from apps.api.src.core.exceptions import NoCompatibleBlueprintError
    raise NoCompatibleBlueprintError(f"{form} Lv{level} は定義されていません")


def _merge_constraints(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """ベース atom_constraints にパッチを差分マージする（シャローマージ）。

    patch の値が dict でない場合（LLM 生成のフラット形式: {パラメータ名: 値}）は
    既存の全 Atom クラスに対してそのパラメータを設定する。
    """
    merged = {k: dict(v) for k, v in base.items()}
    for atom_class, params in patch.items():
        if not isinstance(params, dict):
            # フラット形式: atom_class がパラメータ名で params がその値
            for ac_dict in merged.values():
                ac_dict[atom_class] = params
            continue
        if atom_class in merged:
            merged[atom_class].update(params)
        else:
            merged[atom_class] = dict(params)
    return merged


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
        # seed 決定（冒頭で確定させ、以降の乱択・リトライループ全体で使う）
        # request.seed が指定されていれば再現的、None なら従来通り毎回変わる非決定挙動を維持する。
        import time as _time
        if request.seed is not None:
            base_seed = request.seed
        else:
            base_seed = (random.randint(1, 1_000_000) ^ (int(_time.time_ns()) & 0xFFFFF)) % 1_000_000 + 1

        # フォーム別Blueprint優先: execute_blueprint_by_form があればそちらを使う
        bp_by_form = mapping.get("execute_blueprint_by_form", {})
        if request.problem_form in bp_by_form:
            candidate_ids = [bp_by_form[request.problem_form]]
        else:
            # execute_blueprints（リスト）があればその全要素が候補、なければ execute_blueprint 単体が候補
            blueprints_list = mapping.get("execute_blueprints")
            if blueprints_list and isinstance(blueprints_list, list) and len(blueprints_list) > 1:
                candidate_ids = list(blueprints_list)
            else:
                candidate_ids = [
                    mapping.get("execute_blueprint", blueprints_list[0] if blueprints_list else "BasicCalculationStructure")
                ]
        blueprint_params = mapping.get("blueprint_params", {})
        # 問題文を form 別に出し分けたい blueprint（例: CoordinatePlaneStructure は calc で
        # 「グラフをかき」を出さない）のために現在の form を params に注入する。未知 params を
        # 無視する blueprint には無害。
        blueprint_params = {**blueprint_params, "_problem_form": request.problem_form}

        # 契約強制: mapping が要求する form を supported_forms に持たない blueprint に
        # 黙って退化させない。候補を form でフィルタし、空なら正直にエラーにする。
        candidate_blueprints = {
            cid: self.blueprint_loader(cid, params=blueprint_params) for cid in candidate_ids
        }
        filtered_ids = [
            cid for cid in candidate_ids
            if request.problem_form in candidate_blueprints[cid].supported_forms
        ]
        if not filtered_ids:
            raise NoCompatibleBlueprintError(
                f"lesson={request.lesson_id} は form={request.problem_form} を要求するが、"
                f"候補blueprint {candidate_ids} はいずれも supported_forms に "
                f"{request.problem_form} を含まない（静かなフォールバック禁止）"
            )
        bp_id = random.Random(base_seed).choice(filtered_ids)
        blueprint = candidate_blueprints[bp_id]

        # レベル固有 atom_constraints が明示指定した Atom 型（＝そのレベルの意図する型）。
        # トップレベルの atom_constraints が複数型のメニューを持つ場合でも、レベルの意図を優先して
        # Atom 型選択を絞るために使う（tag駆動でCircleAtom等が混入するのを防ぐ）。
        level_atom_type_keys: Optional[List[str]] = None

        # --- 難易度設定パス ---
        # 新設計（離散レベル制）: target_level 指定 + difficulty_levels 定義済みの場合
        has_level_path = (
            request.target_level is not None
            and "difficulty_levels" in mapping
            and request.problem_form in mapping["difficulty_levels"]
        )

        if has_level_path:
            lv_config = get_level_config(mapping, request.problem_form, request.target_level)  # type: ignore[arg-type]
            if not lv_config.get("implementable", True):
                note = lv_config.get("implementation_note", "")
                raise NoCompatibleBlueprintError(f"Lv{request.target_level} は未実装: {note}")
            # レベル固有の blueprint_params をベース設定にマージ
            level_bp_params = {**blueprint_params, **lv_config.get("blueprint_params", {})}
            if lv_config.get("blueprint_override"):
                blueprint = self.blueprint_loader(lv_config["blueprint_override"], params=level_bp_params)
            elif level_bp_params != blueprint_params:
                blueprint = self.blueprint_loader(bp_id, params=level_bp_params)
            base_constraints = {k: dict(v) for k, v in mapping.get("atom_constraints", {}).items()}
            level_constraints = lv_config.get("atom_constraints", {}) or {}
            atom_constraints = _merge_constraints(base_constraints, level_constraints)
            level_atom_type_keys = list(level_constraints.keys()) or None
            # UI 表示用スコア: y_base を基準に lv に応じてスケール
            n_levels = len(mapping["difficulty_levels"][request.problem_form])
            y_base = int(mapping.get("y_base", 50))
            computed_difficulty = float(y_base + (request.target_level / max(n_levels, 1)) * 30)  # type: ignore[operator]
        else:
            # 旧設計フォールバック（y_base + delta_factors）
            plan = reconcile_difficulty(
                target=request.target_difficulty or int(mapping.get("y_base", 50)),
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
            raw_delta = (request.target_difficulty or int(mapping.get("y_base", 50))) - int(mapping.get("y_base", 50))

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

            computed_difficulty = float(plan.computed_difficulty)

        # 契約強制（最終アサート）: レベル固有 blueprint_override や旧設計フォールバックの
        # plan.blueprint によって最終的な blueprint が差し替わった場合も、
        # request.problem_form を supported_forms が満たすかを再検証する。
        if request.problem_form not in blueprint.supported_forms:
            raise NoCompatibleBlueprintError(
                f"lesson={request.lesson_id} は form={request.problem_form} を要求するが、"
                f"最終選択された blueprint {blueprint.blueprint_id} は supported_forms に "
                f"{request.problem_form} を含まない（静かなフォールバック禁止）"
            )

        # unit_mix_bonus: 複合単元（+2/単元追加）→ 制約を多様化
        # 現状 Atom レベルでは直接対応困難。LLM プロンプトへの目安として計算のみ

        # base_seed は run() 冒頭で決定済み（request.seed 指定時は再現的、未指定時は時刻ベースで従来通り非決定）
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
                    required_tags=mapping.get("required_tags"),  # §38.2: mapping の tags で Atom 選択をガイド
                    preferred_noun_types=level_atom_type_keys,  # レベルが明示した Atom 型を優先
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
                    difficulty_score=computed_difficulty,
                    problem_form=request.problem_form,  # type: ignore[arg-type]
                    sub_questions=sub_questions,
                    visual_dsl=visual_dsl,
                    seed=seed,
                    blueprint_id=blueprint.blueprint_id,
                    blueprint_version=blueprint.blueprint_version,
                    sampled_nouns_info=sampled_nouns_info,
                    difficulty_level=request.target_level,
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
                    target_difficulty=int(computed_difficulty),
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
            component = _RENDER_TYPE_TO_COMPONENT.get(
                getattr(mr.visual_dsl, "render_type", None),
                blueprint.visual_slot.component_type,
            )
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
