"""問題生成エンドポイント（§31, §35.2）"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException

from apps.api.src.core.cache.prefetch import PrefetchCache

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
    simultaneous_eq_verb,
    slice_solid_verb,
    solve_eq_verb,
    knowledge_check_verb,
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


def _git_commit_short() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


_GIT_COMMIT = _git_commit_short()

router = APIRouter(prefix="/problems", tags=["problems"])

_mapping_cache: Dict[str, Any] | None = None
_runner: BlueprintRunner | None = None
_prefetch = PrefetchCache(max_size=5)


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


def _build_response(result, request: ProblemGenerationRequest, lesson_mapping: Dict[str, Any]) -> ProblemGenerationResponse:
    """GeneratedProblem → ProblemGenerationResponse 変換"""
    mr = result.middle_representation
    sub_texts_by_label: Dict[str, str] = {
        sq.get("label", ""): sq.get("text", "") for sq in (result.sub_question_texts or [])
    }
    # explanation_text は dict {"_all": ..., "(1)": ..., "(2)": ...} 形式
    exp_raw = result.explanation_text
    exp_map: Dict[str, str] = exp_raw if isinstance(exp_raw, dict) else {"_all": exp_raw or ""}
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
                # サブ問題ラベルに対応する解説。無ければ (1) にだけ全体解説を入れる
                explanation_text=exp_map.get(sq.label) or (exp_map.get("_all") if i == 0 else None),
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
            git_commit=_GIT_COMMIT,
        ),
    )


@router.post("/generate", response_model=ProblemGenerationResponse)
def generate_problem(
    request: ProblemGenerationRequest,
    background_tasks: BackgroundTasks,
) -> ProblemGenerationResponse:
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
        target_level=request.target_level,
        problem_form=request.problem_form,
        lesson_id=lesson_id,
        unlearned_lesson_ids=request.unlearned_lesson_ids,
        seed=request.seed,
    )

    # 1. PrefetchCache から取り出し（あれば即返却 + バックグラウンドで補充）
    cached = _prefetch.pop_for(request, lesson_id)
    if cached is not None:
        background_tasks.add_task(
            _refill_async, request, lesson_id, gen_request, lesson_mapping, 1
        )
        return _build_response(cached, request, lesson_mapping)

    # 2. キャッシュミス → 同期生成
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

    # 3. 同時にバックグラウンドで 2 問先読み
    background_tasks.add_task(
        _refill_async, request, lesson_id, gen_request, lesson_mapping, 2
    )

    return _build_response(result, request, lesson_mapping)


async def _refill_async(
    request: ProblemGenerationRequest,
    lesson_id: str,
    gen_request: GenerationRequest,
    lesson_mapping: Dict[str, Any],
    count: int,
) -> None:
    """PrefetchCache の補充。例外は内部で握りつぶす（先読み失敗で API は止めない）"""
    runner = _get_runner()
    await _prefetch.refill(
        request,
        lesson_id,
        runner_run=lambda: runner.run(gen_request, lesson_mapping),
        count=count,
    )


@router.get("/mapping/{lesson_id}")
def get_mapping(lesson_id: str) -> Dict[str, Any]:
    mapping = _load_mapping()
    if lesson_id not in mapping:
        raise HTTPException(status_code=404, detail=f"未登録: {lesson_id}")
    return mapping[lesson_id]


@router.post("/inspect")
def inspect_middle_representation(request: ProblemGenerationRequest) -> Dict[str, Any]:
    """LLM 翻訳を一切行わず、SymPy 計算結果の中間表現をそのまま返す。

    システム側の計算（Blueprint/Atom/Verb）が正しいかを確認するために使う。
    LLM を呼ばないため即座に返却される。
    """
    mapping = _load_mapping()
    if not request.curriculum.lesson_ids:
        raise HTTPException(status_code=400, detail="lesson_ids が空です")

    lesson_id = request.curriculum.lesson_ids[0]
    if lesson_id not in mapping:
        raise HTTPException(status_code=404, detail=f"未登録: {lesson_id}")
    lesson_mapping = mapping[lesson_id]

    if request.problem_form not in lesson_mapping.get("supported_forms", []):
        raise HTTPException(
            status_code=400,
            detail=f"{lesson_id} は {request.problem_form} をサポートしていません",
        )

    # BlueprintRunner を LLM なしモードで実行
    from apps.api.src.blueprints.registry import load_blueprint as _load_bp
    from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
    from apps.api.src.core.dedup.hash_cache import DuplicationGuard
    from apps.api.src.core.llm.translator import LLMTranslator
    from apps.api.src.core.runner.atom_selector import AtomSelector
    from apps.api.src.core.runner.blueprint_runner import BlueprintRunner, GenerationRequest
    import os, tempfile

    tmp_db = tempfile.mktemp(suffix=".db")
    os.environ["SKIP_LLM_IN_TESTS"] = "true"  # この呼び出しの間だけ
    try:
        runner = BlueprintRunner(
            dedup=DuplicationGuard(db_path=tmp_db),
            diversity=DiversityRotation(),
            translator=LLMTranslator(),
            atom_selector=AtomSelector(),
            blueprint_loader=_load_bp,
            max_retries=20,
        )
        gen_request = GenerationRequest(
            target_difficulty=request.target_difficulty,
            target_level=request.target_level,
            problem_form=request.problem_form,
            lesson_id=lesson_id,
            seed=request.seed,
        )
        result = runner.run(gen_request, lesson_mapping)
    finally:
        os.environ.pop("SKIP_LLM_IN_TESTS", None)
        try:
            import pathlib; pathlib.Path(tmp_db).unlink(missing_ok=True)
        except Exception:
            pass

    mr = result.middle_representation

    # 中間表現をそのまま JSON 化
    return {
        "lesson_id": lesson_id,
        "lesson_title": lesson_mapping.get("title"),
        "blueprint_id": mr.blueprint_id,
        "problem_form": mr.problem_form,
        "difficulty_score": mr.difficulty_score,
        "selected_tags": mr.selected_tags,
        "seed": mr.seed,
        "sampled_atoms": mr.sampled_nouns_info,
        "sub_questions": [
            {
                "label": sq.label,
                "prompt_hint": sq.prompt_hint,
                "answer": {
                    "type": sq.answer.type,
                    "sympy_form": str(sq.answer.sympy_form),
                    "text_form": sq.answer.text_form,
                },
                "logic_steps": [
                    {
                        "operation_name": s.operation_name,
                        "operands": s.operands[:3],
                        "sympy_expr": str(s.sympy_expr),
                        "narration_hint": s.narration_hint,
                    }
                    for s in sq.logic_steps
                ],
            }
            for sq in mr.sub_questions
        ],
        "note": "この結果は LLM 翻訳前の生データです。sympy_form が正しければシステム側は OK、問題文がおかしければ LLM 側の問題です。",
    }


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
                "domain": m.get("domain", ""),
                "large_unit": m.get("large_unit", ""),
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


@router.get("/difficulty-range/{lesson_id}")
def get_difficulty_range(lesson_id: str, form: str = "calculation") -> Dict[str, Any]:
    """新 Raw Score モデルに基づく lesson × form の難易度レンジを返す"""
    mapping = _load_mapping()
    if lesson_id not in mapping:
        raise HTTPException(status_code=404, detail=f"未登録: {lesson_id}")
    m = mapping[lesson_id]
    from apps.api.src.core.runner.difficulty_reconciler import get_form_range_from_y_base
    lo, hi = get_form_range_from_y_base(m["y_base"], form)
    return {
        "lesson_id": lesson_id,
        "form": form,
        "y_base": m["y_base"],
        "raw_y_base": m.get("raw_y_base", m["y_base"]),
        "min_difficulty": lo,
        "max_difficulty": hi,
        "default_difficulty": m["y_base"],
    }
