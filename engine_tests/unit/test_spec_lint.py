"""Task2: FamilySpec のローダ・spec_lint テスト（R1〜R5 fail + 正常系 + ローダ往復）。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from engine.core.contracts import SpecFamily, VisualReq
from engine.core.registry import _Registry
from engine.core.spec.lint import LintError, lint_family
from engine.core.spec.loader import load_family_dir, load_family_spec


# ---------------------------------------------------------------------------
# ダミー frame（FrameProtocol を満たす簡単なオブジェクト）
# ---------------------------------------------------------------------------
class DummyFrame:
    def __init__(
        self,
        form: str,
        given_vocab: frozenset[str],
        asked_vocab: frozenset[str],
        visual: VisualReq,
    ) -> None:
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
        given_vocab=frozenset({"point_a", "point_b", "slope", "intercept"}),
        asked_vocab=frozenset({"value", "expression", "coordinate"}),
        visual="optional",
    )


def _calculation_frame_no_visual() -> DummyFrame:
    return DummyFrame(
        form="calculation",
        given_vocab=frozenset({"expression", "equation"}),
        asked_vocab=frozenset({"value", "simplified_expr", "solution"}),
        visual="none",
    )


# ---------------------------------------------------------------------------
# 共通フィクスチャ: registry にダミー recipe/template/checker を登録
# ---------------------------------------------------------------------------
def _make_registry() -> _Registry:
    reg = _Registry()

    @reg.register_recipe("math.linear_from_two_points", provides_concepts=["linear_function.expression_from_points"])
    def _recipe(ctx: Any, rng: Any) -> Any:  # noqa: ANN001
        return None

    @reg.register_recipe("math.no_concepts_declared")
    def _recipe2(ctx: Any, rng: Any) -> Any:  # noqa: ANN001
        return None

    reg.register_template("lf_expr_two_points_v1", object())

    @reg.register_checker("style.currency_yen")
    def _checker(*a: Any, **kw: Any) -> Any:
        return None

    return reg


def _clean_spec_dict() -> dict[str, Any]:
    return {
        "family": "math.g2_l25.find_value",
        "form": "find_value",
        "source_desc": "2点の座標から1次関数の式を求める。Lv2=傾き→切片。",
        "concepts_default": ["linear_function.expression_from_points"],
        "levels": {
            "2": {
                "signature": "lf_expr_two_points_basic",
                "recipe": "math.linear_from_two_points",
                "params": {
                    "method": "slope_then_intercept",
                    "slope_domain": {"int_range": [-4, 4], "exclude": [0]},
                    "point_domain": {
                        "lattice": {"x": {"int_range": [-5, 5]}, "y": {"int_range": [-8, 8]}},
                        "distinct": ["x"],
                    },
                },
                "given": ["point_a", "point_b"],
                "asked": ["expression"],
                "visual": "none",
                "text": {"tier": "T1", "template": "lf_expr_two_points_v1"},
                "hints": ["steps_prefix"],
                "cause_tags": ["lf.slope_formula_error"],
            },
            "3": {
                "signature": "lf_expr_two_points_simultaneous",
                "recipe": "math.linear_from_two_points",
                "params": {
                    "method": "simultaneous",
                    "slope_domain": {"frac_range": {"num": [-5, 5], "den": [2, 3]}},
                },
                "given": ["point_a", "point_b"],
                "asked": ["expression"],
                "visual": "optional",
                "text": {"tier": "T1", "template": "lf_expr_two_points_v1"},
                "hints": ["steps_prefix"],
                "cause_tags": ["lf.simultaneous_setup_error"],
            },
        },
        "remedial": {"default_level": 2},
    }


def _spec_from_dict(d: dict[str, Any]) -> SpecFamily:
    from engine.core.contracts import SpecLevel

    levels = {}
    for k, v in (d.get("levels") or {}).items():
        block = dict(v)
        block["level"] = int(k)
        levels[str(k)] = SpecLevel(**block)
    return SpecFamily(
        family=d["family"],
        form=d["form"],
        source_desc=d.get("source_desc", ""),
        concepts_default=list(d.get("concepts_default") or []),
        levels=levels,
        remedial_default_level=(d.get("remedial") or {}).get("default_level"),
    )


# ---------------------------------------------------------------------------
# 正常系: 全 clean
# ---------------------------------------------------------------------------
def test_clean_spec_has_no_errors():
    reg = _make_registry()
    spec = _spec_from_dict(_clean_spec_dict())
    frames = {"find_value": _find_value_frame()}
    errors = lint_family(
        spec,
        registry=reg,
        concepts={"linear_function.expression_from_points"},
        causes={"lf.slope_formula_error", "lf.simultaneous_setup_error"},
        frames=frames,
    )
    assert errors == []


def test_clean_spec_with_no_injections_skips_r4_r5():
    """concepts/causes/frames が None の場合、それらに依存する規則はスキップされる。"""
    reg = _make_registry()
    spec = _spec_from_dict(_clean_spec_dict())
    errors = lint_family(spec, registry=reg)
    assert errors == []


# ---------------------------------------------------------------------------
# R1: 未登録の recipe/template/checker
# ---------------------------------------------------------------------------
def test_r1_fails_on_unregistered_recipe():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["recipe"] = "math.does_not_exist"
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R1" and "math.does_not_exist" in e.message for e in errors)


def test_r1_fails_on_unregistered_template():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["text"] = {"tier": "T1", "template": "no_such_template_v9"}
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R1" and "no_such_template_v9" in e.message for e in errors)


# ---------------------------------------------------------------------------
# R2: signature 重複
# ---------------------------------------------------------------------------
def test_r2_fails_on_duplicate_signature():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["3"]["signature"] = d["levels"]["2"]["signature"]
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R2" for e in errors)


# ---------------------------------------------------------------------------
# R3: ドメイン記法不正
# ---------------------------------------------------------------------------
def test_r3_fails_on_invalid_domain_vocab():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["params"]["slope_domain"] = {"magic_domain": [1, 2]}
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R3" for e in errors)


def test_r3_fails_on_malformed_int_range():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["params"]["slope_domain"] = {"int_range": [5, 1]}  # a > b
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R3" for e in errors)


# ---------------------------------------------------------------------------
# R4: concept/cause が curriculum に不在
# ---------------------------------------------------------------------------
def test_r4_fails_on_unknown_concept():
    reg = _make_registry()
    spec = _spec_from_dict(_clean_spec_dict())
    errors = lint_family(
        spec, registry=reg,
        concepts={"totally_unrelated_concept"},
        causes={"lf.slope_formula_error", "lf.simultaneous_setup_error"},
    )
    assert any(e.rule == "R4" and "linear_function.expression_from_points" in e.message for e in errors)


def test_r4_fails_on_unknown_cause():
    reg = _make_registry()
    spec = _spec_from_dict(_clean_spec_dict())
    errors = lint_family(
        spec, registry=reg,
        concepts={"linear_function.expression_from_points"},
        causes={"totally_unrelated_cause"},
    )
    assert any(e.rule == "R4" and "lf.slope_formula_error" in e.message for e in errors)


# ---------------------------------------------------------------------------
# R5: form/frame 不整合
# ---------------------------------------------------------------------------
def test_r5_fails_on_given_not_in_frame_vocab():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["given"] = ["point_a", "point_b", "totally_unknown_given"]
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg, frames={"find_value": _find_value_frame()})
    assert any(e.rule == "R5" and "totally_unknown_given" in e.message for e in errors)


def test_r5_fails_on_asked_not_in_frame_vocab():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["asked"] = ["totally_unknown_asked"]
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg, frames={"find_value": _find_value_frame()})
    assert any(e.rule == "R5" and "totally_unknown_asked" in e.message for e in errors)


def test_r5_fails_when_visual_required_but_frame_forbids():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["family"] = "math.g2_lXX.calculation"
    d["form"] = "calculation"
    d["levels"]["2"]["given"] = ["expression"]
    d["levels"]["2"]["asked"] = ["value"]
    d["levels"]["2"]["visual"] = "required"
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg, frames={"calculation": _calculation_frame_no_visual()})
    assert any(e.rule == "R5" and "frame.visual=none" in e.message for e in errors)


def test_r5_skipped_when_frames_not_injected():
    reg = _make_registry()
    spec = _spec_from_dict(_clean_spec_dict())
    errors = lint_family(spec, registry=reg, frames=None)
    assert not any(e.rule == "R5" for e in errors)


# ---------------------------------------------------------------------------
# R6: 題材ズレ（recipe 宣言概念の部分集合検査）
# ---------------------------------------------------------------------------
def test_r6_fails_when_concepts_not_subset_of_recipe_declaration():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["concepts_default"] = ["linear_function.expression_from_points", "unrelated.concept"]
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R6" for e in errors)


def test_r6_skipped_when_recipe_declares_no_concepts():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["recipe"] = "math.no_concepts_declared"
    d["levels"]["3"]["recipe"] = "math.no_concepts_declared"
    d["concepts_default"] = ["anything.goes"]
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert not any(e.rule == "R6" for e in errors)


# ---------------------------------------------------------------------------
# R7: hints が空
# ---------------------------------------------------------------------------
def test_r7_fails_on_empty_hints():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["levels"]["2"]["hints"] = []
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R7" for e in errors)


# ---------------------------------------------------------------------------
# R8: source_desc 空
# ---------------------------------------------------------------------------
def test_r8_fails_on_empty_source_desc():
    reg = _make_registry()
    d = _clean_spec_dict()
    d["source_desc"] = "   "
    spec = _spec_from_dict(d)
    errors = lint_family(spec, registry=reg)
    assert any(e.rule == "R8" for e in errors)


# ---------------------------------------------------------------------------
# ローダの往復（YAML → SpecFamily）
# ---------------------------------------------------------------------------
def test_loader_roundtrip_from_yaml(tmp_path: Path):
    d = _clean_spec_dict()
    yaml_path = tmp_path / "g2_l25.find_value.yaml"
    yaml_path.write_text(yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8")

    spec = load_family_spec(yaml_path)

    assert spec.family == "math.g2_l25.find_value"
    assert spec.form == "find_value"
    assert spec.remedial_default_level == 2
    assert set(spec.levels.keys()) == {"2", "3"}
    lvl2 = spec.levels["2"]
    assert lvl2.level == 2
    assert lvl2.signature == "lf_expr_two_points_basic"
    assert lvl2.text == {"tier": "T1", "template": "lf_expr_two_points_v1"}
    assert lvl2.params["method"] == "slope_then_intercept"


def test_loader_propagates_validation_error(tmp_path: Path):
    """構造不正（levels が不正な型等）は pydantic ValidationError がそのまま伝播する。"""
    bad = {
        "family": "math.bad.family",
        "form": "find_value",
        "levels": {
            "2": {
                # signature/recipe が欠落 → SpecLevel の必須フィールド不足で ValidationError
                "given": ["point_a"],
            },
        },
    }
    yaml_path = tmp_path / "bad.yaml"
    yaml_path.write_text(yaml.safe_dump(bad, allow_unicode=True), encoding="utf-8")

    with pytest.raises(Exception):
        load_family_spec(yaml_path)


def test_load_family_dir_loads_all_yaml(tmp_path: Path):
    d1 = _clean_spec_dict()
    d2 = _clean_spec_dict()
    d2["family"] = "math.g2_l25.knowledge"
    d2["form"] = "knowledge"

    (tmp_path / "a.yaml").write_text(yaml.safe_dump(d1, allow_unicode=True), encoding="utf-8")
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(d2, allow_unicode=True), encoding="utf-8")
    (tmp_path / "not_yaml.txt").write_text("ignore me", encoding="utf-8")

    families = load_family_dir(tmp_path)
    assert set(families.keys()) == {"math.g2_l25.find_value", "math.g2_l25.knowledge"}


# ---------------------------------------------------------------------------
# LintError の形（dataclass）
# ---------------------------------------------------------------------------
def test_lint_error_is_dataclass_with_expected_fields():
    e = LintError(rule="R1", message="m", level_key="2")
    assert e.rule == "R1"
    assert e.message == "m"
    assert e.level_key == "2"
