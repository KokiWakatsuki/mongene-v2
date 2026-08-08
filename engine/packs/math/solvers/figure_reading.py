"""図の中の要素を記号で答える solver（Phase E 端物・graph_table Lv1 の3セル）。

g1_l37（点と直線の距離を表す線分）・g2_l32（平行な直線）・g2_l44（斜辺と直角をはさむ2辺）は
単元がばらばらだが、**問い方が同じ**（図を見て、その中の要素を記号で選ぶ＝ChoiceAnswer）
で、frame の `read_figure_element` と `visuals/plane_figure.py` を共有する。
単元別のモジュールに散らすと同じ設計判断が3か所に分かれるので、ここにまとめる。

どれも「答えは図の中の名前」なので、**選択肢は必ず図に描かれている要素で作る**
（図に無いものを混ぜると、消去法で解けてしまう）。
"""
from __future__ import annotations

from engine.core.contracts import ChoiceAnswer, Solution, Step
from engine.core.registry import register_solver


def _steps(pairs: list[tuple[str, str, str]], final: str) -> list[Step]:
    """(op, narration, phrase) の並びから Step を作る（最後の手だけ答えを持つ）。"""
    return [
        Step(
            op=op, args=[], result_srepr="",
            result_display=final if i == len(pairs) - 1 else phrase,
            narration=narration,
        )
        for i, (op, narration, phrase) in enumerate(pairs)
    ]


@register_solver("math.identify_distance_segment")
def identify_distance_segment(
    point: object, foot: object, left: object, right: object
) -> Solution:
    """点と直線の距離を表す線分を選ぶ（g1_l37.graph_table Lv1）。

    点と直線の距離は**垂線の長さ**なので、答えは点と垂線の足を結ぶ線分。
    妨害は図に描かれている他の線分（点と直線上の他の2点を結ぶ線分、直線上の2点を
    結ぶ線分）——どれも図にあるので、消去法ではなく定義で選ぶ必要がある。
    """
    p, h, a, b = (str(v) for v in (point, foot, left, right))
    if len({p, h, a, b}) != 4:
        raise ValueError("点名が重複している")
    correct = f"線分{p}{h}"
    distractors = [f"線分{p}{a}", f"線分{p}{b}", f"線分{a}{b}"]
    steps = _steps(
        [
            (
                "recall_distance_definition",
                "点と直線の距離は、その点から直線に引いた垂線の長さであることを思い出す。",
                "距離の定義を思い出す",
            ),
            (
                "identify_perpendicular_segment",
                "図の中で垂線にあたるのは、点と垂線の足を結ぶ線分だから、それを選ぶ。",
                "",
            ),
        ],
        correct,
    )
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=distractors, fact_id="line_angle_terms.point_line_distance"
        ),
        steps=steps,
    )


@register_solver("math.identify_parallel_line")
def identify_parallel_line(
    base_angle: object, names: object, angles: object
) -> Solution:
    """横断線となす角が等しい直線（＝基準の直線と平行な直線）を選ぶ（g2_l32.graph_table Lv1）。

    同位角が等しいならば2直線は平行、という条件そのもの。角が一致する候補が
    ちょうど1本であることを検査する（複数あると答えが定まらない）。
    """
    base = float(str(base_angle))
    name_list = [str(v) for v in names]  # type: ignore[union-attr]
    angle_list = [float(str(v)) for v in angles]  # type: ignore[union-attr]
    if len(name_list) != len(angle_list) or len(name_list) < 2:
        raise ValueError("候補の直線と角の数が合わない")
    matched = [n for n, a in zip(name_list, angle_list, strict=True) if a == base]
    if len(matched) != 1:
        raise ValueError(f"角が一致する候補が1本でない: {matched}")
    correct = f"直線{matched[0]}"
    distractors = [f"直線{n}" for n in name_list if n != matched[0]]
    steps = _steps(
        [
            (
                "read_angles_with_transversal",
                "それぞれの直線が横断線となす角を図から読み取る。",
                "図から角を読む",
            ),
            (
                "compare_corresponding_angles",
                "同位角が等しいとき2直線は平行になるので、基準の直線と同じ大きさの角を"
                "つくっている直線を選ぶ。",
                "",
            ),
        ],
        correct,
    )
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=distractors, fact_id="parallel_lines.identify_parallel"
        ),
        steps=steps,
    )


@register_solver("math.identify_right_triangle_sides")
def identify_right_triangle_sides(labels: object, right_index: object) -> Solution:
    """直角三角形の斜辺と、直角をはさむ2辺を記号で答える（g2_l44.graph_table Lv1）。

    斜辺は直角の向かい側の辺＝直角の頂点をふくまない辺。妨害は「斜辺の取り違え」
    （直角をはさむ辺のどちらかを斜辺と答える）——直角三角形の合同条件で実際に
    起きる誤りをそのまま選択肢にする。
    """
    names = [str(v) for v in labels]  # type: ignore[union-attr]
    idx = int(str(right_index))
    if len(names) != 3 or len(set(names)) != 3:
        raise ValueError("頂点名は相異なる3つであること")
    if idx not in (0, 1, 2):
        raise ValueError("直角の頂点の位置が不正")
    right = names[idx]
    others = [n for i, n in enumerate(names) if i != idx]
    hypotenuse = f"{others[0]}{others[1]}"
    leg_1, leg_2 = f"{right}{others[0]}", f"{right}{others[1]}"
    correct = f"斜辺は辺{hypotenuse}、直角をはさむ2辺は辺{leg_1}と辺{leg_2}"
    distractors = [
        f"斜辺は辺{leg_1}、直角をはさむ2辺は辺{hypotenuse}と辺{leg_2}",
        f"斜辺は辺{leg_2}、直角をはさむ2辺は辺{hypotenuse}と辺{leg_1}",
    ]
    steps = _steps(
        [
            (
                "locate_right_angle",
                "図の直角の記号から、どの頂点が直角かを確かめる。",
                "直角の頂点を見つける",
            ),
            (
                "identify_hypotenuse_and_legs",
                "斜辺は直角の向かい側の辺だから、直角の頂点をふくまない辺が斜辺で、"
                "残りの2辺が直角をはさむ辺になる。",
                "",
            ),
        ],
        correct,
    )
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=distractors,
            fact_id="right_triangle_congruence.hypotenuse_and_legs",
        ),
        steps=steps,
    )


__all__ = [
    "identify_distance_segment",
    "identify_parallel_line",
    "identify_right_triangle_sides",
]
