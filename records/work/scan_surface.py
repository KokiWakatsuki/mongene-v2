"""**自分で読んで見つけた欠陥の型**を、コーパス全体に当てる走査。

`scan_explanations.py` は解説の作りを見る。こちらは**読んで初めて気づいた面**
——表記のゆれ・単位の付け忘れ・答えの丸写し・重複——を見る。

読むのは context に入る分しか読めないが、走査は 1201 問すべてに当たる。
読んで型が分かったら走査にする、が「同じ根の別の出口」を潰す唯一の方法。

実行:
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/scan_surface.py
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from scan_explanations import _STEP_RE, load


def _steps(e: str) -> list[tuple[str, str]]:
    """(指示文, 括弧の中身) の一覧。接続詞は落とす。"""
    return [
        (re.sub(r"^(まず|次に|最後に)、", "", m.group(1).strip()), m.group(2).strip())
        for m in _STEP_RE.finditer(e)
    ]


# その手の仕事が「複数の値を集めること」である指示文（答えと一致して当然）。
_COLLECTING = re.compile(r"(すべて並べ|並べて答え|答えをすべて|まとめて答え|"
                         r"両端の値を読|それぞれ.{0,6}を読み取|組にして|答えとする)")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


# --- ① 最後の手の括弧が、答え全体の丸写し ----------------------------------
# 括弧には「その手で得たもの」を入れる規約。答えを丸ごと写すと、前の手で出した値が
# もう一度並ぶ（`階級値 57.5、度数の合計 25`）。**複数の値を並べた答え**のときだけ見る。
def _last_step_copies_answer(a: str, e: str) -> bool:
    """最後の手の括弧が、**前の手ですでに出した値をもう一度並べている**か。

    「答えと一致するか」で見ると誤検出が出る。最後の手が本当に複数の値を
    集める手（「求めた時刻をすべて並べる」「最小値と最大値を読む」）もあり、
    そこでは答えと一致するのが正しい（37セル挙げて、その多くがこれだった）。

    本当の欠陥は**同じ値が2度出ること**なので、
    「最後の括弧＝答え」かつ「その答えの一部が前の手の括弧にすでにある」で見る。
    """
    st = _steps(e)
    if len(st) < 2 or "／" in a:
        return False
    instruction, last = st[-1]
    if _norm(last) != _norm(a):
        return False
    # **集める手は除く。** 「求めた時刻をすべて並べる」「最小値と最大値を読む」は、
    # その手の仕事が複数の値を集めることなので、答えと一致するのが正しい。
    if _COLLECTING.search(instruction):
        return False
    earlier = {_norm(d) for _i, d in st[:-1]}
    # 「表面積 484π cm²」→「484πcm²」。ラベルを外した**値**で、完全一致だけを見る
    # （部分一致にすると `1.4` が前の手の計算式に出るだけで挙がる＝誤検出）。
    parts = []
    for chunk in re.split(r"[、,]", a):
        v = _norm(re.sub(r"^[^\d\-+(（]*", "", chunk))
        if len(v) >= 2:
            parts.append(v)
    return any(p in earlier for p in parts)


# --- ② 1手目の括弧が、もう答えになっている --------------------------------
def _first_step_is_answer(a: str, e: str) -> bool:
    st = _steps(e)
    if len(st) < 2 or not a:
        return False
    return _norm(st[0][1]) == _norm(a)


# --- ③ 表記のゆれ -----------------------------------------------------------
_MIXED_ORDINAL = re.compile(r"第[一二三四]四分位数")          # 算用数字と混ざる
_PLUS_MINUS = re.compile(r"[+\-] -\d")                        # `3x + -3`
# 「x の値」「x の項」だけを見る。**「x座標」「y軸」は教科書もこう書く**ので、
# それを挙げると 44 問のほとんどが偽陽性になった（最初そう書いて外した）。
_TIGHT_LATIN = re.compile(r"[ぁ-んァ-ヶ一-龥][a-z](?:の値|の項|の係数)")
_KATAKANA_ZERO = re.compile(r"ゼロ")


def _notation_problems(q: str, a: str, e: str) -> list[str]:
    out = []
    text = f"{q}\n{a}\n{e}"
    if _MIXED_ORDINAL.search(text) and re.search(r"第[13]四分位数", text):
        out.append("第一/第1 の混在")
    if _PLUS_MINUS.search(text):
        out.append("`+ -` の表記")
    if _TIGHT_LATIN.search(text):
        out.append("英字の前に空きが無い")
    if _KATAKANA_ZERO.search(text):
        out.append("「ゼロ」と「0」の混在")
    return out


# --- ④ 問題文にあるのに、解説でも答えでも使われない数値 --------------------
# 「底面の半径4cm、高さ14cm」と与えて比だけを答えさせる、のような取り違え。
_NUM = re.compile(r"\d+(?:\.\d+)?")
_COUNTER = re.compile(r"\d+\s*[つ個本回枚人組桁番面点色台冊次]")


def _unused_given_numbers(q: str, a: str, e: str) -> list[str]:
    """**この検査は当てにならない**（450問挙げて、ほとんどが偽陽性だった）。

    問題文の `0.6` が解説では `3/5` に、`+122` が `122` に化けるので、
    「本文に同じ数字が出るか」では使われたかどうかを判定できない。
    値の同一性は文字列では測れない——測るなら params と MR の突き合わせが要る。
    報告には出さず、根拠として残す（同じ検査をもう一度書かないため）。
    """
    body = f"{a}\n{e}"
    stripped = _COUNTER.sub("", q)
    used = set(_NUM.findall(body))
    out = []
    for n in _NUM.findall(stripped):
        # 1桁も見る（「半径が4cm」の 4 を見落とす）。単独の数として本文に
        # 現れているかは下の正規表現で確かめるので、桁数で切らない。
        if n in used:
            continue
        # 桁の一部として現れていれば使われているとみなす（`24` が `240` に出る等は除く）
        if re.search(rf"(?<!\d){re.escape(n)}(?!\d)", body):
            continue
        out.append(n)
    return sorted(set(out))


def main() -> None:
    rows = load()
    hits: dict[str, list[tuple[str, str]]] = defaultdict(list)
    dup: dict[tuple[str, str], list[str]] = defaultdict(list)

    for cell, q, a, e, _h in rows:
        if _last_step_copies_answer(a, e):
            hits["最後の手の括弧が答えの丸写し"].append((cell, a[:70]))
        if _first_step_is_answer(a, e):
            hits["1手目の括弧がもう答え"].append((cell, a[:70]))
        for name in _notation_problems(q, a, e):
            hits[name].append((cell, q[:70]))
        # 頂点名だけを伏せた問題文が一致する＝実質同じ問題
        masked = re.sub(r"[A-Z]", "@", q)
        dup[(cell, _norm(masked))].append(a)

    for (cell, _m), answers in dup.items():
        if len(answers) > 1 and len(set(answers)) == 1:
            hits["頂点名だけ違う同じ問題"].append((cell, f"{len(answers)}問 / 答え {answers[0][:50]}"))

    print(f"走査した問題 {len(rows)} 個\n")
    for name in (
        "最後の手の括弧が答えの丸写し", "1手目の括弧がもう答え",
        "第一/第1 の混在", "`+ -` の表記", "英字の前に空きが無い",
        "「ゼロ」と「0」の混在", "頂点名だけ違う同じ問題",
    ):
        found = hits.get(name, [])
        cells = sorted({c for c, _ in found})
        print(f"■ {name}: {len(found)} 問 / {len(cells)} セル")
        for cell, sample in found[:5]:
            print(f"    {cell}  {sample}")
        if len(cells) > 5:
            print(f"    … ほか {len(cells) - 5} セル")
        print()


if __name__ == "__main__":
    main()
