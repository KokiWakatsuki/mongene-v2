"""選択式の問題の**選択肢**を全部書き出し、機械で測れるところを測る。

## なぜ要るか

knowledge form は選択式で、**選択肢の出来が問題の質そのもの**である。
明らかに変な選択肢が混じっていれば、生徒は内容を読まずに消去法で当たる。
630セルの大きな塊なのに、**選択肢は一度も読まれていない**（2026-08-15 時点）。

## 機械で測れる3つ

  答えが長さで浮く    正解だけ極端に長い／短いと、読まずに当たる
  答えが言い回しで浮く  正解だけ「〜こと」で終わるなど、形が違うと当たる
  選択肢が重複する     同じ意味の選択肢が2つあると答えが一意でない
                     （文字列一致で拾えるのは完全重複だけ。意味の重複は目で見る）

**測れないもの（目で読む）**: 誤答が「もっともらしい誤り」になっているか。
これは概念を知らないと判断できないので、機械では出せない。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/dump_choices.py           # 測定
  PYTHONPATH=engine_core .venv/bin/python records/work/dump_choices.py --dump    # 全文を出す
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, family_of, make_env

_OUT = Path("records/work/bt/choices.md")


def main() -> int:
    dump = "--dump" in sys.argv
    env = make_env()
    rows: list[tuple[str, str, list[str]]] = []
    for coord in capability_cells(env):
        try:
            res = generate(
                cell_request(coord, 1),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
        except Exception:  # noqa: BLE001
            continue
        if isinstance(res, Unsupported):
            continue
        for sq in res.sub_questions:
            # **属性名は `distractors`（`choices` ではない）。**
            # 最初 `choices` を見て 0 件になった。0 件が出たら、まず検査が
            # 動いているかを疑う——ここはその実例。
            if getattr(sq.answer, "kind", "") != "choice":
                continue
            correct = str(sq.answer.correct)
            ch = [correct, *[str(d) for d in sq.answer.distractors]]
            rows.append((f"{family_of(coord)}.Lv{coord.level}", correct, ch))

    print(f"選択式の小問 {len(rows)} 件\n")

    # ① 正解が長さで浮いていないか（正解の長さが、誤答の平均から大きく離れる）
    long_out: list[tuple[float, str, int, list[int]]] = []
    for cell, correct, ch in rows:
        others = [len(c) for c in ch if c != correct]
        if len(others) < 2:
            continue
        m = statistics.mean(others)
        if m == 0:
            continue
        ratio = len(correct) / m
        if ratio >= 1.6 or ratio <= 0.62:
            long_out.append((ratio, cell, len(correct), sorted(others)))
    print(f"=== 正解が長さで浮いている（{len(long_out)} 件）===")
    for r, cell, n, others in sorted(long_out, key=lambda t: -abs(t[0] - 1))[:20]:
        print(f"  {cell:<30} 正解 {n:>3}字 / 誤答 {others}  比 {r:.2f}")

    # ⓪ **誤答が少なすぎないか。** 生成物を全部読んで見つけた欠陥
    #    （g3_l39 は誤答が 0 個で必ず正解する問題だった）を、二度と戻さないための検査。
    #    誤答は「同じ domain の他の用語」から作るので、用語が少ない domain は
    #    ここに出る。**この検査は読んで見つけたものを既知にしてから足した**——
    #    先に検査を書いても、この形は思いつかなかった。
    # **真偽型（○×）は誤答が1つで正当**。「いえる／いえない」「正の数／負の数」の
    # ように、選択肢が対になっている問いは実物にもある。用語想起で誤答が
    # 1つ以下のものだけを出す（読んで判断した内容を、検査に写した）。
    def _is_pair(a: str, b: str) -> bool:
        # 否定は語尾に付くとは限らない（「比例するとはいえない」対「比例するといえる」）。
        # 肯定・否定の言い回しをそろえてから比べる。
        def norm(s: str) -> str:
            for neg, pos in (("とはいえない", "といえる"), ("ではない", "である"),
                             ("でない", "である"), ("しない", "する")):
                s = s.replace(neg, pos)
            return s.replace("ない", "")
        if norm(a) == norm(b) and a != b:
            return True
        # 「AとBのどちらか、記号で答えよ」型。本文が A・B を定義しているので、
        # 選択肢が記号だけでも問題は成立する（読んで確かめた）。
        if {a, b} <= {"A", "B", "A組", "B組"}:
            return True
        # 向き・位置・調査の種類のように、対になる言い方が2つしかないもの。
        for x, y in (("右上がり", "右下がり"), ("垂直", "平行"),
                     ("全数調査", "標本調査"), ("散らばり", "中心"),
                     ("右上と左下", "左上と右下"), ("偏りが生じにくく", "偏りが生じやすく")):
            if (x in a and y in b) or (y in a and x in b):
                return True
        for neg in ("とはいえない", "ではない", "でない", "ない", "しない"):
            if a == b + neg or b == a + neg:
                return True
        opposites = [("正の数", "負の数"), ("通る", "通らない"), ("正しい", "誤り"),
                     ("ふくまれる", "ふくまれない"), ("右上がり", "右下がり"),
                     ("単項式", "多項式"), ("有理数", "無理数"), ("傾き", "切片"),
                     ("閉じている", "閉じていない"), ("変わる", "変わらない"),
                     ("等しい", "等しくない"), ("妥当である", "妥当でない"),
                     ("解である", "解ではない"), ("解である", "解でない")]
        return any({a, b} == set(o) for o in opposites) or (
            a.lstrip("+-").isdigit() and b.lstrip("+-").isdigit())

    thin = [(cell, correct, ch) for cell, correct, ch in rows
            if len(ch) < 3 and not (len(ch) == 2 and _is_pair(ch[0], ch[1]))]
    print(f"=== 誤答が2つ未満（{len(thin)} 件）===")
    for cell, correct, ch in thin[:20]:
        print(f"  {cell:<32} ○{correct} ×{[c for c in ch if c != correct]}")
    print()

    # ② 選択肢の完全重複
    dup = [(cell, ch) for cell, _c, ch in rows if len(set(ch)) != len(ch)]
    print(f"\n=== 選択肢が重複している（{len(dup)} 件）===")
    for cell, ch in dup[:10]:
        print(f"  {cell}: {ch}")

    # ③ 選択肢が2つしかない（○×型。実物にもあるが、当てずっぽうで50%）
    two = [cell for cell, _c, ch in rows if len(ch) == 2]
    print(f"\n=== 選択肢が2つ（{len(two)} 件）===")
    print("  " + "、".join(sorted(set(two))[:14]) + (" …" if len(set(two)) > 14 else ""))

    if dump:
        lines = ["# 選択式の問題の選択肢（全件）", ""]
        for cell, correct, ch in rows:
            lines.append(f"## {cell}")
            for c in ch:
                lines.append(f"  {'○' if c == correct else '×'} {c}")
            lines.append("")
        _OUT.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n→ {_OUT}（{len(rows)} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
