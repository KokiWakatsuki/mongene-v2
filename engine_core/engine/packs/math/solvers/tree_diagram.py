"""樹形図に整理する solver（Phase E 端物・g2_l52 / g2_l53 の graph_table Lv1）。

「起こりうる場合をすべて樹形図に表せ」は作図そのものを engine が採点できないので、
**樹形図を読んだ結果である「すべての場合の列」**を答えにする（g2_l52 Lv2 の
「樹形図に表せ」→「全部で何通りか」と同じ手を、列まで答えさせる形に進めたもの）。
答えは GraphAnswer で、features は 場合の列（出現順）＋総数。

場合は itertools で列挙し直す（掛け算の結果を主張せず数える＝double-solve）。
"""
from __future__ import annotations

import itertools

import sympy

from engine.core.contracts import Feature, GraphAnswer, Solution, Step
from engine.core.registry import register_solver

_TREE_OPS = ["list_first_choices", "branch_second_choices", "count_all_paths"]

_TREE_NARRATION: dict[str, str] = {
    "list_first_choices": "1回目に起こりうるものをすべて書き出して、"
                          "はじめの点から枝を分ける。",
    "branch_second_choices": "その枝それぞれの先で、2回目に起こりうるものを"
                             "書き出してさらに枝を分ける。",
    "count_all_paths": "枝の先まで進んだ道すじが1つの場合にあたるので、"
                       "それを順に読み上げて、全部で何通りかを数える。",
}

def _tree_phrase(firsts: list[str], seconds: list[str]) -> dict[str, str]:
    """樹形図の手の括弧（枝そのもの）。指示の言い直しは置かない（面③）。"""
    return {
        "list_first_choices": "、".join(firsts),
        "branch_second_choices": "、".join(seconds),
    }


@register_solver("math.tree_diagram_outcomes")
def tree_diagram_outcomes(items: object, draws: object, replace: object) -> Solution:
    """2回の試行で起こりうる場合をすべて列挙する（樹形図の中身）。

    items: 1回目に起こりうるものの名前の並び（硬貨なら ["表","裏"]、玉なら色の並び）。
    draws: 何回か（このセルは 2 固定だが、将来 3 段にできるよう引数にしておく）。
    replace: True なら毎回同じ選択肢（硬貨を2枚投げる）、False なら**もとに戻さない**
      （玉を続けて取り出す＝1回目に取った玉は2回目には無い）。
    """
    names = [str(v) for v in items]  # type: ignore[union-attr]
    k = int(str(draws))
    with_replacement = str(replace).lower() in ("true", "1", "yes")
    if len(names) < 2 or len(set(names)) != len(names):
        raise ValueError("選択肢は相異なる2つ以上であること")
    if k < 2:
        raise ValueError("樹形図は2段以上であること")
    if not with_replacement and k > len(names):
        raise ValueError("もとに戻さないので、取り出す回数は選択肢の数以下であること")

    if with_replacement:
        tuples = list(itertools.product(names, repeat=k))
    else:
        tuples = list(itertools.permutations(names, k))
    paths = ["-".join(t) for t in tuples]
    total = len(paths)
    if total < 2:
        raise ValueError("場合が1通りしかなく、樹形図に整理する意味がない")

    features = [
        Feature(kind="outcome", srepr=sympy.srepr(sympy.Symbol(p)), display="、".join(p.split("-")))
        for p in paths
    ]
    features.append(
        Feature(kind="total_count", srepr=sympy.srepr(sympy.Integer(total)), display=f"{total}通り")
    )
    disp = f"全部で{total}通り（" + " / ".join(f.display for f in features[:-1]) + "）"
    srepr = sympy.srepr(sympy.Integer(total))
    steps = [
        Step(
            op=op, args=[],
            result_srepr=srepr if i == len(_TREE_OPS) - 1 else "",
            result_display=disp if i == len(_TREE_OPS) - 1
            else _tree_phrase(
                list(dict.fromkeys(t[0] for t in tuples)),
                list(dict.fromkeys(t[1] for t in tuples if len(t) > 1)),
            )[op],
            narration=_TREE_NARRATION[op],
        )
        for i, op in enumerate(_TREE_OPS)
    ]
    return Solution(answer=GraphAnswer(features=features, solution_svg_ref=""), steps=steps)


__all__ = ["tree_diagram_outcomes"]
