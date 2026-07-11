"""Task5b: 縦串 FamilySpec YAML（engine/curriculum/math/families）の lint clean 検証。

load_family_dir で全 family を読み、lint_family（R1〜R8）を curriculum の実物
（概念ID集合・要因ID集合）と REGISTRY の実物（recipe/template）・7 frame 辞書を
注入して検査する。M0 縦串 = g2_l25.find_value / g2_l24.find_value / g2_l25.graph_table。
"""
from __future__ import annotations

from pathlib import Path

import engine.packs.math  # noqa: F401  (register_recipe/template/frame の副作用のため import)
from engine.core.curriculum import load_curriculum
from engine.core.registry import REGISTRY
from engine.core.spec.lint import lint_family
from engine.core.spec.loader import load_family_dir

FAMILIES_DIR = Path("engine/curriculum/math/families")

_KNOWN_FORMS = [
    "calculation", "knowledge", "find_value", "graph_table",
    "word_problem", "proof", "construction",
]


def _frames() -> dict:
    return {form: REGISTRY.frame(form) for form in _KNOWN_FORMS if REGISTRY.has_frame(form)}


def test_families_dir_has_expected_m0_vertical_slice():
    families = load_family_dir(FAMILIES_DIR)
    assert set(families.keys()) == {
        "math.g2_l25.find_value",
        "math.g2_l24.find_value",
        "math.g2_l25.graph_table",
    }


def test_all_m0_families_lint_clean():
    curriculum = load_curriculum()
    families = load_family_dir(FAMILIES_DIR)
    frames = _frames()
    concepts = curriculum.concept_ids()
    causes = curriculum.cause_ids()

    for name, spec in families.items():
        errors = lint_family(spec, registry=REGISTRY, concepts=concepts, causes=causes, frames=frames)
        assert errors == [], f"{name}: lint エラー {errors}"


def test_g2_l25_find_value_levels_present():
    families = load_family_dir(FAMILIES_DIR)
    spec = families["math.g2_l25.find_value"]
    assert set(spec.levels.keys()) == {"2", "3"}
    assert spec.levels["2"].signature != spec.levels["3"].signature


def test_g2_l24_find_value_levels_present():
    families = load_family_dir(FAMILIES_DIR)
    spec = families["math.g2_l24.find_value"]
    assert set(spec.levels.keys()) == {"1", "3"}
    assert spec.levels["1"].signature != spec.levels["3"].signature


def test_g2_l24_lv1_concept_tags_include_intercept_from_point():
    """remedial G-Q7r の静的前提: lf.confused_with_proportional / lf.substitution_error の
    戻り先が g2_l24 find_value Lv1 で target_concepts=[linear_function.intercept_from_point]。
    """
    families = load_family_dir(FAMILIES_DIR)
    spec = families["math.g2_l24.find_value"]
    lv1 = spec.levels["1"]
    assert "linear_function.intercept_from_point" in lv1.concept_tags


def test_g2_l25_graph_table_visual_required():
    families = load_family_dir(FAMILIES_DIR)
    spec = families["math.g2_l25.graph_table"]
    lv2 = spec.levels["2"]
    assert lv2.visual == "required"


def test_source_desc_transcribed_from_units_generated_yaml():
    """R8: source_desc に units.generated.yaml の desc/example が転記されていること。"""
    families = load_family_dir(FAMILIES_DIR)

    g2_l25_fv = families["math.g2_l25.find_value"].source_desc
    assert "2点から傾きを出し" in g2_l25_fv
    assert "(1, 3)" in g2_l25_fv

    g2_l24_fv = families["math.g2_l24.find_value"].source_desc
    assert "傾きと1点を代入し切片を求めて式を決める" in g2_l24_fv
    assert "平行" in g2_l24_fv

    g2_l25_gt = families["math.g2_l25.graph_table"].source_desc
    assert "グラフ上の2点の座標を読み取る" in g2_l25_gt
