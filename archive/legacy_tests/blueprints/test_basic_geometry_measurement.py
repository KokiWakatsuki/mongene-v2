"""BasicGeometryMeasurementStructure の params 対応（measure_type 切替）の単体テスト。

G6-a修正(g1_l51再ターゲット)で `params.measure_type` を追加した際の回帰防止。
LLM は使わない。
"""
from __future__ import annotations

from apps.api.src.blueprints.basic_geometry_measurement import (
    build_basic_geometry_measurement_blueprint,
)


def test_default_params_preserve_area_measure_type_and_2d_visual():
    """params 未指定時は既存挙動（area・2D_Geometry_Renderer）を維持する（後方互換）。"""
    bp = build_basic_geometry_measurement_blueprint(None)
    assert bp.verb_invocations[0].verb.measure_type == "area"
    assert bp.visual_slot.component_type == "2D_Geometry_Renderer"
    assert bp.visual_slot.compatible_noun_types == ["PolygonAtom", "CircleAtom"]


def test_surface_area_params_switches_verb_and_visual_slot():
    """measure_type=surface_area 指定で MeasureGeometryVerb と visual_slot が3D立体向けに切り替わる。

    g1_l51（柱体・錐体の表面積）はこのモードで PrismAtom/PyramidAtom/SphereAtom の
    surface_area_expr を直接問う。
    """
    bp = build_basic_geometry_measurement_blueprint({"measure_type": "surface_area"})
    assert bp.verb_invocations[0].verb.measure_type == "surface_area"
    assert bp.visual_slot.component_type == "3D_Renderer"
    assert set(bp.visual_slot.compatible_noun_types) == {"PrismAtom", "PyramidAtom", "SphereAtom"}


def test_supported_forms_includes_calculation_and_visual():
    """calculation/visual フォームでも使える（word_problem 限定ではない）ことを保証する。

    blueprint.supported_forms 自体はランナーで強制されないが、ドキュメント/一貫性のため
    実際に使うフォームを宣言しておく。
    """
    bp = build_basic_geometry_measurement_blueprint({"measure_type": "surface_area"})
    assert "calculation" in bp.supported_forms
    assert "visual" in bp.supported_forms
