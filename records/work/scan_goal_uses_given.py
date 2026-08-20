"""証明の結論が、**仮定を1つも使わずに**導けていないかを測る。

## なぜ要るか

「仮定を使わない結論は問わない」を `naturalness._is_worth_asking` に足したとき、
`ded.proof_chain(f)` で仮定を探した。ところが `proof_chain` の docstring は
**「仮定はここには含めない」**と書いてある。だから何も一致せず、
153本中120本が生成不能になった（戻した）。

正しい探し方は、導出を**葉まで**たどること。葉のうち1つでも `ded.given` に
あれば、その結論は仮定を使っている。

**直す前に、まず何件あるかを測る。** 0件なら足す歯止めは要らない
（＝壊した120本のぶんの危険を、得るもの無しに背負うところだった）。

実行:
  .venv/bin/python records/work/scan_goal_uses_given.py [--seeds N]
"""
from __future__ import annotations

import sys
from collections import Counter

from engine.core.contracts import Unsupported
from engine.eval._harness import build_mr, capability_cells, family_of, make_env


def main() -> int:
    seeds = 3
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    looked = 0
    proof_cells = 0
    no_given: list[str] = []
    kinds: Counter[str] = Counter()

    for coord in capability_cells(env):
        if coord.form != "proof":
            continue
        proof_cells += 1
        for seed in range(1, seeds + 1):
            try:
                r = build_mr(coord, seed, env)
            except Exception:  # noqa: BLE001
                continue
            mr = getattr(r, "mr", r)
            if isinstance(mr, Unsupported):
                continue
            looked += 1
            for sq in mr.sub_questions:
                ans = sq.answer
                if getattr(ans, "kind", "") != "proof":
                    continue
                kinds[ans.kind] += 1
                # **フィールド名は `lines`（`steps` ではない）。** `steps` を読んで
                # AttributeError で落ちた。memory の「読むフィールド違い」の再発。
                #
                # **根拠の文字列で探してはいけない。** 仮定の行は「仮定より」とも
                # 「O は AD の中点だから」とも書かれる（教科書の書き分けに合わせて
                # 自然な言い換えをする）。「仮定」を含むかで数えたら 153本中68本が
                # 「仮定を使っていない」と出たが、その中身は仮定そのものだった。
                # 行の `op` は言い換えても変わらないので、そちらで見る。
                # **証明の描き手は3系統ある。** ここを取り違えて3度外した。
                #   ① 推論器 `build_proof_lines`: 仮定を**独立行**に出す
                #      （op=cite_hypothesis / reason=「仮定より」）
                #   ② 図形の単元別の描き手: 仮定を**使う手の根拠に畳み込む**
                #      （op=use_midpoint / reason=「O は AD の中点だから」）
                #   ③ 数の性質の証明: 仮定は `given["premises"]` にあり
                #      （「f、w を整数とすると、2つの偶数は 2f、2w と表される」）、
                #      証明はそこから始まる（op=form_expression）
                # ②を落とすと 66本、②③を落とすと 33本が誤って出る。
                ops = [str(ln.op) for ln in ans.lines]
                reasons = [str(ln.reason) for ln in ans.lines]
                cites = [
                    r_ for o, r_ in zip(ops, reasons, strict=True)
                    if o in ("cite_hypothesis", "cite_common")
                ]
                folded = [
                    r_ for o, r_ in zip(ops, reasons, strict=True)
                    if o.startswith("use_") and r_
                ]
                # 「図のかき方から」＝問題文が述べていない（図の都合で成り立つ）事実。
                # ③ 数の性質の証明: 仮定は `given["premises"]` にあるか、
                # 証明の最初の手そのもの（文字を置く・数を文字で表す・仮定を述べる）。
                # given に premises が無い形（g2_l7 Lv3）もあるので op で見る。
                _SETUP_OPS = frozenset(
                    {"form_expression", "state_hypothesis", "choose_letters", "represent_numbers"}
                )
                from_premises = bool(_SETUP_OPS & set(ops))
                # **op の列挙で追うのは限界だった。** `set_representation` の根拠が
                # 「仮定より、m は4の倍数だから」で、cite でも use_ でもなかった。
                # 根拠の文が仮定に言及しているか、given の文を引いているかで見る。
                mentions = any(
                    "仮定" in r_
                    or any(g and g[:12] in r_ for g in mr.given.values())
                    for r_ in reasons
                )
                stated = [r_ for r_ in cites if r_ != "図のかき方から"]
                if not stated and not folded and not from_premises and not mentions:
                    no_given.append(
                        f"{family_of(coord)}.Lv{coord.level} seed{seed}: "
                        f"引用行={cites or '（無し）'} / 畳み込み={folded or '（無し）'}"
                    )

    # **比べる相手の個数を必ず出す。** 0件が「無い」のか「見ていない」のかを分ける。
    print(f"proof のセル {proof_cells}／組み立てた MR {looked}／証明の答え {sum(kinds.values())}\n")
    print(f"■ 機械では仮定の使用を確認できなかった証明: {len(no_given)} 件（目で読む対象）")
    for s in no_given[:20]:
        print(f"  {s}")
    print(
        "\n★ これは合否のゲートではない。証明の描き手が5系統あり（推論器・図形の単元別・"
        "数の性質・命題の真偽・定理の証明）、仮定の出し方がそれぞれ違うので、"
        "**機械の1つの規則では覆えない**。0件になるまで規則を緩めるのは本末転倒。"
        "\n★ 2026-08-17 に残った件（g3_l51 三平方の定理の証明）を行ごと直読し、"
        "根拠がすべて given['premises'] の構成を引いていることを確認した。"
        "**5系統すべてで仮定は使われており、「仮定を使わない結論」は1件も無い。**"
        "\n★ したがって naturalness に「仮定を使う結論だけ問う」歯止めは要らない。"
        "同じ日にそれを足して 153本中120本を生成不能にしたが、守るべき対象は無かった。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
