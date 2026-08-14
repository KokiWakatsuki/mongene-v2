"""eval 共有ハーネス（実装設計 §8.3・Task10）。

eval プログラム群（coverage_scan / dup_rate / level_sep / retry_stats）が共有する
「セルの走査」「MR の構築」「remedial 対応の走査」ロジック。

`engine.eval` は core/packs/curriculum を **読むだけ**（生成と読み取りのみ・§5.5）。
core/pack は一切変更しない。MR を得る手順は `core.pipeline.GeneratorSupplier` の
recipe 構成部（`_construct_with_bounded_retry` + seed 刻印）を忠実に再現する
（Problem は params/MR を運ばないため、fp/dup_key の測定には MR 実体が要る）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from engine.bootstrap import bootstrap
from engine.core.contracts import (
    MR,
    CellContext,
    Coordinate,
    GenerateOptions,
    GenerateRequest,
    SpecFamily,
)
from engine.core.curriculum import CurriculumModel, load_curriculum
from engine.core.pipeline import _STATEMENT_SIZE_REDRAWS, capabilities, resolve
from engine.core.registry import REGISTRY, _Registry
from engine.core.rng import Rng, derive_rng
from engine.core.spec.loader import load_family_dir
from engine.core.verify.statement_size import limits_for as statement_limits_for
from engine.core.verify.statement_size import statement_is_too_big

_DEFAULT_FAMILIES_DIR = Path("engine/curriculum/math/families")

# 有界リトライ上限（pipeline._MAX_BOUNDED_RETRY と一致させる）。
_MAX_BOUNDED_RETRY = 3


@dataclass(frozen=True)
class EvalEnv:
    """eval が使う不変環境（bootstrap 済みの registry + curriculum + families）。"""

    curriculum: CurriculumModel
    families: dict[str, SpecFamily]
    registry: _Registry = REGISTRY


def make_env(
    *,
    families_dir: Path = _DEFAULT_FAMILIES_DIR,
    registry: _Registry = REGISTRY,
) -> EvalEnv:
    """pack 登録 + Q ゲート install（bootstrap）を済ませ、curriculum/families を読む。"""
    bootstrap(registry)
    return EvalEnv(
        curriculum=load_curriculum(),
        families=load_family_dir(families_dir),
        registry=registry,
    )


# ---------------------------------------------------------------------------
# セル走査（capabilities 準拠）
# ---------------------------------------------------------------------------
def capability_cells(env: EvalEnv) -> list[Coordinate]:
    """spec が実在し lint clean な base セル一覧（capabilities）。"""
    cells = capabilities(
        curriculum=env.curriculum, families=env.families, registry=env.registry
    )
    return sorted(cells, key=lambda c: (c.unit, c.form, c.level))


def family_of(coord: Coordinate) -> str:
    return f"{coord.subject}.{coord.unit}.{coord.form}"


def cell_request(coord: Coordinate, seed: int) -> GenerateRequest:
    """base セル座標 × seed の GenerateRequest を組む。"""
    return GenerateRequest(
        subject=coord.subject, unit=coord.unit, form=coord.form, level=coord.level, seed=seed
    )


# ---------------------------------------------------------------------------
# MR の構築（core.pipeline の recipe 構成部を忠実に再現）
# ---------------------------------------------------------------------------
def _construct_with_bounded_retry(ctx: CellContext, rng: Rng, env: EvalEnv) -> tuple[MR, int]:
    """recipe を呼ぶ。`_bounded_retry` 属性がある recipe のみ最大3回まで rng.spawn で再試行。

    戻り値: (mr, attempts_used)。attempts_used は retry_stats 用（1=リトライ無しで成功）。

    **問題文の大きさによる組み直しは pipeline 側と同じ経路を通す。**
    ここに pipeline の写しを持っていたので、`statement_size` の組み直しを
    pipeline に足したとき、**ゲートが生徒に出るのと違う MR を測る**状態になっていた
    （dup_rate も level_sep も `build_mr` を使う）。写しを増やさず、
    構成の外枠は `engine.core.pipeline` の関数をそのまま呼ぶ。
    """
    recipe_fn = env.registry.recipe(ctx.spec_level.recipe)
    max_attempts = getattr(recipe_fn, "_bounded_retry", 1)
    max_attempts = min(max_attempts, _MAX_BOUNDED_RETRY) if max_attempts else 1

    attempts_used = 0

    def one_pass(pass_rng: Rng) -> MR:
        """recipe の有界リトライ1回ぶん（attempts を数えながら）。"""
        nonlocal attempts_used
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            attempt_rng = pass_rng.spawn(attempt) if attempt > 0 else pass_rng
            attempts_used = attempt + 1
            try:
                return recipe_fn(ctx, attempt_rng)
            except Exception as e:  # noqa: BLE001 - 構成失敗は retry_stats の測定対象
                last_exc = e
                continue
        assert last_exc is not None
        raise last_exc

    limits = statement_limits_for(ctx.spec_level)
    last: MR | None = None
    for redraw in range(_STATEMENT_SIZE_REDRAWS):
        pass_rng = rng.spawn(1000 + redraw) if redraw else rng
        last = one_pass(pass_rng)
        text = " ".join(str(v) for v in last.given.values())
        if not statement_is_too_big(text, limits):
            return last, attempts_used
    assert last is not None
    return last, attempts_used


@dataclass
class MRResult:
    """MR 構築の結果（成功/失敗と retry 回数を保持）。"""

    coord: Coordinate
    seed: int
    mr: MR | None
    attempts: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.mr is not None


def build_mr(coord: Coordinate, seed: int, env: EvalEnv) -> MRResult:
    """base セル × seed の MR を構築する（pipeline と同じ derive_rng + seed 刻印）。

    resolve が Unsupported を返す（未制作等）場合や recipe 構成が有界内に失敗した
    場合は `MRResult(mr=None, error=...)` を返す（例外を握り、eval のレポートに集約）。
    """
    req = GenerateRequest(
        subject=coord.subject, unit=coord.unit, form=coord.form, level=coord.level, seed=seed
    )
    ctx = resolve(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
    if not isinstance(ctx, CellContext):
        return MRResult(coord=coord, seed=seed, mr=None, attempts=0, error=f"resolve:{ctx.code}")

    rng = derive_rng(ctx.family, ctx.level, ctx.purpose, seed)
    try:
        mr, attempts = _construct_with_bounded_retry(ctx, rng, env)
    except Exception as e:  # noqa: BLE001
        return MRResult(coord=coord, seed=seed, mr=None, attempts=_MAX_BOUNDED_RETRY,
                        error=f"construct:{type(e).__name__}:{e}")
    mr = mr.model_copy(update={"seed": seed})
    return MRResult(coord=coord, seed=seed, mr=mr, attempts=attempts)


# ---------------------------------------------------------------------------
# remedial 対応の走査（§5.2・remedial DoD）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RemedialCase:
    """1つの誤答要因の remedial 対応（送り側の要求セル → 戻り先座標 → 対象概念）。"""

    cause_id: str
    target_concepts: tuple[str, ...]
    requesting: Coordinate  # この要因を cause_tags に持つ実在セル（送り側）
    remediation_unit: str
    remediation_form: str
    remediation_level: int | None


def requesting_cell_for_cause(cause_id: str, env: EvalEnv) -> Coordinate | None:
    """cause_id を cause_tags に含む capability セルを1つ返す（送り側の実セル）。"""
    caps = {(c.unit, c.form, c.level): c for c in capability_cells(env)}
    for family_name, spec in env.families.items():
        parts = family_name.split(".", 2)
        if len(parts) != 3:
            continue
        _subject, unit, form = parts
        for spec_level in spec.levels.values():
            if cause_id in spec_level.cause_tags:
                key = (unit, form, spec_level.level)
                if key in caps:
                    return caps[key]
    return None


def remedial_cases(env: EvalEnv) -> list[RemedialCase]:
    """curriculum の全誤答要因について remedial 対応表を組み立てる。

    送り側セル（cause を cause_tags に持つ実在セル）が見つからない要因は
    `requesting=None` にできないため除外し、呼び出し側で「送り側不在」を別途検出できる
    よう `unreferenced_causes` で補完する。ここでは送り側が引ける要因のみ返す。
    """
    cases: list[RemedialCase] = []
    for cause_id, cause in sorted(env.curriculum.error_causes.items()):
        requesting = requesting_cell_for_cause(cause_id, env)
        if requesting is None:
            continue
        cases.append(
            RemedialCase(
                cause_id=cause_id,
                target_concepts=cause.target_concepts,
                requesting=requesting,
                remediation_unit=cause.remediation.unit,
                remediation_form=cause.remediation.form,
                remediation_level=cause.remediation.level,
            )
        )
    return cases


def unreferenced_causes(env: EvalEnv) -> list[str]:
    """どの capability セルの cause_tags にも現れない要因（送り側不在）。"""
    referenced: set[str] = set()
    for spec in env.families.values():
        for spec_level in spec.levels.values():
            referenced.update(spec_level.cause_tags)
    return sorted(set(env.curriculum.error_causes) - referenced)


def remedial_request(case: RemedialCase, seed: int) -> GenerateRequest:
    """RemedialCase から remedial の GenerateRequest を組む（送り側座標 + cause_id）。"""
    return GenerateRequest(
        subject=case.requesting.subject,
        unit=case.requesting.unit,
        form=case.requesting.form,
        level=case.requesting.level,
        purpose="remedial",
        seed=seed,
        options=GenerateOptions(cause_id=case.cause_id),
    )


__all__ = [
    "EvalEnv",
    "make_env",
    "capability_cells",
    "family_of",
    "cell_request",
    "MRResult",
    "build_mr",
    "RemedialCase",
    "requesting_cell_for_cause",
    "remedial_cases",
    "unreferenced_causes",
    "remedial_request",
]
