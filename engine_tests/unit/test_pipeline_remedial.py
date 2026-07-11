"""Task4: pipeline.resolve() の remedial 解決テスト（実装設計 §5.2）。

purpose=="remedial" は options.cause_id 必須。cause を curriculum から引き、
remediation 座標（unit/form/level。level 省略時は FamilySpec.remedial_default_level）
で再解決する。成功時: requested は元リクエスト座標、CellContext の
unit/form/level（resolved 相当）は戻り先座標。cause_not_found・戻り先が
capabilities 外（not_implemented）も検証する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import (
    CellContext,
    Coordinate,
    GenerateOptions,
    GenerateRequest,
    SpecFamily,
    SpecLevel,
    Unsupported,
    VisualReq,
)
from engine.core.curriculum import CurriculumModel, ErrorCause, Remediation
from engine.core.pipeline import resolve
from engine.core.registry import _Registry


class DummyFrame:
    def __init__(self, form: str, given_vocab: frozenset[str], asked_vocab: frozenset[str], visual: VisualReq) -> None:
        self.form = form
        self.given_vocab = given_vocab
        self.asked_vocab = asked_vocab
        self.visual = visual

    def check_mr(self, mr: Any) -> tuple[bool, str]:
        return True, ""

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        return frozenset()


def _frame() -> DummyFrame:
    return DummyFrame(
        form="find_value",
        given_vocab=frozenset({"point_a", "point_b", "slope"}),
        asked_vocab=frozenset({"expression"}),
        visual="optional",
    )


def _curriculum(*, remediation_level: int | None = 1) -> CurriculumModel:
    """要求元セル g2_l25/find_value/Lv2 と、戻り先 g1_l36/find_value/Lv1(or 省略) を持つ。"""
    return CurriculumModel(
        units={
            "g2_l25": {"forms": {"find_value": {"levels": {"2": {"desc": "d", "example": "e"}}}}},
            "g1_l36": {
                "forms": {
                    "find_value": {
                        "levels": {str(remediation_level or 1): {"desc": "d2", "example": "e2"}}
                    }
                }
            },
        },
        concepts={},
        error_causes={
            "lf.confused_with_proportional": ErrorCause(
                id="lf.confused_with_proportional",
                label="比例と混同した",
                target_concepts=(),
                remediation=Remediation(unit="g1_l36", form="find_value", level=remediation_level),
            )
        },
        prerequisites=[],
    )


def _registry() -> _Registry:
    reg = _Registry()

    @reg.register_recipe("math.dummy_recipe")
    def _recipe(ctx: Any, rng: Any) -> Any:  # noqa: ANN001
        return None

    reg.register_template("dummy_template_v1", "テンプレ")
    reg.register_frame(_frame())
    return reg


def _spec_family(*, unit: str, level: int, remedial_default_level: int | None = None) -> SpecFamily:
    return SpecFamily(
        family=f"math.{unit}.find_value",
        form="find_value",
        source_desc="ダミー",
        concepts_default=["c1"],
        levels={
            str(level): SpecLevel(
                level=level,
                signature=f"sig_{unit}_{level}",
                recipe="math.dummy_recipe",
                params={},
                given=["point_a", "point_b"],
                asked=["expression"],
                visual="none",
                text={"tier": "T1", "template": "dummy_template_v1"},
                hints=["steps_prefix"],
                cause_tags=[],
            )
        },
        remedial_default_level=remedial_default_level,
    )


def _req(*, cause_id: str | None = "lf.confused_with_proportional") -> GenerateRequest:
    return GenerateRequest(
        subject="math", unit="g2_l25", form="find_value", level=2,
        purpose="remedial",
        options=GenerateOptions(cause_id=cause_id),
    )


# ---------------------------------------------------------------------------
# 正常系: remediation.level 明示
# ---------------------------------------------------------------------------
def test_remedial_resolves_to_remediation_coordinate_with_explicit_level():
    curriculum = _curriculum(remediation_level=1)
    families = {
        "math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2),
        "math.g1_l36.find_value": _spec_family(unit="g1_l36", level=1),
    }
    registry = _registry()

    ctx = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(ctx, CellContext)
    # requested は元リクエスト座標
    assert ctx.requested == Coordinate(subject="math", unit="g2_l25", form="find_value", level=2)
    # resolved（CellContext の座標そのもの）は戻り先
    assert ctx.unit == "g1_l36"
    assert ctx.form == "find_value"
    assert ctx.level == 1
    assert ctx.purpose == "remedial"


# ---------------------------------------------------------------------------
# 正常系: remediation.level 省略 → FamilySpec.remedial_default_level を使う
# ---------------------------------------------------------------------------
def test_remedial_uses_family_default_level_when_remediation_level_omitted():
    curriculum = _curriculum(remediation_level=None)
    families = {
        "math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2),
        "math.g1_l36.find_value": _spec_family(unit="g1_l36", level=1, remedial_default_level=1),
    }
    registry = _registry()

    ctx = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(ctx, CellContext)
    assert ctx.unit == "g1_l36"
    assert ctx.level == 1


# ---------------------------------------------------------------------------
# cause_id 必須（欠落）
# ---------------------------------------------------------------------------
def test_remedial_missing_cause_id_is_cause_not_found():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2)}
    registry = _registry()

    result = resolve(_req(cause_id=None), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "cause_not_found"


# ---------------------------------------------------------------------------
# cause_id が curriculum に無い
# ---------------------------------------------------------------------------
def test_remedial_unknown_cause_id_is_cause_not_found():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2)}
    registry = _registry()

    result = resolve(_req(cause_id="ghost.cause"), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "cause_not_found"


# ---------------------------------------------------------------------------
# 戻り先が capabilities 外（FamilySpec 無し）→ not_implemented
# ---------------------------------------------------------------------------
def test_remedial_target_outside_capabilities_is_not_implemented():
    curriculum = _curriculum(remediation_level=1)
    families = {
        "math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2),
        # g1_l36 の FamilySpec を意図的に欠落させる
    }
    registry = _registry()

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented"


# ---------------------------------------------------------------------------
# 戻り先座標が curriculum タクソノミーにすら無い → not_implemented
# ---------------------------------------------------------------------------
def test_remedial_target_missing_from_taxonomy_is_not_implemented():
    curriculum = CurriculumModel(
        units={"g2_l25": {"forms": {"find_value": {"levels": {"2": {"desc": "d", "example": "e"}}}}}},
        concepts={},
        error_causes={
            "lf.confused_with_proportional": ErrorCause(
                id="lf.confused_with_proportional", label="l", target_concepts=(),
                remediation=Remediation(unit="g1_l99_ghost", form="find_value", level=1),
            )
        },
        prerequisites=[],
    )
    families = {"math.g2_l25.find_value": _spec_family(unit="g2_l25", level=2)}
    registry = _registry()

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented"
