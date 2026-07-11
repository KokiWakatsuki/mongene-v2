"""コアパイプライン（実装設計 §5・§5.1・§5.2・§5.3）— resolve / generate / capabilities。

`engine.core` は `engine.packs` / `engine.curriculum` を import しない。curriculum は
`load_curriculum()` がファイル読みするだけ、families は呼び出し側（CLI・テスト）が
`load_family_dir` で読んで注入する。frame は `registry.frame(form)` 経由で取得する
（FrameProtocol 経由なので pack 実体を import しない）。
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Protocol

from engine.core.contracts import (
    CellContext,
    Coordinate,
    GenerateRequest,
    GenerateResult,
    Meta,
    Problem,
    SubQuestionOut,
    Unsupported,
)
from engine.core.curriculum import CurriculumModel, load_curriculum
from engine.core.registry import REGISTRY, _Registry
from engine.core.render.t1_template import TextResult, render_text, render_visual
from engine.core.rng import Rng, derive_rng, issue_seed
from engine.core.signature import fingerprint_hash
from engine.core.spec.loader import load_family_dir
from engine.core.verify.gates import GateFailure, run_gates

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, SpecFamily

_DEFAULT_FAMILIES_DIR = "engine/curriculum/math/families"

# 有界リトライの上限（§5.3）。recipe が `_bounded_retry` 属性を宣言した場合のみ使う。
_MAX_BOUNDED_RETRY = 3


def _default_families() -> dict[str, "SpecFamily"]:
    """既定の FamilySpec ディレクトリを読む。無ければ空 dict（M0 は縦串のみ制作予定）。"""
    from pathlib import Path

    d = Path(_DEFAULT_FAMILIES_DIR)
    if not d.exists():
        return {}
    return load_family_dir(d)


# ---------------------------------------------------------------------------
# resolve（§5・§5.2）
# ---------------------------------------------------------------------------
def resolve(
    req: GenerateRequest,
    *,
    curriculum: CurriculumModel | None = None,
    families: dict[str, "SpecFamily"] | None = None,
    registry: _Registry = REGISTRY,
) -> CellContext | Unsupported:
    """GenerateRequest → CellContext（成功）または Unsupported（拒否）。

    判定順（F-5 明示拒否）:
      unit 不在 → unit_not_found
      form 不在 → form_not_supported
      level 不在 → level_not_supported
      FamilySpec が families に無い/そのレベルが無い → not_implemented
      frame 未登録 → form_not_supported

    purpose == "remedial" は §5.2 の別経路（cause_id → 戻り先座標で再解決）。
    """
    curriculum = curriculum if curriculum is not None else load_curriculum()
    families = families if families is not None else _default_families()

    if req.purpose == "remedial":
        return _resolve_remedial(req, curriculum=curriculum, families=families, registry=registry)

    return _resolve_coordinate(
        subject=req.subject,
        unit=req.unit,
        form=req.form,
        level=req.level,
        purpose=req.purpose,
        requested=Coordinate(subject=req.subject, unit=req.unit, form=req.form, level=req.level),
        options=req.options,
        curriculum=curriculum,
        families=families,
        registry=registry,
    )


def _resolve_coordinate(
    *,
    subject: str,
    unit: str,
    form: str,
    level: int,
    purpose: str,
    requested: Coordinate,
    options: Any,
    curriculum: CurriculumModel,
    families: dict[str, "SpecFamily"],
    registry: _Registry,
) -> CellContext | Unsupported:
    """1つの座標(unit/form/level)を実際に解決する共通ロジック。"""
    if not curriculum.has_unit(unit):
        return Unsupported(code="unit_not_found", detail=f"unit={unit!r}")
    if not curriculum.has_form(unit, form):
        return Unsupported(code="form_not_supported", detail=f"unit={unit!r} form={form!r}")
    if not curriculum.has_level(unit, form, level):
        return Unsupported(
            code="level_not_supported", detail=f"unit={unit!r} form={form!r} level={level}"
        )

    family_name = f"math.{unit}.{form}"
    spec_family = families.get(family_name)
    if spec_family is None:
        return Unsupported(code="not_implemented", detail=f"FamilySpec 未制作: {family_name!r}")
    spec_level = spec_family.levels.get(str(level))
    if spec_level is None:
        return Unsupported(
            code="not_implemented", detail=f"FamilySpec に level={level} が無い: {family_name!r}"
        )

    if not registry.has_frame(form):
        return Unsupported(code="form_not_supported", detail=f"frame 未登録: form={form!r}")
    frame = registry.frame(form)

    return CellContext(
        subject=subject,
        family=family_name,
        form=form,
        unit=unit,
        level=level,
        purpose=purpose,  # type: ignore[arg-type]
        frame=frame,
        spec_family=spec_family,
        spec_level=spec_level,
        curriculum_view=curriculum.curriculum_view(unit),
        requested=requested,
        options=options,
    )


def _resolve_remedial(
    req: GenerateRequest,
    *,
    curriculum: CurriculumModel,
    families: dict[str, "SpecFamily"],
    registry: _Registry,
) -> CellContext | Unsupported:
    """remedial の解決（§5.2）: cause_id → curriculum の remediation 座標 → 再解決。

    requested は元リクエスト座標のまま。resolved（= CellContext の unit/form/level）は
    戻り先座標。remediation.level 省略時は FamilySpec.remedial_default_level を使う。
    """
    cause_id = req.options.cause_id
    if not cause_id:
        return Unsupported(code="cause_not_found", detail="purpose=remedial に options.cause_id が無い")

    cause = curriculum.get_cause(cause_id)
    if cause is None:
        return Unsupported(code="cause_not_found", detail=f"cause_id={cause_id!r} が curriculum に無い")

    rem = cause.remediation
    requested = Coordinate(subject=req.subject, unit=req.unit, form=req.form, level=req.level)

    rem_level = rem.level
    if rem_level is None:
        family_name = f"math.{rem.unit}.{rem.form}"
        spec_family = families.get(family_name)
        if spec_family is None or spec_family.remedial_default_level is None:
            return Unsupported(
                code="not_implemented",
                detail=f"remediation level 省略時の既定値が無い: {family_name!r}",
            )
        rem_level = spec_family.remedial_default_level

    result = _resolve_coordinate(
        subject=req.subject,
        unit=rem.unit,
        form=rem.form,
        level=rem_level,
        purpose=req.purpose,
        requested=requested,
        options=req.options,
        curriculum=curriculum,
        families=families,
        registry=registry,
    )
    if isinstance(result, Unsupported):
        # 戻り先座標が capabilities 外（未制作 or タクソノミー不在）→ not_implemented に統一
        if result.code in ("unit_not_found", "form_not_supported", "level_not_supported"):
            return Unsupported(
                code="not_implemented",
                detail=f"remediation 戻り先が未実装: {rem.unit}/{rem.form}/Lv{rem_level}（{result.detail}）",
            )
        return result
    return result


# ---------------------------------------------------------------------------
# Supplier 抽象（§5.1）
# ---------------------------------------------------------------------------
class Supplier(Protocol):
    """問題供給源の抽象。generate() の手順3-9 はこの実装の1つ（GeneratorSupplier）を呼ぶ。

    将来の拡張点: M1 でプール（事前生成した検証済み Problem の即時取り出し）を
    別実装として差し込む。M0 では生成器のみ実装するが、pipeline はこの一段を
    最初から持つ（M1 での骨格改修を防ぐ）。
    """

    def supply(self, ctx: CellContext, seed: int, *, registry: _Registry = REGISTRY) -> Problem:
        ...


class GeneratorSupplier:
    """生成器（M0 唯一の Supplier 実装）。手順3-9（recipe→gates→text→gates→visual→gates→assemble）。"""

    def supply(self, ctx: CellContext, seed: int, *, registry: _Registry = REGISTRY) -> Problem:
        rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
        mr = _construct_with_bounded_retry(ctx, rng, registry=registry)
        # recipe は (ctx, rng) のみを受け取り外側の seed 値を知らないため、pipeline が
        # 採番した seed を MR に刻印する（MR.seed = 再現の正。H8）。
        mr = mr.model_copy(update={"seed": seed})

        run_gates(mr, ctx, "mr", registry=registry)

        text = render_text(mr, ctx, registry=registry)
        run_gates(text, ctx, "text", registry=registry)

        svg = render_visual(mr, ctx, registry=registry)
        run_gates(svg, ctx, "visual", registry=registry)

        return assemble_problem(mr, text, svg, ctx)


def _construct_with_bounded_retry(ctx: CellContext, rng: Rng, *, registry: _Registry) -> "MR":
    """recipe を呼ぶ。`@bounded_retry` 相当（recipe 関数の `_bounded_retry` 属性）が
    宣言されている場合のみ最大3回まで rng.spawn で再試行する。宣言が無ければリトライ無し。
    """
    recipe_fn = registry.recipe(ctx.spec_level.recipe)
    max_attempts = getattr(recipe_fn, "_bounded_retry", 1)
    max_attempts = min(max_attempts, _MAX_BOUNDED_RETRY) if max_attempts else 1

    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        attempt_rng = rng.spawn(attempt) if attempt > 0 else rng
        try:
            return recipe_fn(ctx, attempt_rng)
        except Exception as e:  # noqa: BLE001 - 有界リトライの対象例外は recipe 側の構成失敗
            last_exc = e
            continue
    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# generate（§5）
# ---------------------------------------------------------------------------
def generate(
    req: GenerateRequest,
    *,
    curriculum: CurriculumModel | None = None,
    families: dict[str, "SpecFamily"] | None = None,
    registry: _Registry = REGISTRY,
    supplier: Supplier | None = None,
) -> GenerateResult:
    """要求 → Problem（成功）または Unsupported（拒否・ゲート全滅）。"""
    curriculum = curriculum if curriculum is not None else load_curriculum()
    families = families if families is not None else _default_families()
    supplier = supplier if supplier is not None else GeneratorSupplier()

    ctx = resolve(req, curriculum=curriculum, families=families, registry=registry)
    if isinstance(ctx, Unsupported):
        return ctx

    seed = req.seed if req.seed is not None else issue_seed()

    try:
        return supplier.supply(ctx, seed, registry=registry)
    except GateFailure as e:
        return Unsupported(code="verification_exhausted", detail=f"{e.gate_name}: {e.detail}")


# ---------------------------------------------------------------------------
# assemble_problem（手順9）
# ---------------------------------------------------------------------------
def assemble_problem(mr: "MR", text: TextResult, svg: str | None, ctx: CellContext) -> Problem:
    """MR + TextResult + svg + ctx → Problem（§4.2 のフィールド名に一致）。"""
    sub_questions: list[SubQuestionOut] = []
    all_concepts: list[str] = []
    all_causes: list[str] = []
    for sq in mr.sub_questions:
        sub_questions.append(
            SubQuestionOut(
                label=sq.label,
                prompt_text=text.prompts.get(sq.label, ""),
                answer=sq.answer,
                solution_steps=sq.steps,
                explanation=text.explanations.get(sq.label, ""),
                hints=text.hints.get(sq.label, []),
                concept_tags=sq.concept_tags,
                cause_tags=sq.cause_tags,
            )
        )
        for c in sq.concept_tags:
            if c not in all_concepts:
                all_concepts.append(c)
        for c in sq.cause_tags:
            if c not in all_causes:
                all_causes.append(c)

    resolved_coord = Coordinate(subject=ctx.subject, unit=ctx.unit, form=ctx.form, level=ctx.level)

    meta = Meta(
        requested=ctx.requested,
        resolved=resolved_coord,
        purpose=ctx.purpose,
        seed=mr.seed,
        signature=mr.signature,
        concept_tags=all_concepts,
        cause_tags=all_causes,
        provenance=mr.provenance,
        render_keys=text.render_keys,
    )

    problem_ref = _compute_problem_ref(mr, text)

    return Problem(
        problem_ref=problem_ref,
        problem_text=text.problem_text,
        visual_svg=svg,
        sub_questions=sub_questions,
        meta=meta,
    )


def _compute_problem_ref(mr: "MR", text: TextResult) -> str:
    """problem_ref = sha256(provenance_json + seed + render_keys) の16進16桁程度。"""
    payload = {
        "provenance": mr.provenance.model_dump(),
        "seed": mr.seed,
        "render_keys": text.render_keys,
        "signature": mr.signature,
        "fp": fingerprint_hash(mr),
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# capabilities（§5）
# ---------------------------------------------------------------------------
def capabilities(
    *,
    curriculum: CurriculumModel | None = None,
    families: dict[str, "SpecFamily"] | None = None,
    registry: _Registry = REGISTRY,
) -> list[Coordinate]:
    """families の各 FamilySpec × levels のうち `lint_family` が clean なセルを列挙する。

    `not_implemented` はここに出ない（families に無いセルは列挙対象外そのもの）。
    """
    from engine.core.spec.lint import lint_family

    curriculum = curriculum if curriculum is not None else load_curriculum()
    families = families if families is not None else _default_families()

    frames = {form: registry.frame(form) for form in _known_forms(registry)}
    concepts = curriculum.concept_ids()
    causes = curriculum.cause_ids()

    result: list[Coordinate] = []
    for family_name, spec_family in families.items():
        errors = lint_family(
            spec_family, registry=registry, concepts=concepts, causes=causes, frames=frames
        )
        if errors:
            continue
        # family_name は "math.<unit>.<form>" 形式（resolve と対称）。
        parts = family_name.split(".", 2)
        if len(parts) != 3:
            continue
        _subject_tag, unit, form = parts
        for level_key, spec_level in spec_family.levels.items():
            if not curriculum.has_level(unit, form, spec_level.level):
                continue
            result.append(Coordinate(subject="math", unit=unit, form=form, level=spec_level.level))
    return result


def _known_forms(registry: _Registry) -> list[str]:
    """registry に登録済みの frame の form 名一覧（capabilities の frame 注入用）。"""
    # _Registry は _frames の公開アクセサを持たないため、frame() の KeyError を避けるべく
    # 既知の7 form を試す（未登録なら単に含まれない）。
    candidates = [
        "calculation", "knowledge", "find_value", "graph_table",
        "word_problem", "proof", "construction",
    ]
    return [f for f in candidates if registry.has_frame(f)]


__all__ = [
    "resolve",
    "generate",
    "capabilities",
    "assemble_problem",
    "Supplier",
    "GeneratorSupplier",
]
