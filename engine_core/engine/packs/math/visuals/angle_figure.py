"""角の問題の図（平行線と角・三角形の角）。

★**このクラスタは長いあいだ図なしで出していた。** 「2直線ℓ、mが1点で交わっている。
∠aの大きさは135°である。∠aの対頂角にあたる∠xの大きさを求めよ」のように、
配置を全部ことばで述べていた。実物の問題集はここを必ず図で示す——どの角が ∠a で
どの角が ∠x かは、ことばで書くと長くなるうえに読み違えやすい。

図そのものは `geometry_figure.render_construction_svg`（点・線分・角の印・自由な文字を
受け取る宣言的な描き手）に任せ、ここでは**配置の座標を組む**ことだけを行う。
"""
from __future__ import annotations

import math
from typing import Any

from engine.packs.math.visuals.geometry_figure import render_construction_svg

# 平行な2直線の高さと、直線を引く範囲（図の座標系。画素へは描き手が写す）。
_TOP_Y = 2.0
_BOTTOM_Y = -2.0
_HALF_W = 4.0


def _parallel_pair_base(line_a: str, line_b: str) -> dict[str, Any]:
    """平行な2直線 ℓ・m と、それを横切る直線 n の骨組み。

    P = n と ℓ の交点、Q = n と m の交点。直線は交点の外まで伸ばす
    （伸ばさないと「2直線が交わっている」ではなく「線分がつながっている」に見える）。
    """
    slant_x = 1.2
    ext = 0.9  # 交点の外へ出す長さ（n の向きに対する倍率）
    dx, dy = 2 * slant_x, _BOTTOM_Y - _TOP_Y
    coords = {
        "P": (-slant_x, _TOP_Y),
        "Q": (slant_x, _BOTTOM_Y),
        "La": (-_HALF_W, _TOP_Y), "Lb": (_HALF_W, _TOP_Y),
        "Ma": (-_HALF_W, _BOTTOM_Y), "Mb": (_HALF_W, _BOTTOM_Y),
        "Na": (-slant_x - dx * ext / 2, _TOP_Y - dy * ext / 2),
        "Nb": (slant_x + dx * ext / 2, _BOTTOM_Y + dy * ext / 2),
    }
    return {
        "coords": coords,
        "segments": [("La", "Lb"), ("Ma", "Mb"), ("Na", "Nb")],
        "parallel_groups": [[("La", "Lb"), ("Ma", "Mb")]],
        "hidden_points": ["La", "Lb", "Ma", "Mb", "Na", "Nb"],
        "unnamed_points": ["P", "Q"],
        "free_labels": [
            ["Lb", line_a, 16, -6],
            ["Mb", line_b, 16, -6],
            ["Nb", "n", 14, 12],
        ],
    }


def angle_equality_svg(relation: str, angle_label: str, x_label: str) -> str:
    """対頂角・同位角・錯角のいずれか1組を示す図（g2_l31/l32.find_value Lv1）。

    `relation` は "vertical"（2直線が交わる）／"corresponding"（同位角）／
    "alternate"（錯角）。**どの角が ∠a で どの角が ∠x か**を印と名前で示す。
    """
    if relation == "vertical":
        # 2直線 ℓ・m が1点 O で交わる。∠a は上、∠x はその対頂角（下）。
        params: dict[str, Any] = {
            "coords": {
                "O": (0.0, 0.0),
                "A": (3.0, 2.0), "B": (-3.0, -2.0),   # 直線 ℓ
                "C": (-3.0, 2.0), "D": (3.0, -2.0),   # 直線 m
            },
            "segments": [("A", "B"), ("C", "D")],
            "angle_marks": [
                ["O", "A", "C", angle_label],
                ["O", "B", "D", x_label],
            ],
            "free_labels": [["A", "ℓ", 16, -8], ["C", "m", -16, -8]],
            "hidden_points": ["A", "B", "C", "D"],
            "unnamed_points": ["O"],
        }
        return render_construction_svg(params)

    params = _parallel_pair_base("ℓ", "m")
    if relation == "corresponding":
        # 同位角: 直線 n から見て同じ側・同じ位置（どちらも右下）。
        params["angle_marks"] = [
            ["P", "Lb", "Q", angle_label],
            ["Q", "Mb", "Nb", x_label],
        ]
    elif relation == "alternate":
        # 錯角: 直線 n をはさんで反対側（∠a は右下、∠x は左上）。
        params["angle_marks"] = [
            ["P", "Lb", "Q", angle_label],
            ["Q", "Ma", "P", x_label],
        ]
    else:
        raise ValueError(f"未知の関係: {relation!r}")
    return render_construction_svg(params)


