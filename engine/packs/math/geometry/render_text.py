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

# 図の構造そのもの（点が一直線に並んでいる・円周上にある等）は、教科書では仮定の行に
# 書かない。図を見れば分かることなので、番号を振って引用すると証明が冗長になる。
# （「弧BCに対する円周角は等しいから ∠BAC＝∠BDC」と書くのであって、その前に
# 「点Aと点Dは弦BCについて同じ側の弧の上にある …①」の行は立てない。）
_STRUCTURAL_KINDS = frozenset({"collinear", "parallel_dir", "on_circle", "same_arc"})


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
    # 「定義を開くだけ」の行は、その前提（仮定）と1行にまとめる。
    folded: dict[Fact, Fact] = {}
    for f in chain:
        rule = ded.rule_of(f)
        if rule is not None and rule.definitional and len(ded.premises_of(f)) == 1:
            premise = ded.premises_of(f)[0]
            if ded.rule_of(premise) is None:
                folded[f] = premise

    used_given: list[Fact] = []
    for f in chain:
        for p in ded.premises_of(f):
            if ded.rule_of(p) is not None or p.kind in _STRUCTURAL_KINDS:
                continue
            if p in folded.values():
                continue  # 畳んだ行の中に書くので、単独の仮定の行にはしない
            if p not in used_given:
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
        # 定義を開く行は「（仮定）だから　（結論）」の1行にする。
        reason = f"{fact_text(folded[f])}だから" if f in folded else rule.reason
        lines.append(
            ProofLine(
                claim=fact_text(f),
                reason=reason,
                number=None if is_goal else n,
                refs=() if f in folded else refs,
                op=rule.name,
            )
        )
    return lines


def compared_triangles(ded: Deduction, goal: Fact) -> tuple[tuple[str, ...], ...]:
    """証明の冒頭に書く「△… と △… において」の2三角形を、導出から決める。

    目標が合同そのものでなくても（「∠BAC＝∠CAD を示せ」でも）、証明は三角形を
    比べるところから始まる。**証明の中で最初に出てくる合同**の2三角形を見出しにする
    ——教科書がそう書いている。合同を経由しない証明なら見出しは付けない。
    """
    for f in ded.proof_chain(goal):
        if f.kind == "tri_cong":
            return f.args
    if goal.kind == "tri_cong":
        return goal.args
    return ()


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
            # 番号を引かない行は「〜から　主張」と書く（「対頂角は等しい　∠…」だと
            # 文がつながらない）。「仮定より」「〜だから」は既に接続の形になっている。
            reason = line.reason
            if reason != "仮定より" and not reason.endswith("だから"):
                reason += "から"
            out.append(f"　　{reason}　　{line.claim}{tail}")
        else:
            out.append(f"　　{line.claim}{tail}")
    return "\n".join(out)


__all__ = ["ProofLine", "build_proof_lines", "compared_triangles", "render_proof"]
