"""動点まわりの T1 テンプレート登録（実装設計 §7・§7.2）。"""
from __future__ import annotations

from engine.core.registry import REGISTRY

# g3_l31.find_value Lv2/Lv3: 動点による三角形の面積を求める（C3・visual不要）
LF_MOTION_AREA_V1 = "{{ given.condition }}。"


def _register_all() -> None:
    REGISTRY.register_template("lf_motion_area_v1", LF_MOTION_AREA_V1)


_register_all()


__all__ = ["LF_MOTION_AREA_V1"]
