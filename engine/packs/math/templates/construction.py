"""基本作図（form: construction）の T1 テンプレート登録（実装設計 §7・§7.2）。

台帳（units.generated.yaml）の example をそのまま問題文の型にしている。作図の問題文は
市販の問題集でも言い方が固定されているので、テンプレートで揺らさない。

**テンプレートに数字を一切書かない**（G-Q5t）。本文に出る数は given 由来の助数詞
（「2点」「3点」）と、助数詞除去の対象になる「1つ」「2辺」だけである。

記号名（点の名前）は given の文字列にだけ現れるようにし、テンプレート側は
「この点」「その線分」と受けている——名前を動かしても文が壊れないようにするため。
"""
from __future__ import annotations

from engine.core.registry import REGISTRY

_KEEP = "作図に用いた線は消さずに残すこと。"
_KEEP_SHORT = "作図に用いた線は残すこと。"

# g1_l41 Lv1: 線分の垂直二等分線
CS_PERPENDICULAR_BISECTOR_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "定規とコンパスだけを使って、この線分の垂直二等分線を作図せよ。" + _KEEP
)

# g1_l41 Lv2: 2点から等距離で直線ℓ上にある点
CS_EQUIDISTANT_POINT_ON_LINE_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "この2点から等しい距離にあり、かつ直線ℓ上にある点Pを、作図によって求めよ。" + _KEEP_SHORT
)

# g1_l42 Lv1: 角の二等分線
CS_ANGLE_BISECTOR_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "定規とコンパスだけを使って、この角の二等分線を作図せよ。" + _KEEP_SHORT
)

# g1_l42 Lv2: 角の2辺から等距離で線分上にある点
CS_EQUIDISTANT_POINT_FROM_SIDES_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "角の2辺から等しい距離にあり、かつその線分上にある点Pを、作図によって求めよ。" + _KEEP_SHORT
)

# g1_l43 Lv1: 点を通る垂線
CS_PERPENDICULAR_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "定規とコンパスだけを使って、この点を通り直線ℓに垂直な直線を作図せよ。" + _KEEP_SHORT
)

# g1_l43 Lv2: 点と直線の距離を表す線分・垂線の足
CS_FOOT_AND_DISTANCE_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "点Pと直線ℓとの距離を表す線分を作図によってかき、垂線の足Hを図中に示せ。" + _KEEP_SHORT
)

# g1_l44 Lv2: 2点から等距離にある点の集まり（基本作図1つ・誘導あり）
CS_LOCUS_EQUIDISTANT_TWO_POINTS_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "この2点から等しい距離にある点の集まりを、基本作図を1つ使って作図せよ。" + _KEEP_SHORT
)

# g1_l44 Lv3: 3点から等距離にある点（基本作図2つの交点）
CS_EQUIDISTANT_POINT_THREE_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "この3点から等しい距離にある点Pを、作図によって求めよ。" + _KEEP_SHORT
)

# g1_l44 Lv4: 辺上にあり2辺から等距離の点（方針から構成・誘導なし）
CS_POINT_ON_SIDE_EQUIDISTANT_V1 = (
    "下の図に{{ given.construction_conditions }}が与えられている。"
    "辺BC上にあり、2辺AB、ACから等しい距離にある点Pを、作図によって求めよ。"
    "どの基本作図を使うかは自分で判断すること。" + _KEEP_SHORT
)


def _register_all() -> None:
    REGISTRY.register_template("cs_perpendicular_bisector_v1", CS_PERPENDICULAR_BISECTOR_V1)
    REGISTRY.register_template(
        "cs_equidistant_point_on_line_v1", CS_EQUIDISTANT_POINT_ON_LINE_V1
    )
    REGISTRY.register_template("cs_angle_bisector_v1", CS_ANGLE_BISECTOR_V1)
    REGISTRY.register_template(
        "cs_equidistant_point_from_sides_v1", CS_EQUIDISTANT_POINT_FROM_SIDES_V1
    )
    REGISTRY.register_template("cs_perpendicular_v1", CS_PERPENDICULAR_V1)
    REGISTRY.register_template("cs_foot_and_distance_v1", CS_FOOT_AND_DISTANCE_V1)
    REGISTRY.register_template(
        "cs_locus_equidistant_two_points_v1", CS_LOCUS_EQUIDISTANT_TWO_POINTS_V1
    )
    REGISTRY.register_template("cs_equidistant_point_three_v1", CS_EQUIDISTANT_POINT_THREE_V1)
    REGISTRY.register_template(
        "cs_point_on_side_equidistant_v1", CS_POINT_ON_SIDE_EQUIDISTANT_V1
    )


_register_all()


__all__ = [
    "CS_PERPENDICULAR_BISECTOR_V1",
    "CS_EQUIDISTANT_POINT_ON_LINE_V1",
    "CS_ANGLE_BISECTOR_V1",
    "CS_EQUIDISTANT_POINT_FROM_SIDES_V1",
    "CS_PERPENDICULAR_V1",
    "CS_FOOT_AND_DISTANCE_V1",
    "CS_LOCUS_EQUIDISTANT_TWO_POINTS_V1",
    "CS_EQUIDISTANT_POINT_THREE_V1",
    "CS_POINT_ON_SIDE_EQUIDISTANT_V1",
]
