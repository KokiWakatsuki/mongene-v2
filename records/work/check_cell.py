"""1セルの DoD 検証スニペット（HANDOFF 13c §4 / 12 §5-#8 由来を再作成）。

用途: 指定した (unit, form, Lv...) の各レベルを
  1. 120-seed でフル gate（generate 経路・Q ゲート込み）を通し拒否数を数える
  2. cell_dup_rate を 100-seed 実測（閾 0.20）
一発で見る。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/check_cell.py <unit> <form> <lv,lv,...>
例:
  PYTHONPATH=engine_core .venv/bin/python records/work/check_cell.py g1_l23 calculation 3
  PYTHONPATH=engine_core .venv/bin/python records/work/check_cell.py g1_l24 calculation 1,2
"""
from __future__ import annotations

import sys

from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env
from engine.eval.dup_rate import cell_dup_rate
from engine.eval.text_quality import cell_text_quality

_GATE_SEEDS = 120
_DUP_SEEDS = 100
# eval の既定は 5。速い確認では多めに見る（点名は seed ごとに変わる）。
_TQ_SEEDS = 12
_DUP_THRESHOLD = 0.20  # family YAML の dup_rate_max があればそちらが優先される


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: check_cell.py <unit> <form> <lv,lv,...>")
        return 2
    unit, form, levels_s = sys.argv[1], sys.argv[2], sys.argv[3]
    levels = [int(x) for x in levels_s.split(",")]

    env = make_env()
    all_ok = True
    for lv in levels:
        coord = Coordinate(subject="math", unit=unit, form=form, level=lv)
        # 1) フル gate 拒否数
        rejects: list[str] = []
        sample_shown = False
        for seed in range(1, _GATE_SEEDS + 1):
            req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
            res = generate(
                req,
                curriculum=env.curriculum,
                families=env.families,
                registry=env.registry,
            )
            if isinstance(res, Unsupported):
                rejects.append(f"seed{seed}:{res.code}:{res.detail}")
            elif not sample_shown:
                sample_shown = True
                sq = res.sub_questions[0]
                ans = sq.answer
                ans_repr = getattr(ans, "display", None) or getattr(ans, "correct", ans)
                print(f"\n--- {unit}.{form}.Lv{lv} sample (seed{seed}) ---")
                print(f"  prompt : {sq.prompt_text!r}")
                print(f"  answer : {ans_repr!r}")
                # **生徒が読むものをそのまま出す。** 以前はここが `st.narration`
                # だったので、解説にしか出ない `Step.detail` が見えず、
                # 「直したのに変わっていない」と読み違える口になっていた。
                for line in str(sq.explanation).splitlines():
                    print(f"    解説 {line}")
                for hint in sq.hints:
                    print(f"    ヒント {hint}")
                for st in sq.solution_steps:
                    print(f"      step[{st.op}] {st.result_display!r}")
        # 2) dup_rate @100
        dr = cell_dup_rate(env, coord, _DUP_SEEDS, _DUP_THRESHOLD)

        # 3) text_quality（記号の食い違い）
        #
        # **ここが無いと、速い確認が素通りさせる種類がある。** 解説の括弧に
        # 実物の点名を書き写して `KW²`・`X(-10/a, 0)`・`EG : OE` と入れたら、
        # rejects も dup も通ったまま eval の text_quality だけが落ちた
        # （問題文が点に名前をつけていないので「問題文に無い記号」になる）。
        # 検査ごとに見ている面が違う——速い側に無い面は、19分の全走まで見えない。
        tq = cell_text_quality(env, coord, _TQ_SEEDS)

        gate_ok = len(rejects) == 0
        dup_ok = dr.ok
        tq_ok = not (tq.stray_symbols or tq.empty_hint)
        mark = "OK" if (gate_ok and dup_ok and tq_ok) else "FAIL"
        print(f"\n[{mark}] {unit}.{form}.Lv{lv}")
        print(f"  gate: rejects={len(rejects)}/{_GATE_SEEDS}")
        print(
            f"  text_quality: 問題文に無い記号={''.join(tq.stray_symbols) or 'なし'}"
            f" / 中身のないヒント={'あり' if tq.empty_hint else 'なし'}"
        )
        for s in tq.stray_samples[:3]:
            print(f"    ! {s}")
        for r in rejects[:5]:
            print(f"    ! {r}")
        print(
            f"  dup_rate={dr.dup_rate} (distinct {dr.distinct_dup_keys}/{dr.generated})"
            f" fps={dr.distinct_fps} over_threshold={dr.over_threshold}"
            f" build_failures={len(dr.build_failures)}"
        )
        for bf in dr.build_failures[:3]:
            print(f"    ! build_fail {bf}")
        if not (gate_ok and dup_ok and tq_ok):
            all_ok = False

    print(f"\n=== {'ALL_OK' if all_ok else 'SOME_FAIL'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
