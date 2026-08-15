"""word_problem の不変条件: params の数値は必ず問題文に出ている数である。

由来（セッション #104/#105 で実バグとして踏んだ）: 食塩水セルの初稿が params に
**本文に出ていない導出値**（食塩の重さ S = c·W/100）を置いていた。こうすると
「本文の濃度 c を書き間違えても checker が S を見て正解を出す」＝場面文と検証が
切り離された穴ができる。params に置くのは「本文に現れる数」だけにし、導出は
builder 側で行う、というのが文章題セルの設計契約である。

この契約は 1 セルずつ手で書いた assert では守り切れない（新セルが増えるたびに
書き忘れる）。ここでは **capabilities() を走査して word_problem の全セルに対して
機械的に**検査する＝新セルを追加すると自動で被覆される。

例外は `_NO_NUMBERS_KEY_CELLS` に明示列挙する（暗黙のすり抜けを作らないため）。

`numbers` が**空**のセル（数値をすべて図が与える＝本文に算用数字が無い文章題。
C11 g2_l57 の箱ひげ図がこれ）は、本文に算用数字が 1 つも無いことを併せて検査する。
そうしないと「numbers を空にすれば本文の数値が検査されない」抜け道になる。
"""
from __future__ import annotations

import re

import sympy

from engine.bootstrap import bootstrap
from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import capabilities, generate
from engine.eval._harness import build_mr, make_env

_SEEDS = 8

# params["numbers"] という形を持たない（先行実装で個別の params 構造を持つ）セル。
# 新セルは必ず numbers 形にすること＝ここに足すのではなく recipe 側を直す。
_NO_NUMBERS_KEY_CELLS: frozenset[tuple[str, int]] = frozenset({("g2_l16", 2)})

# **語で書かれている値**は、算用数字としては本文に現れない（それでも読者には見えている）。
#   faces      … 「大小2個のさいころ」＝6面（「1から6までの目が出る」とは書かない）
#   condition  … 「和が○以上になる」「積が○になる」（"sum_at_least" は符号）
# どちらも答えを漏らす値ではない（条件が分かっても数え上げは要る）。
_WORD_ENCODED_KEYS: frozenset[str] = frozenset({"faces", "condition"})


def test_word_problem_params_numbers_all_appear_in_problem_text() -> None:
    bootstrap()
    env = make_env()
    cells = sorted(
        (c for c in capabilities() if c.form == "word_problem"),
        key=lambda c: (c.unit, c.level),
    )
    assert cells, "word_problem のセルが 1 つも無い（capabilities の走査が壊れている）"

    violations: list[str] = []
    unnecessary_exemptions = set(_NO_NUMBERS_KEY_CELLS)
    for cell in cells:
        coord = Coordinate(subject="math", unit=cell.unit, form=cell.form, level=cell.level)
        for seed in range(1, _SEEDS + 1):
            built = build_mr(coord, seed, env)
            if built.mr is None:
                continue
            numbers = built.mr.params.get("numbers")
            if not isinstance(numbers, dict):
                if (cell.unit, cell.level) in _NO_NUMBERS_KEY_CELLS:
                    unnecessary_exemptions.discard((cell.unit, cell.level))
                    break
                violations.append(
                    f"{cell.unit}.Lv{cell.level}: params に numbers dict が無い"
                    f"（keys={sorted(built.mr.params)}）"
                )
                break
            result = generate(
                GenerateRequest(
                    subject="math",
                    unit=cell.unit,
                    form=cell.form,
                    level=cell.level,
                    seed=seed,
                ),
                curriculum=env.curriculum,
                families=env.families,
                registry=env.registry,
            )
            if isinstance(result, Unsupported):
                continue
            text = result.problem_text + " " + " ".join(
                sq.prompt_text for sq in result.sub_questions
            )
            if not numbers:
                # 数値をすべて図が与えるセル。本文に算用数字があれば「numbers を空に
                # して検査を素通りさせた」ことになるので違反として落とす。
                # "(1)" "(2)" は小問の通し番号（場面の数値ではない）なので除く。
                digits = sorted(set(re.findall(r"\d", re.sub(r"\(\d+\)", "", text))))
                if digits:
                    violations.append(
                        f"{cell.unit}.Lv{cell.level} seed{seed}: params['numbers'] が空なのに "
                        f"本文に算用数字 {digits} がある"
                        f"（本文に出る数は必ず numbers に置くこと）"
                    )
                    break
                continue
            missing = [
                f"{name}={sympy.sympify(value)}"
                for name, value in numbers.items()
                if name not in _WORD_ENCODED_KEYS and str(sympy.sympify(value)) not in text
            ]
            if missing:
                violations.append(
                    f"{cell.unit}.Lv{cell.level} seed{seed}: 本文に現れない params 数値 "
                    f"{missing}（導出値は params に置かず builder 側で導くこと）"
                )
                break

    assert not violations, "word_problem の params 忠実性違反:\n" + "\n".join(violations)
    assert not unnecessary_exemptions, (
        f"不要になった例外がある（_NO_NUMBERS_KEY_CELLS から削除せよ）: "
        f"{sorted(unnecessary_exemptions)}"
    )
