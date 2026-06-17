"""問題生成エンドポイント（§31, §35.2）"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from apps.api.src.atoms.noun import (  # noqa: F401 - Atom 登録のため
    circle_angle_atom,
    circle_atom,
    data_set_atom,
    equation_atom,
    event_atom,
    inverse_func_atom,
    line_angle_atom,
    linear_func_atom,
    moving_point_atom,
    number_atom,
    point_atom,
    polygon_atom,
    polynomial_atom,
    prism_atom,
    proportion_atom,
    pyramid_atom,
    quadratic_func_atom,
    sample_atom,
    sequence_atom,
    sphere_atom,
    square_root_atom,
)
from apps.api.src.atoms.verb import (  # noqa: F401 - Verb 登録のため
    analyze_data_verb,
    calculate_arithmetic_verb,
    calculate_probability_verb,
    construct_geometry_verb,
    cutout_verb,
    estimate_population_verb,
    find_angle_verb,
    find_divisors_verb,
    form_shape_verb,
    generalize_formula_verb,
    intersect_verb,
    locus_verb,
    measure_geometry_verb,
    prove_algebraic_verb,
    prove_geometry_verb,
    slice_solid_verb,
    solve_eq_verb,
    solve_linear_diophantine_verb,
    transform_shape_verb,
    unfold_net_verb,
)
from apps.api.src.blueprints.registry import load_blueprint
from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
from apps.api.src.core.dedup.hash_cache import DuplicationGuard
from apps.api.src.core.exceptions import (
    LLMRateLimitError,
    MongeneError,
    NoCompatibleBlueprintError,
    UnsupportedFormError,
)
from apps.api.src.core.llm.translator import LLMTranslator
from apps.api.src.core.scenarios.bank import ScenarioBank
from apps.api.src.core.runner.atom_selector import AtomSelector
from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest
from apps.api.src.domains.problems.schemas import (
    AnswerSchema,
    MetadataSchema,
    ProblemGenerationRequest,
    ProblemGenerationResponse,
    SubQuestionSchema,
    VisualsSchema,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
MAPPING_PATH = REPO_ROOT / "master_data" / "mapping.json"
DEDUP_DB_PATH = REPO_ROOT / "master_data" / "cache" / "api_dedup.db"

router = APIRouter(prefix="/problems", tags=["problems"])

_mapping_cache: Dict[str, Any] | None = None
_runner: BlueprintRunner | None = None


def _load_mapping() -> Dict[str, Any]:
    global _mapping_cache
    if _mapping_cache is None:
        _mapping_cache = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    return _mapping_cache


def _get_runner() -> BlueprintRunner:
    global _runner
    if _runner is None:
        DEDUP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            scenarios = ScenarioBank.load()
        except FileNotFoundError:
            scenarios = None
        _runner = BlueprintRunner(
            dedup=DuplicationGuard(db_path=str(DEDUP_DB_PATH)),
            diversity=DiversityRotation(),
            translator=LLMTranslator(),
            atom_selector=AtomSelector(),
            blueprint_loader=load_blueprint,
            scenario_bank=scenarios,
            max_retries=50,
        )
    return _runner


@router.post("/generate", response_model=ProblemGenerationResponse)
def generate_problem(request: ProblemGenerationRequest) -> ProblemGenerationResponse:
    mapping = _load_mapping()
    if not request.curriculum.lesson_ids:
        raise HTTPException(status_code=400, detail="curriculum.lesson_ids が空です")

    lesson_id = request.curriculum.lesson_ids[0]
    if lesson_id not in mapping:
        raise HTTPException(status_code=404, detail=f"未登録の lesson_id: {lesson_id}")
    lesson_mapping = mapping[lesson_id]

    if request.problem_form not in lesson_mapping.get("supported_forms", []):
        raise HTTPException(
            status_code=400,
            detail=f"{lesson_id} は {request.problem_form} をサポートしていません",
        )

    runner = _get_runner()
    gen_request = GenerationRequest(
        target_difficulty=request.target_difficulty,
        problem_form=request.problem_form,
        lesson_id=lesson_id,
        unlearned_lesson_ids=request.unlearned_lesson_ids,
    )
    try:
        result = runner.run(gen_request, lesson_mapping)
    except UnsupportedFormError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NoCompatibleBlueprintError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except LLMRateLimitError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except MongeneError as e:
        raise HTTPException(status_code=500, detail=str(e))

    mr = result.middle_representation
    sub_texts_by_label: Dict[str, str] = {
        sq.get("label", ""): sq.get("text", "") for sq in (result.sub_question_texts or [])
    }

    return ProblemGenerationResponse(
        content_problem_text=result.problem_text,
        sub_questions=[
            SubQuestionSchema(
                label=sq.label,
                prompt_text=sub_texts_by_label.get(sq.label, sq.prompt_hint),
                answer=AnswerSchema(
                    type=sq.answer.type,
                    sympy_form=str(sq.answer.sympy_form) if sq.answer.sympy_form is not None else None,
                    text_form=sq.answer.text_form,
                    extras=sq.answer.extras,
                ),
                explanation_text=result.explanation_text if i == 0 else None,
            )
            for i, sq in enumerate(mr.sub_questions)
        ],
        visuals=VisualsSchema(
            problem_diagram_url=result.diagram_url,
            explanation_diagram_url=None,
        ),
        metadata=MetadataSchema(
            base_difficulty=int(lesson_mapping.get("y_base", 50)),
            adjustment_delta=int(mr.difficulty_score - lesson_mapping.get("y_base", 50)),
            used_atoms=sorted(
                {a for a in mr.selected_tags if a not in lesson_mapping.get("required_tags", [])}
            ),
            seed=mr.seed,
            blueprint_id=mr.blueprint_id,
            blueprint_version=mr.blueprint_version,
        ),
    )


@router.get("/mapping/{lesson_id}")
def get_mapping(lesson_id: str) -> Dict[str, Any]:
    mapping = _load_mapping()
    if lesson_id not in mapping:
        raise HTTPException(status_code=404, detail=f"未登録: {lesson_id}")
    return mapping[lesson_id]


@router.get("/lessons")
def list_lessons() -> Dict[str, Any]:
    mapping = _load_mapping()
    return {
        "total": len(mapping),
        "lessons": [
            {
                "lesson_id": lid,
                "grade": m["grade"],
                "lesson_number": m["lesson_number"],
                "title": m["title"],
                "blueprint": m["execute_blueprint"],
                "supported_forms": m["supported_forms"],
                "y_base": m["y_base"],
            }
            for lid, m in sorted(
                mapping.items(),
                key=lambda kv: (kv[1]["grade"], kv[1]["lesson_number"]),
            )
        ],
    }
