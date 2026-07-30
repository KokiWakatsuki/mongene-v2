"""等式・不等式で関係を表す文章題の double_solve checker（G-Q1 が呼ぶ・§6.2）。

4セル（g1_l19/g1_l20 の Lv1・Lv2）を1つの checker が賄う。recipe が
`math.word_problem_relation` 1つに集約されているので、G-Q1 が引く checker 名
（`{recipe}.double_solve`）も1つで足りる。

独立性: params が持つのは**場面文に出ている数値**だけで、答え（関係式）は入って
いない。checker はその数値から `FORMULATION_BUILDERS` で関係式を組み直す。
値を求める小問がない（asked="formulation" の1小問のみ）ので、返す Solution は
常に単体（G-Q1 は `Solution` 単体を「小問数1の list」として扱う）。
"""
from __future__ import annotations

import sympy

from engine.core.contracts import MR, Solution, SymbolicAnswer
from engine.core.registry import register_checker
from engine.packs.math.recipes.word_problem_relation import FORMULATION_BUILDERS, RECIPE_NAME


@register_checker(f"{RECIPE_NAME}.double_solve")
def double_solve_word_problem_relation(mr: MR) -> Solution:
    p = mr.params
    kind = str(p["scenario_kind"])
    numbers = {k: int(sympy.sympify(v)) for k, v in p["numbers"].items()}

    formulation = FORMULATION_BUILDERS[kind](**numbers)
    return Solution(
        answer=SymbolicAnswer(
            srepr=sympy.srepr(formulation.relation), display=formulation.display
        ),
        steps=[],
    )


__all__ = ["double_solve_word_problem_relation"]
