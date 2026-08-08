"""図形の証明セルの double_solve checker（G-Q1・§6.2）。

**独立性の意味がこの form では違う。** 数値の答えを別経路で計算し直すのではなく、
「params の構成パラメータだけから**証明をもう一度探索し直し**、同じ結論・同じ根拠の列に
なるか」を見る。答え（証明文）は params に入っていないので、checker は recipe の
出力を一切見ずに、構成 → 推論 → 結論 → 証明 をやり直す。
"""
from __future__ import annotations

from engine.core.contracts import MR, ProofAnswer, ProofStep, Solution
from engine.core.registry import register_checker
from engine.packs.math.recipes.geometry_proof import TOPICS_CONGRUENCE, build_problem
from engine.packs.math.geometry.render_text import compared_triangles, render_proof


@register_checker("math.geometry_proof.double_solve")
def double_solve_geometry_proof(mr: MR) -> Solution:
    kind = str(mr.params["construction"])
    params = {k: float(v) for k, v in mr.params["numbers"].items()}
    built = build_problem(
        kind, params, level=int(mr.level), topics=TOPICS_CONGRUENCE,
        exclude_rules=tuple(mr.params.get("exclude_rules", ())),
        depth=mr.params.get("proof_depth"),
        prefer=mr.params.get("prefer") or None,
    )
    if built is None:
        raise ValueError("checker: 同じ構成から問題を組み直せなかった")
    _con, ded, goal, lines = built
    text = render_proof(lines, targets=compared_triangles(ded, goal.fact))
    return Solution(
        answer=ProofAnswer(
            text=text,
            lines=[
                ProofStep(
                    claim=line.claim, reason=line.reason, number=line.number,
                    refs=list(line.refs), op=line.op,
                )
                for line in lines
            ],
        ),
        steps=[],
    )