def zigzag_angle_svg(a1_label: str, a2_label: str, x_label: str) -> str:
    """平行な2直線のあいだで1回折れ曲がる折れ線の図（g2_l31/l32.find_value Lv2）。

    A は ℓ 上、B は m 上、P が折れ点。∠A は ℓ と線分PA、∠B は m と線分PB がつくる角で、
    どちらも折れ線から見て同じ側にある。求めるのは折れ点の角 ∠APB。
    """
    params: dict[str, Any] = {
        "coords": {
            "A": (1.4, _TOP_Y),
            "B": (1.9, _BOTTOM_Y),
            "P": (-1.6, 0.1),
            "La": (-_HALF_W, _TOP_Y), "Lb": (_HALF_W, _TOP_Y),
            "Ma": (-_HALF_W, _BOTTOM_Y), "Mb": (_HALF_W, _BOTTOM_Y),
        },
        "segments": [("La", "Lb"), ("Ma", "Mb"), ("A", "P"), ("P", "B")],
        "parallel_groups": [[("La", "Lb"), ("Ma", "Mb")]],
        "angle_marks": [
            ["A", "La", "P", a1_label],
            ["B", "Ma", "P", a2_label],
            ["P", "A", "B", x_label],
        ],
        "free_labels": [["Lb", "ℓ", 16, -6], ["Mb", "m", 16, -6]],
        "hidden_points": ["La", "Lb", "Ma", "Mb"],
    }
    return render_construction_svg(params)


# ---------------------------------------------------------------------------
# 三角形の角
# ---------------------------------------------------------------------------
def _triangle_from_angles(
    angle_b: float, angle_c: float, base: float = 4.0
) -> dict[str, tuple[float, float]]:
    """底辺 BC を水平に置き、両端の角から頂点 A を決める。

    **図は与えられた角のとおりに描く。** 教科書の図は厳密な縮尺ではないが、
    「∠B=60° と書いてあるのに図では鈍角」のような食い違いは読み手を迷わせる。
    角から座標を出せば、図と本文が必ず一致する。
    """
    rb, rc = math.radians(angle_b), math.radians(angle_c)
    # B=(0,0), C=(base,0)。A は B から角 rb、C から角 (180-rc) の向きの交点。
    # 正弦定理: BA = base * sin(rc) / sin(rb + rc)
    ba = base * math.sin(rc) / math.sin(rb + rc)
    return {
        "B": (0.0, 0.0),
        "C": (base, 0.0),
        "A": (ba * math.cos(rb), ba * math.sin(rb)),
    }


def triangle_third_angle_svg(
    angle_a: float, angle_b: float, a_label: str, b_label: str, x_label: str
) -> str:
    """三角形の2つの内角がわかっていて、残りの1つを問う図（g2_l33.find_value Lv1）。"""
    angle_c = 180.0 - angle_a - angle_b
    coords = _triangle_from_angles(angle_b, angle_c)
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [("A", "B"), ("B", "C"), ("C", "A")],
        "angle_marks": [
            ["A", "B", "C", a_label],
            ["B", "C", "A", b_label],
            ["C", "A", "B", x_label],
        ],
    }
    return render_construction_svg(params)


