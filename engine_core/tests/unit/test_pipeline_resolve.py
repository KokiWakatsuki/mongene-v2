"""Task4: pipeline.resolve() の unit テスト。

curriculum / families / registry はすべてテスト内で注入する（本物の
engine/curriculum・engine/packs の内容には依存しない・自己完結）。resolve の
判定順（F-5 明示拒否）: unit_not_found / form_not_supported / level_not_supported /
not_implemented（FamilySpec 不在・frame 未登録）を検証する。
"""
from __future__ import annotations

from typing import Any

from engine.core.contracts import (
    CellContext,
    Coordinate,
    GenerateRequest,
    SpecFamily,
    SpecLevel,
    Unsupported,
    VisualReq,
)
from engine.core.curriculum import CurriculumModel
from engine.core.pipeline import resolve
from engine.core.registry import _Registry


# ---------------------------------------------------------------------------
# ダミー frame（FrameProtocol を満たす最小実装）
# ---------------------------------------------------------------------------
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


def _find_value_frame() -> DummyFrame:
    return DummyFrame(
        form="find_value",
        given_vocab=frozenset({"point_a", "point_b"}),
        asked_vocab=frozenset({"expression"}),
        visual="optional",
    )


# ---------------------------------------------------------------------------
# ダミー curriculum（unit/g2_l25 のみを持つ）
# ---------------------------------------------------------------------------
def _dummy_curriculum(*, with_form: bool = True, with_level: bool = True) -> CurriculumModel:
    forms: dict[str, Any] = {}
    if with_form:
        levels: dict[str, Any] = {}
        if with_level:
            levels["2"] = {"desc": "d", "example": "e"}
        forms["find_value"] = {"levels": levels}
    return CurriculumModel(
        units={"g2_l25": {"forms": forms}},
        concepts={},
        error_causes={},
        prerequisites=[],
    )


def _dummy_registry(*, with_frame: bool = True) -> _Registry:
    reg = _Registry()

    @reg.register_recipe("math.dummy_recipe")
    def _recipe(ctx: Any, rng: Any) -> Any:  # noqa: ANN001
        return None

    reg.register_template("dummy_template_v1", "問題文テンプレ")

    if with_frame:
        reg.register_frame(_find_value_frame())
    return reg


def _dummy_spec_family(*, level: int = 2) -> SpecFamily:
    return SpecFamily(
        family="math.g2_l25.find_value",
        form="find_value",
        source_desc="ダミーの source_desc",
        concepts_default=["c1"],
        levels={
            str(level): SpecLevel(
                level=level,
                signature="sig1",
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
        remedial_default_level=2,
    )


def _req(*, unit: str = "g2_l25", form: str = "find_value", level: int = 2) -> GenerateRequest:
    return GenerateRequest(subject="math", unit=unit, form=form, level=level)


# ---------------------------------------------------------------------------
# 正常系
# ---------------------------------------------------------------------------
def test_resolve_success_requested_equals_resolved():
    curriculum = _dummy_curriculum()
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry()

    ctx = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(ctx, CellContext)
    assert ctx.unit == "g2_l25"
    assert ctx.form == "find_value"
    assert ctx.level == 2
    assert ctx.requested == Coordinate(subject="math", unit="g2_l25", form="find_value", level=2)
    assert ctx.spec_family.family == "math.g2_l25.find_value"
    assert ctx.spec_level.level == 2
    assert ctx.frame.form == "find_value"


# ---------------------------------------------------------------------------
# unit_not_found
# ---------------------------------------------------------------------------
def test_resolve_unit_not_found():
    curriculum = _dummy_curriculum()
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry()

    result = resolve(_req(unit="ghost_unit"), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "unit_not_found"


# ---------------------------------------------------------------------------
# form_not_supported（curriculum に form が無い場合）
# ---------------------------------------------------------------------------
def test_resolve_form_not_supported_when_curriculum_lacks_form():
    curriculum = _dummy_curriculum(with_form=False)
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry()

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "form_not_supported"


# ---------------------------------------------------------------------------
# level_not_supported（curriculum に level が無い場合）
# ---------------------------------------------------------------------------
def test_resolve_level_not_supported_when_curriculum_lacks_level():
    curriculum = _dummy_curriculum(with_level=False)
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry()

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "level_not_supported"


# ---------------------------------------------------------------------------
# not_implemented（FamilySpec が families に無い）
# ---------------------------------------------------------------------------
def test_resolve_not_implemented_when_family_spec_missing():
    curriculum = _dummy_curriculum()
    families: dict[str, SpecFamily] = {}
    registry = _dummy_registry()

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented"


# ---------------------------------------------------------------------------
# not_implemented（FamilySpec はあるがそのレベルが無い）
# ---------------------------------------------------------------------------
def test_resolve_not_implemented_when_level_missing_in_spec():
    curriculum = _dummy_curriculum()
    families = {"math.g2_l25.find_value": _dummy_spec_family(level=3)}
    registry = _dummy_registry()

    result = resolve(_req(level=2), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented"


# ---------------------------------------------------------------------------
# form_not_supported（frame 未登録）
# ---------------------------------------------------------------------------
def test_resolve_form_not_supported_when_frame_unregistered():
    curriculum = _dummy_curriculum()
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry(with_frame=False)

    result = resolve(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "form_not_supported"


# ---------------------------------------------------------------------------
# 両方注入できることの確認（curriculum/families が引数無しでは load_curriculum/load_family_dir
# を使うため、テストは必ず注入する。これ自体を明示的に確認する。）
# ---------------------------------------------------------------------------
def test_resolve_accepts_injected_curriculum_and_families():
    curriculum = _dummy_curriculum()
    families = {"math.g2_l25.find_value": _dummy_spec_family()}
    registry = _dummy_registry()

    ctx = resolve(_req(), curriculum=curriculum, families=families, registry=registry)
    assert isinstance(ctx, CellContext)
