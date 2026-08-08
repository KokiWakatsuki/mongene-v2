"""導出 →（主張, 根拠）の列 → 証明文（docs/proof_engine_design_2026-08-08.md §5）。

**LLM は使わない。** 証明文は市販の問題集・入試の模範解答が例外なく同じ型で書かれて
いる定型文で、テンプレートのほうが型が安定して質が高い（LLM を挟むと言い回しが揺れ、
番号の付け方が崩れ、採点する側にとっても害になる）。

出力の型（教科書の型そのまま）:

    （証明）△ABC と △ADC において
        仮定より　　AB ＝ AD　…①
        仮定より　　BC ＝ DC　…②
        AC は共通　…③
        ①、②、③より、3組の辺がそれぞれ等しいので
        △ABC ≡ △ADC
"""
from __future__ import annotations

from dataclasses import dataclass

from engine.packs.math.geometry.deduce import Deduction
from engine.packs.math.geometry.facts import (
    Fact,
    fact_text,
    is_common_segment,
    tri_text,
)


@dataclass(frozen=True)
class ProofLine:
    """証明文の1行 ＝（主張, 根拠, 番号）。

    `reason` は規則カタログの `reason` か、仮定の行なら「仮定より」など。
    `refs` はこの行が引く先行行の番号（①②③）。
    """

    claim: str
    reason: str
    number: int | None
    refs: tuple[int, ...] = ()
    op: str = ""  # 規則名（op 列＝level_sep の材料になる）


_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


def _num(n: int) -> str:
    return _CIRCLED[n - 1] if 1 <= n <= len(_CIRCLED) else f"({n})"


def build_proof_lines(
    ded: Deduction,
    goal: Fact,
    *,
    common_facts: frozenset[Fact] = frozenset(),
) -> list[ProofLine]:
    """導出から証明の行を組む。

    `common_facts` は「共通だから」と書くべき仮定（対角線を共有する等）。ふつうの仮定は
    「仮定より」になるので、根拠の言い方をここで分ける——教科書がそう書き分けている。
    """
    chain = ded.proof_chain(goal)
    used_given: list[Fact] = []
    for f in chain:
        for p in ded.premises_of(f):
            if ded.rule_of(p) is None and p not in used_given:
                used_given.append(p)

    lines: list[ProofLine] = []
    number_of: dict[Fact, int] = {}
    n = 0
    for f in used_given:
        n += 1
        number_of[f] = n
        # 「AC は共通」は主張の中に根拠が入っているので、根拠欄を空にする
        # （「共通　AC は共通」と二重に書かない）。
        common = is_common_segment(f) or f in common_facts
        lines.append(
            ProofLine(
                claim=fact_text(f),
                reason="" if is_common_segment(f) else ("共通だから" if common else "仮定より"),
                number=n,
                op="cite_common" if common else "cite_hypothesis",
            )
        )
    for f in chain:
        rule = ded.rule_of(f)
        assert rule is not None
        refs = tuple(number_of[p] for p in ded.premises_of(f) if p in number_of)
        is_goal = f == goal
        if not is_goal:
            n += 1
            number_of[f] = n
        lines.append(
            ProofLine(
                claim=fact_text(f),
                reason=rule.reason,
                number=None if is_goal else n,
                refs=refs,
                op=rule.name,
            )
        )
    return lines


def render_proof(lines: list[ProofLine], *, targets: tuple[tuple[str, ...], ...] = ()) -> str:
    """行の並びを証明文にする。`targets` は冒頭の「△ABC と △ADC において」の2三角形。"""
    out: list[str] = []
    head = "（証明）"
    if targets:
        head += " と ".join(tri_text(t) for t in targets) + " において"
    out.append(head)
    for line in lines:
        tail = f"　…{_num(line.number)}" if line.number is not None else ""
        if line.refs:
            refs = "、".join(_num(r) for r in line.refs)
            out.append(f"　　{refs}より、{line.reason}ので")
            out.append(f"　　　{line.claim}{tail}")
        elif line.reason:
            out.append(f"　　{line.reason}　　{line.claim}{tail}")
        else:
            out.append(f"　　{line.claim}{tail}")
    return "\n".join(out)


__all__ = ["ProofLine", "build_proof_lines", "render_proof"]
