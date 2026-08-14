"""命題の逆と反例の solver（Phase E 端物・g2_l38.knowledge Lv2）。

台帳 Lv2 は「命題から仮定/結論を取り出し、逆や反例を判別・提示する」で、
(1) 逆を判別する (2) その逆が正しくないことを示す反例を提示する、の2段。
どちらも **ChoiceAnswer**（選択）にして採点可能にする——「逆の文を書け」「反例を挙げよ」
という記述は engine が採点できないが、**候補から選ばせれば判別も提示も同じ操作**になる。

命題は数値をパラメータに持つ型（テンプレート）で作る。**命題を数個カタログに並べる
だけでは組合せ数が足りず dup が通らない**（既知の罠）ので、数値と変数名を動かして
変種を作る。どの型も「もとの命題は正しく、逆は正しくない」ようにパラメータを縛る
——そうでないと (2) の反例が存在しない。
"""
from __future__ import annotations

from engine.core.contracts import ChoiceAnswer, Solution, Step
from engine.core.registry import register_solver

# 命題の型。それぞれ「仮定」「結論」を日本語で組み立てる関数を持つ。
#   multiple : n が {a} の倍数ならば n は {b} の倍数（a = b·k・逆は偽）
#   greater  : x > {a} ならば x > {b}（a > b・逆は偽）
#   positive : {v} > 0 かつ {w} > 0 ならば {v}+{w} > 0（逆は偽）
_KINDS = ("multiple", "greater", "positive")


def _parts(kind: str, var: str, a: int, b: int) -> tuple[str, str]:
    """(仮定, 結論) の日本語。どちらも「…である」で終える（否定形を機械的に作るため）。"""
    if kind == "multiple":
        return f"{var}が{a}の倍数である", f"{var}が{b}の倍数である"
    if kind == "greater":
        return f"{var}>{a}である", f"{var}>{b}である"
    return f"{var}>0かつ{var}'>0である", f"{var}+{var}'>0である"


def _negate(clause: str) -> str:
    """「…である」→「…でない」。裏・対偶を作るのに使う。

    素朴に「ない」を付けると「…であるない」になって日本語が壊れる（実際に踏んだ）。
    仮定・結論はすべて「である」で終わる形にそろえてあるので、そこだけを差し替える。
    """
    if not clause.endswith("である"):
        raise ValueError(f"否定形を作れない形の文: {clause!r}")
    return clause[: -len("である")] + "でない"


def _statement(hypothesis: str, conclusion: str) -> str:
    return f"{hypothesis}ならば、{conclusion}"


@register_solver("math.proposition_converse_choice")
def proposition_converse_choice(kind: object, var: object, a: object, b: object) -> Solution:
    """命題の逆として正しいものを選ぶ（g2_l38.knowledge Lv2 の (1)）。

    妨害は **裏**（両方を否定した文）・**対偶**（否定して入れかえた文）・**もとの命題**。
    「逆＝仮定と結論を入れかえた文」を、似た形の3つと区別できるかを見る。
    """
    k, v = str(kind), str(var)
    ai, bi = int(str(a)), int(str(b))
    hypothesis, conclusion = _parts(k, v, ai, bi)
    correct = _statement(conclusion, hypothesis)
    distractors = [
        _statement(_negate(hypothesis), _negate(conclusion)),   # 裏
        _statement(_negate(conclusion), _negate(hypothesis)),   # 対偶
        _statement(hypothesis, conclusion),                      # もとの命題
    ]
    if correct in distractors:
        raise ValueError("逆と同じ文が妨害に混ざっている")
    steps = [
        Step(
            op="extract_hypothesis_and_conclusion", args=[], result_srepr="",
            result_display="仮定と結論を取り出す",
            narration="「…ならば…」の形の文で、「ならば」の前が仮定、後ろが結論であることを"
                      "確かめて、それぞれを取り出す。",
        ),
        Step(
            op="swap_for_converse", args=[], result_srepr="", result_display=correct,
            narration="逆は、仮定と結論を入れかえた文だから、取り出した2つを入れかえて作る。",
        ),
    ]
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=distractors, fact_id="proof_logic.converse_of_proposition"
        ),
        steps=steps,
    )


