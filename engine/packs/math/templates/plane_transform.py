"""平面図形の移動（平行移動・回転移動・対称移動）の T1 テンプレート登録

（実装設計 §7・§7.2）。Lv1(grid_only)は given.polygon_points、Lv2(coordinate)は
given.polygon_coordinates を使う（level_sep・G-FP 対策で given のキー名を分けている
ため、テンプレートも対応するキーを参照する2種になる）。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

LF_POLYGON_TRANSFORM_GRID_V1 = "{{ given.polygon_points }}この三角形を、{{ given.move_spec }}三角形A'B'C'をかけ。"
# 「3頂点」と数字で書くと、答えの座標値と偶然一致し G-Q5t が誤検知する
# （固定テンプレ文中の数字は given 由来でなく whitelist されないため）。「各頂点」で
# 数字を避ける（鉄則: テンプレ文にも digit-free を徹底する）。
LF_POLYGON_TRANSFORM_COORDINATE_V1 = (
    "{{ given.polygon_coordinates }}この三角形を、{{ given.move_spec }}とき、"
    "移動後の各頂点の座標をそれぞれ答え、移動後の三角形を図示せよ。"
)


def _register_all() -> None:
    REGISTRY.register_template("lf_polygon_transform_grid_v1", LF_POLYGON_TRANSFORM_GRID_V1)
    REGISTRY.register_template(
        "lf_polygon_transform_coordinate_v1", LF_POLYGON_TRANSFORM_COORDINATE_V1
    )


_register_all()


__all__ = [
    "LF_POLYGON_TRANSFORM_GRID_V1",
    "LF_POLYGON_TRANSFORM_COORDINATE_V1",
]
