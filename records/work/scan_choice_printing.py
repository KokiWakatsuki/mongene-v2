"""選択式の問題で、**選択肢が印刷されているか**を全セルで測る。

## なぜ要るか

630セル中163セルが選択式だが、選択肢は `ChoiceAnswer.distractors` の中にしか
無いことが多い。本文が「次のア〜ウから選べ」と言っているのに選択肢が1つも
印刷されていなければ、**印刷物として解答不能**である。

出す4つ:

  printed      本文に正解の文字列が出ている（＝recipe が手で書き込んでいる）
  asks_choice  本文が「選べ／選びなさい」と言っている
  claims_n     本文が「ア〜ウ」等で選択肢の個数を宣言している（実数と突き合わせる）
  prompt_pick  小問の問いが「正しいものを選びなさい。」になっている

実行:
  .venv/bin/python records/work/scan_choice_printing.py [--seeds N]
"""
from __future__ import annotations

import re
import sys

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, family_of, make_env

# 「本文が選択を求めているか」の判定は**レンダラと同じものを使う**。走査側で
# 別に書くと、「標本を選び出す方法を何といいますか」の「選び」を拾って、直って
# いるものを未印刷と数える（実際そうなった）。
from engine.core.render.t1_template import _ASKS_CHOICE_RE as _ASKS_CHOICE  # noqa: E402
# 本文が宣言する選択肢の範囲（「ア〜ウ」「ア～エ」「①〜④」）。
_CLAIMS = re.compile(r"([アイウエオ①②③④⑤])\s*[〜～ー-]\s*([アイウエオ①②③④⑤])")
_KANA = "アイウエオカキ"
_MARU = "①②③④⑤⑥⑦"

_PROMPT_PICK = "正しいものを選びなさい。"


def _claimed_count(text: str) -> int | None:
    m = _CLAIMS.search(text)
    if not m:
        return None
    a, b = m.group(1), m.group(2)
    for seq in (_KANA, _MARU):
        if a in seq and b in seq:
            return seq.index(b) - seq.index(a) + 1
    return None


def main() -> int:
    seeds = 1
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    cells = list(capability_cells(env))
    n_choice_cells = 0
    printed: list[str] = []
    unprinted: list[str] = []
    count_mismatch: list[str] = []
    prompt_only: list[str] = []   # 本文は記述式なのに問いが「選びなさい」
    total_cells = 0

    for coord in cells:
        total_cells += 1
        rows: list[tuple[bool, bool, bool, int, int | None]] = []
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception:  # noqa: BLE001
                continue
            if isinstance(res, Unsupported):
                continue
            for sq in res.sub_questions:
                if getattr(sq.answer, "kind", "") != "choice":
                    continue
                body = res.problem_text
                # **印刷先は本文とはかぎらない。** 選択肢は `prompts` に出す
                # （漏洩ゲート G-Q5t の対象が problem_text と hints だけなので、
                # そこに置くとゲートを緩めずに印刷できる）。本文しか見ない走査は
                # 直した後も「未印刷」を数え続ける——ここはその実例。
                shown = body + "\n" + (sq.prompt_text or "")
                n = 1 + len(sq.answer.distractors)
                rows.append((
                    str(sq.answer.correct) in shown
                    and all(str(d) in shown for d in sq.answer.distractors),
                    bool(_ASKS_CHOICE.search(body)),
                    _PROMPT_PICK in (sq.prompt_text or ""),
                    n,
                    _claimed_count(body),
                ))
        if not rows:
            continue
        n_choice_cells += 1
        name = f"{family_of(coord)}.Lv{coord.level}"
        is_printed = any(r[0] for r in rows)
        asks = any(r[1] for r in rows)
        picks = any(r[2] for r in rows)
        if is_printed:
            printed.append(name)
            for was_printed, _asks, _p, n, claimed in rows:
                if was_printed and claimed is not None and claimed != n:
                    count_mismatch.append(f"{name}: 本文は{claimed}個と言い、実際は{n}個")
                    break
        elif asks:
            unprinted.append(f"{name}（選択肢 {rows[0][3]} 個）")
        elif picks:
            prompt_only.append(name)

    print(f"走査したセル {total_cells}／うち選択式 {n_choice_cells}\n")
    print(f"■ 選択肢が印刷されている            {len(printed)}")
    print(f"■ 本文が「選べ」と言うのに未印刷    {len(unprinted)}  ← 解答不能")
    print(f"■ 本文は記述式なのに問いは「選べ」  {len(prompt_only)}  ← 問いと本文の食い違い")
    print(f"■ 印刷済みだが個数の宣言が合わない  {len(count_mismatch)}\n")
    for title, items in (
        ("未印刷", unprinted), ("問いの食い違い", prompt_only), ("個数の宣言", count_mismatch),
    ):
        if items:
            print(f"--- {title} ---")
            for s in items:
                print(f"  {s}")
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