def arrowhead_angle_svg(
    angle_a: float, angle_b: float, angle_c: float,
    a_label: str, b_label: str, c_label: str, x_label: str,
) -> str:
    """三角形の内部の点がつくる角（ブーメラン型）の図（g2_l33.find_value Lv2）。

    ∠BAC=angle_a、∠ABD=angle_b、∠ACD=angle_c。残りは ∠DBC と ∠DCB に等分して
    配り、D を2本の半直線の交点として厳密に置く。
    """
    rest = 180.0 - angle_a - angle_b - angle_c

    def build(share: float) -> tuple[dict[str, tuple[float, float]], float]:
        """残りの角を B 側に share、C 側に (1-share) 配ったときの図と、D の高さ。"""
        coords = _triangle_from_angles(angle_b + rest * share, angle_c + rest * (1 - share))
        bx, by = coords["B"]
        cx, cy = coords["C"]
        ax, ay = coords["A"]
        # B から BA の向きを angle_b だけ BC 側へ回した半直線と、
        # C から CA の向きを angle_c だけ CB 側へ回した半直線の交点が D。
        t1 = math.atan2(ay - by, ax - bx) - math.radians(angle_b)
        t2 = math.atan2(ay - cy, ax - cx) + math.radians(angle_c)
        det = math.cos(t1) * math.sin(t2) - math.sin(t1) * math.cos(t2)
        t = ((cx - bx) * math.sin(t2) - (cy - by) * math.cos(t2)) / det
        coords["D"] = (bx + t * math.cos(t1), by + t * math.sin(t1))
        return coords, coords["D"][1] / max(ay, 1e-9)

    # **D が底辺に貼りついた図は読めない。** 残りの角の配り方は自由なので、
    # D が底辺から最も高く浮く配り方を選ぶ（∠BDC の印と名前が底辺に重ならない）。
    coords = max((build(sh) for sh in [i / 20 for i in range(3, 18)]), key=lambda r: r[1])[0]
    params: dict[str, Any] = {
        "coords": coords,
        "segments": [("A", "B"), ("B", "C"), ("C", "A"), ("B", "D"), ("C", "D")],
        "angle_marks": [
            ["A", "B", "C", a_label],
            ["B", "A", "D", b_label],
            ["C", "A", "D", c_label],
            # ∠BDC は180°に近いので、名前は二等分線でなく D の右上に置く
            # （二等分線の先は底辺 BC の上になり、重なって読めない）。
            ["D", "B", "C", x_label, (-44.0, -14.0)],
        ],
    }
    return render_construction_svg(params)


def isosceles_svg(
    v: str, apex: str, base1: str, base2: str,
    apex_angle: float, apex_label: str, base_label: str,
) -> str:
    """二等辺三角形（等しい2辺に印・頂角と底角に名前）（g2_l41.find_value Lv1）。

    `apex` が頂角の頂点、`base1`/`base2` が底角の頂点。`v` は使わない（呼び出し側が
    三角形の名前を作るために持っているだけ）。
    """
    base_angle = (180.0 - apex_angle) / 2
    coords = _triangle_from_angles(base_angle, base_angle)
    # _triangle_from_angles は B・C が底角、A が頂角。名前を差し替える。
    named = {apex: coords["A"], base1: coords["B"], base2: coords["C"]}
    params: dict[str, Any] = {
        "coords": named,
        "segments": [(apex, base1), (base1, base2), (base2, apex)],
        "equal_groups": [[(apex, base1), (apex, base2)]],
        "angle_marks": [
            [apex, base1, base2, apex_label],
            [base1, base2, apex, base_label],
        ],
    }
    return render_construction_svg(params)


__all__ = [
    "angle_equality_svg",
    "arrowhead_angle_svg",
    "isosceles_svg",
    "triangle_third_angle_svg",
    "zigzag_angle_svg",
]
