"""pythagoras_proof.py の solver を直接叩いて、出来上がりの質を見る。"""
import sys

from engine.packs.math.solvers.pythagoras_proof import (
    AREA_PROOF_IDS,
    CONVERSE_NAME_SETS,
    TRIPLES,
    FigureNames,
    area_proof_lines,
    build_area_proof,
    build_converse_case,
    converse_proof_lines,
    render_proof_text,
)

print(f"面積証明の型: {AREA_PROOF_IDS}")
print(f"ピタゴラス数: {len(TRIPLES)} 通り  例 {TRIPLES[:6]}")
print()

for pid in AREA_PROOF_IDS:
    for guided in (True, False):
        names = FigureNames(outer="ABCD", inner="EFGH") if guided else None
        proof = build_area_proof(pid, ("a", "b", "c"), names, flip=False)
        tag = "誘導あり" if guided else "誘導なし"
        if proof is None:
            print(f"### {pid} / {tag}  -> None（組めない）")
            continue
        lines = area_proof_lines(proof, guided)
        print(f"### {pid} / {tag}   figure_kind={proof.figure_kind}")
        print(f"  配置: {proof.arrangement}")
        print(f"  ops : {[ln.op for ln in lines]}")
        print(render_proof_text(lines))
        print()

print("=" * 60)
for ctx in ("triangle", "quadrilateral", "field"):
    case = build_converse_case(ctx, CONVERSE_NAME_SETS[0], 0, False, 0)
    assert case is not None
    print(f"### 逆 / {ctx}")
    print(f"  仮定: {case.premises}")
    print(f"  結論: {case.conclusion}")
    print(render_proof_text(converse_proof_lines(case)))
    print()