@register_solver("math.proposition_counterexample_choice")
def proposition_counterexample_choice(
    kind: object, var: object, a: object, b: object
) -> Solution:
    """逆が正しくないことを示す反例を選ぶ（g2_l38.knowledge Lv2 の (2)）。

    反例＝**逆の仮定を満たすが、逆の結論を満たさない**例。妨害は
      ・逆の仮定も結論も満たす例（反例になっていない＝いちばん多い誤り）
      ・逆の仮定を満たさない例（そもそも当てはまらない）
    の2種類にする。どれが反例かは、solver 側で条件を実際に判定して決める
    （日本語の見た目ではなく、数の性質で選ぶ）。
    """
    k, v = str(kind), str(var)
    ai, bi = int(str(a)), int(str(b))

    if k == "multiple":
        # 逆:「b の倍数ならば a の倍数」。反例＝b の倍数だが a の倍数でない数。
        hyp = lambda n: n % bi == 0          # noqa: E731 - 判定はこの関数だけに閉じる
        con = lambda n: n % ai == 0          # noqa: E731
        counter = next(n for n in range(bi, bi * ai + 1) if hyp(n) and not con(n))
        satisfies_both = ai
        fails_hypothesis = next(n for n in range(2, bi * ai) if not hyp(n))
        fmt = lambda n: f"{v}={n}"           # noqa: E731
    elif k == "greater":
        # 逆:「x>b ならば x>a」（a>b）。反例＝b より大きく a 以下の数。
        hyp = lambda n: n > bi               # noqa: E731
        con = lambda n: n > ai               # noqa: E731
        counter = bi + 1
        satisfies_both = ai + 1
        fails_hypothesis = bi
        fmt = lambda n: f"{v}={n}"           # noqa: E731
    else:
        # 逆:「v+v'>0 ならば v>0 かつ v'>0」。反例＝和は正だが一方が負の組。
        hyp = lambda pair: pair[0] + pair[1] > 0            # noqa: E731
        con = lambda pair: pair[0] > 0 and pair[1] > 0      # noqa: E731
        counter = (-ai, ai + bi)
        satisfies_both = (ai, bi)
        fails_hypothesis = (-ai, -bi)
        fmt = lambda pair: f"{v}={pair[0]}、{v}'={pair[1]}"  # noqa: E731

    if not (hyp(counter) and not con(counter)):
        raise ValueError("反例が逆の仮定を満たさない、または結論も満たしている")
    if not (hyp(satisfies_both) and con(satisfies_both)):
        raise ValueError("妨害1が「逆の仮定も結論も満たす例」になっていない")
    if hyp(fails_hypothesis):
        raise ValueError("妨害2が逆の仮定を満たしてしまっている")

    correct = fmt(counter)
    distractors = [fmt(satisfies_both), fmt(fails_hypothesis)]
    if correct in distractors:
        raise ValueError("反例と同じ例が妨害に混ざっている")
    steps = [
        Step(
            op="state_counterexample_condition", args=[], result_srepr="",
            result_display="逆の仮定は満たし、逆の結論は満たさない例",
            narration="反例は、逆の仮定は満たすのに逆の結論は満たさない例のことである。"
                      "この2つを同時に見る必要がある。",
        ),
        Step(
            op="pick_counterexample", args=[], result_srepr="", result_display=correct,
            narration="候補を1つずつ確かめて、逆の仮定を満たし、しかも逆の結論を満たさないものを選ぶ。"
                      "それが1つ見つかれば、逆は正しくないと言える。",
        ),
    ]
    return Solution(
        answer=ChoiceAnswer(
            correct=correct, distractors=distractors,
            fact_id="proof_logic.counterexample_for_converse",
        ),
        steps=steps,
    )


__all__ = [
    "_negate",
    "proposition_converse_choice",
    "proposition_counterexample_choice",
    "_KINDS",
    "_parts",
    "_statement",
]
