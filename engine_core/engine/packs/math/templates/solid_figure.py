"""空間図形の「計量」まわりの T1 テンプレート登録（C8 横展開9セル）。

いずれも statement を recipe 側で完成させて given に渡す（sector 系と同型）ため、
テンプレートは given をそのまま句点で閉じるだけ。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g1_l51.find_value Lv1: 角柱・円柱の表面積(直接)
LF_SOLID_SURFACE_DIRECT_V1 = "{{ given.condition }}。"

# g1_l51.find_value Lv2: 円錐の中心角経由の表面積
LF_SOLID_CONE_SURFACE_CENTRAL_ANGLE_V1 = "{{ given.condition }}。"

# g1_l51.find_value Lv3: 複合立体/逆算の表面積
LF_SOLID_COMPOSITE_OR_REVERSE_SURFACE_V1 = "{{ given.condition }}。"

# g1_l52.calculation Lv1: 円柱の体積の公式代入
LF_SOLID_CYLINDER_VOLUME_SUBSTITUTION_V1 = "{{ given.expression }}。"

# g1_l52.find_value Lv1: 角柱・角錐の体積(直接)
LF_SOLID_PRISM_PYRAMID_VOLUME_DIRECT_V1 = "{{ given.condition }}。"

# g1_l52.find_value Lv2: 直角三角形底面の体積(多段)
LF_SOLID_RIGHT_TRIANGLE_VOLUME_MULTISTEP_V1 = "{{ given.condition }}。"

# g1_l52.find_value Lv3: 複合立体/逆算の体積
LF_SOLID_COMPOSITE_OR_REVERSE_VOLUME_V1 = "{{ given.condition }}。"

# g1_l53.find_value Lv1: 球の表面積・体積(直接)
LF_SOLID_SPHERE_DIRECT_V1 = "{{ given.condition }}。"

# g1_l53.find_value Lv2: 半球/逆算の表面積
LF_SOLID_HEMISPHERE_OR_REVERSE_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_solid_surface_direct_v1", LF_SOLID_SURFACE_DIRECT_V1)
    REGISTRY.register_template(
        "lf_solid_cone_surface_central_angle_v1", LF_SOLID_CONE_SURFACE_CENTRAL_ANGLE_V1
    )
    REGISTRY.register_template(
        "lf_solid_composite_or_reverse_surface_v1", LF_SOLID_COMPOSITE_OR_REVERSE_SURFACE_V1
    )
    REGISTRY.register_template(
        "lf_solid_cylinder_volume_substitution_v1", LF_SOLID_CYLINDER_VOLUME_SUBSTITUTION_V1
    )
    REGISTRY.register_template(
        "lf_solid_prism_pyramid_volume_direct_v1", LF_SOLID_PRISM_PYRAMID_VOLUME_DIRECT_V1
    )
    REGISTRY.register_template(
        "lf_solid_right_triangle_volume_multistep_v1", LF_SOLID_RIGHT_TRIANGLE_VOLUME_MULTISTEP_V1
    )
    REGISTRY.register_template(
        "lf_solid_composite_or_reverse_volume_v1", LF_SOLID_COMPOSITE_OR_REVERSE_VOLUME_V1
    )
    REGISTRY.register_template("lf_solid_sphere_direct_v1", LF_SOLID_SPHERE_DIRECT_V1)
    REGISTRY.register_template(
        "lf_solid_hemisphere_or_reverse_v1", LF_SOLID_HEMISPHERE_OR_REVERSE_V1
    )


_register_all()


__all__ = [
    "LF_SOLID_SURFACE_DIRECT_V1",
    "LF_SOLID_CONE_SURFACE_CENTRAL_ANGLE_V1",
    "LF_SOLID_COMPOSITE_OR_REVERSE_SURFACE_V1",
    "LF_SOLID_CYLINDER_VOLUME_SUBSTITUTION_V1",
    "LF_SOLID_PRISM_PYRAMID_VOLUME_DIRECT_V1",
    "LF_SOLID_RIGHT_TRIANGLE_VOLUME_MULTISTEP_V1",
    "LF_SOLID_COMPOSITE_OR_REVERSE_VOLUME_V1",
    "LF_SOLID_SPHERE_DIRECT_V1",
    "LF_SOLID_HEMISPHERE_OR_REVERSE_V1",
]
