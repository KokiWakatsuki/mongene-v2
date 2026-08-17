"""コーパスの**解説とヒント**を走査する。

`scan_defects.py` は問題文と答えしか見ていない（解説・ヒントの行に来たら
`mode = None` にして捨てている）。過去のセッションで解説から出た欠陥
（D-25 の生の sympy `Eq(5*x + y, 45)`・D-17 の中身のないヒント）は、
どれも別の作業のついでに人が気づいたもので、**面として走査されたことがない**。

ここは 1,466 型ぶんある。実行:
    PYTHONPATH=engine_core:records/work .venv/bin/python records/work/scan_explanations.py
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path

# 出力先は `build_corpus.py --out` / 環境変数で動かせる。読む側も同じ場所を見る
# （engine_core だけをメインへ移したとき、置き場がずれても走査が追えるように）。
_SRC = Path(os.environ.get("MONGENE_CORPUS_DIR", "records/work/corpus")) / "INDEX.md"
_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def load() -> list[tuple[str, str, str, str, str]]:
    """(セル, 問題文, 答え, 解説, ヒント) の一覧。"""
    out: list[tuple[str, str, str, str, str]] = []
    cell = pending = ""
    buf: dict[str, list[str]] = {"q": [], "a": [], "e": [], "h": []}
    mode: str | None = None

    def flush() -> None:
        if buf["q"]:
            out.append((
                pending,
                "\n".join(buf["q"]).strip(),
                "\n".join(buf["a"]).strip(),
                "\n".join(buf["e"]).strip(),
                "\n".join(buf["h"]).strip(),
            ))

    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cell = m.group(1)
            continue
        if line.startswith("**問題**"):
            flush()
            pending = cell
            buf = {"q": [], "a": [], "e": [], "h": []}
            mode = "q"
            continue
        for marker, key in (("**答え**", "a"), ("**解説**", "e"), ("**ヒント**", "h")):
            if line.startswith(marker):
                buf[key] = [line.removeprefix(marker).strip()]
                mode = key
                break
        else:
            # 節の切れ目。ここで止めないと `### 型1 `kind=...`` のような
            # 見出しを解説に取り込んでしまう（実際に偽陽性2件を出した）。
            if line.startswith(("**問い**", "**図**", "---", "#")):
                mode = None
                continue
            if mode:
                buf[mode].append(line)
            continue
    flush()
    return out


def _answer_parts(a: str) -> list[str]:
    """答えを小問ごとに割り、「(1) 」のような番号を外す。

    複数小問の答えは `(1) +2300円 ／ (2) -1300円`。番号つきのまま解説を探すと
    全部「出てこない」になる。
    """
    parts = []
    for chunk in re.split(r"[／/、]", a):
        t = re.sub(r"^\(\d+\)\s*", "", chunk.strip()).strip()
        if t:
            parts.append(t)
    return parts


# 1手ぶん = 「…（指示の文）。（結果）」
#
# 括弧の中にさらに括弧が入ることがある（「（点Dを中心とする同じ半径の弧（先の弧との
# 交点2つ））」）。入れ子を1段だけ許さないと、その手を丸ごと取りこぼして
# **手の数を数え違える**（作図9セルで「ヒントの数が合わない」と誤検出した）。
_STEP_RE = re.compile(r"([^。\n]*)。（((?:[^（）]|（[^（）]*）)*)）")


def _overlap(a: str, b: str) -> float:
    """b の文字が a にどれだけ含まれるか（0〜1）。順序は見ない粗い尺度。"""
    if not b:
        return 0.0
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    common = sum(min(cb[ch], ca[ch]) for ch in cb)
    return common / len(b)


# 指示の語尾（`scan_step_values.py` と同じ考え方。句点で終わる証明文は外す）。
# **語尾を足すときは、取りこぼしを疑って足す。** `表す` が入っていなかったので
# 「（動く点の位置を x で表す）」という指示の言い直しが 38 問素通りしていた
# （読んで初めて見つかった）。
_INSTRUCTION_TAIL = re.compile(
    r"(する|読み取る|読みとる|読む|求める|考える|数える|比べる|見比べる|そろえる|もどす|"
    r"わける|分ける|使う|調べる|作る|つくる|当てはめる|あてはめる|確かめる|たしかめる|"
    r"決める|きめる|選ぶ|えらぶ|示す|しめす|まとめる|見分ける|見つける|書き出す|結ぶ|"
    r"表す|あらわす|気づく|とる|おく|置く|注目する)$"
)


def _restated_steps(e: str, a: str = "") -> list[str]:
    """括弧の中が、直前の指示文の言い直しになっている手。

    括弧には**その手で得たもの**（値・図形・式）が入るのが設計。指示文と
    ほぼ同じ文字でできているなら、読んでも新しいことが1つも増えない。
    規則そのものを述べている括弧（「共通の符号をそのままつけ…」など）は
    指示文と語が違うので、この尺度では落ちない。
    """
    out = []
    for m in _STEP_RE.finditer(e):
        instruction, result = m.group(1).strip(), m.group(2).strip()
        # 「まず、」「次に、」「最後に、」は指示文の飾りなので外す
        instruction = re.sub(r"^(まず|次に|最後に)、", "", instruction)
        # **動詞で終わっていないものは結果**（`同一円周上にあるといえる`・
        # `垂直二等分線の作図`）。文字の重なりだけで見ていたころは、判断を答える
        # セルの正しい括弧を 231 問ぶん挙げていた（`scan_step_values.py` と同じ規約）。
        if not _INSTRUCTION_TAIL.search(result):
            continue
        # 選択肢を答えるセルは括弧が答えの文そのもの（「データの散らばりの度合いを
        # 表す」）。指示文と語が似るのは当然なので、答えに含まれるものは除く。
        if a and result and result in a:
            continue
        if len(result) >= 6 and _overlap(instruction, result) >= 0.9:
            out.append(result)
    return out



def _restated_no_value(e: str, a: str) -> list[str]:
    """括弧が**指示の形で、値も式も持っていない**手。

    `_restated_steps`（文字の重なり）では分けられなかった。実物で測ると
    直す前が 0.77、直したあとが 0.82 と**逆転する**——「進んだ道のり = 4x」も
    指示文と同じ語を含むからで、重なりは指示か結果かの手がかりにならない。

    分かれ目は**値や式を持っているか**。指示の語尾で終わり、数も記号も無い括弧は
    「その手で得たもの」になっていない（動点の「動く点の位置を x で表す」38 問）。

    選択肢を答えるセルは括弧が答えの文そのもの（「全校の名簿から乱数表を使って選ぶ」）
    なので、答えに含まれるものは除く。
    """
    out = []
    for m in _STEP_RE.finditer(e):
        result = m.group(2).strip()
        if not _INSTRUCTION_TAIL.search(result):
            continue
        if re.search(r"[0-9=＝∥⊥≡∽√°:：]", result):
            continue  # 値・式・記号を持っている＝産物になっている
        if result and result in a:
            continue  # 選択肢の答えそのもの
        out.append(result)
    return out


def _steps_of(e: str) -> list[str]:
    """解説の手（「…。（結果）」）の一覧。"""
    return [m.group(0) for m in _STEP_RE.finditer(e)]


def _hint_count_mismatch(e: str, h: str) -> bool:
    """ヒントの数が「解説の手数 − 1」になっていないか。

    小問が複数あるセルは解説もヒストも小問ぶん並ぶので、この検査は
    **手が2つ以上あり、ヒントが1つ以上ある単問**だけを見る（`／` で割れる
    複数小問は対象外）。
    """
    if "／" in h or "／" in e:
        return False
    steps = _steps_of(e)
    hints = [x for x in h.split(" / ") if x.strip()]
    if len(steps) < 2 or not hints:
        return False
    return len(hints) != len(steps) - 1


def _tail_of_last_step(e: str) -> str:
    steps = _STEP_RE.findall(e)
    return steps[-1][1].strip() if steps else ""


# グラフ・作図の答えは「key 説明 値」を並べた特徴の一覧（`slope 比例定数 4、
# point 通る点 (-3, -12)`）で、最後の手は「点をとる」「直線をひく」という描く指示。
# 値の一致では測れないので対象外にする。
_FEATURE_ANSWER = re.compile(r"[a-z_]{3,} [^\x00-\x7F]")
_DIGITS = re.compile(r"\d+")


def _last_step_not_answer(a: str, e: str) -> bool:
    """解説の最後の手の括弧に出る数が、答えの数と1つも重ならないか。

    包含では測れない（連立方程式は答え `(4, 6)` に対し最後の手が `（y = 6）` で
    正しい。2値のうち片方で終わるのが自然）。**数の集合が交わるか**で見る。
    """
    last = _tail_of_last_step(e)
    if not last or not a or _FEATURE_ANSWER.search(a):
        return False
    tail_nums = set(_DIGITS.findall(last))
    if not tail_nums:
        # 括弧が言葉だけ（作図・証明・選択肢）の手は対象外
        return False
    answer_nums = set(_DIGITS.findall(a))
    return bool(answer_nums) and not (tail_nums & answer_nums)


# 数え方（助数詞）につく数。答えの値ではないので、漏洩の判定から外す。
_COUNTER_NUM = re.compile(r"\d+\s*[辺つ個本回枚人組桁番面点色台冊]")

# 手の**目的**を述べている語（「〜を求める」「〜に直す」…）。
_PURPOSE_VERB = re.compile(
    r"(求める|表す|直す|なおす|そろえる|確かめる|たしかめる|調べる|見つける|"
    r"読み取る|まとめる|つくる|作る|かく|えらぶ|選ぶ|移項|代入|"
    r"約分|通分|消える|消去|はらう|外す|分ける|加える|あてはめ|当てはめ|"
    r"書き出す|並べる|判別|とおく|置く|の形|公式|定理|性質|条件)"
)
# 計算だけの指示文（`27 を 100 でわる。`）。数と演算しか入っていない。
# π・√・上付きも「式の一部」として数える（`2π × 3 × 30/360 を計算する` を捕まえる）。
_BARE_ARITHMETIC = re.compile(r"^[\s\d()+\-×÷/.,、=²³π√２-９]*[をで][^。]{0,12}[るす]。?$")


def _instruction_is_bare_arithmetic(e: str) -> list[str]:
    """指示文が**計算式だけ**になっていないか（何を求めた数なのかが消えている）。

    `Step.detail` は narration を置きかえるので、detail に値だけを書くと
    **目的が落ちる**。実際に3回踏んだ:

      × まず、27 を 100 でわる。（0.27）            ← 何の数か分からない
      ○ まず、注目していることがらの数 27 を、全体の数 100 でわって、相対度数を求める。

    「計算式＋動詞」だけで、目的を述べる語が1つも無い指示文を挙げる。
    """
    out = []
    for m in _STEP_RE.finditer(e):
        instruction = re.sub(r"^(まず|次に|最後に)、", "", m.group(1).strip())
        if not re.search(r"\d", instruction):
            continue
        if _PURPOSE_VERB.search(instruction):
            continue
        if _BARE_ARITHMETIC.match(instruction + "。"):
            out.append(instruction)
    return out


def _hint_leaks_answer(a: str, h: str) -> bool:
    """ヒントに答えの文字列がそのまま出ていないか（先出し）。

    2文字以下の答え（「正」「誤」など）は偶然の一致が多いので見ない。

    **値を含む断片だけを見る。** 証明の答えは地の文なので、`、` で割ると
    「3辺のうち」のような**ただの言い回し**が断片として出てくる。それがヒントに
    あるだけで「答えが漏れている」と挙げていた（g3_l52.proof.Lv3 で3問の誤検出）。
    先出しになるのは**答えの値・式**が見えたときなので、数字か記号を含む断片に絞る。
    """
    for part in _answer_parts(a):
        token = part.strip()
        if len(token) < 3 or token not in h:
            continue
        # **助数詞につく数は「値」ではない。** 「3辺のうち」の 3 は数え方であって
        # 答えではないのに、数字が入っているというだけで挙げていた
        # （g3_l52.proof.Lv3 で3問の誤検出。G-Q5t が「桁」を counter として
        # 除いているのと同じ考え方）。
        stripped = _COUNTER_NUM.sub("", token)
        if re.search(r"[0-9=＝∥⊥≡∽√°]", stripped):
            return True
    return False


# q, a, e（解説）, h（ヒント）を受け取る
_CHECKS: dict[str, object] = {
    # D-25 の再発検査。sympy の内部表現が日本語の解説に混ざる。
    "解説に生の sympy が出ている": lambda q, a, e, h: bool(
        re.search(r"\b(Eq|Rational|Symbol|Integer|Float|Pow|Mul|Add|sqrt|Abs)\s*\(", e + h)
    ),
    # Python のリスト・辞書・タプルがそのまま出ている。
    "解説に Python の値が出ている": lambda q, a, e, h: bool(
        re.search(r"\[\s*'|\"\s*\]|\{\s*'|None\b|True\b|False\b", e + h)
    ),
    "解説が空": lambda q, a, e, h: not e.strip(),
    "ヒントが空": lambda q, a, e, h: not h.strip(),
    # D-17（中身のないヒント）の解説版。
    # 解説の各手は「〜する。（結果）」の形で、括弧には**その手で得たもの**が入る。
    # 括弧の中が指示の言い直し（動詞で終わる）だと、読んでも何も分からない。
    #   悪い: まず、…かを読み取る。（どちらの向きを…かを読み取る）
    #   良い: まず、点Cを中心に弧をかく。（点Cを中心とする弧）
    "解説の括弧が指示の言い直し": lambda q, a, e, h: bool(_restated_steps(e, a)),
    # 語と助詞の間の半角スペース（D-3 の解説側）。
    "解説にかなと語の間の半角スペース": lambda q, a, e, h: bool(
        re.search(r"[ぁ-んァ-ヶ一-龥] [をがはにでとへのも]", e + h)
    ),
    "解説に英字の変数名が残る": lambda q, a, e, h: bool(
        re.search(r"\b(lhs|rhs|expr|val|tmp|res|ans|obj|params?|kind)\b", e + h)
    ),
    # 「解説の分母が13以上」はここから外した（2026-08-14）。
    # 答えの大きさは **6つ目のゲート `engine.eval.answer_size`** が、セルごとの
    # 宣言（`answer_size_max`）込みで測る。文だけを見るこの検査は、確率の答え
    # （`5/36`・`21/55`）や累乗（`4/81`）まで挙げてしまい、実物は13セルすべてが
    # 正当だった。**同じことを2か所で測らない**（片方が必ず古くなる）。
    "解説が1文しかない": lambda q, a, e, h: bool(
        e.strip() and e.count("。") <= 1 and len(e) < 24
    ),
    # --- ここから 2026-08-13b に足した3検査（ヒントと解説の対応・小問の整合） ---
    #
    # 「ヒントの数＝解説の手数−1」は `t1_template._build_hints` が
    # `[step.narration for step in sq.steps[:-1]]` を返すことで**コードが保証している**。
    # 走査で確かめようとしたが、括弧の無い手（`result_display` が空）と複数文の
    # narration を、書き上がった文から区別できず**誤検出しか出なかった**ので外した。
    # 確かめるなら MR（構造）を見る側＝`text_quality` でやること。
    # 解説の**最後の手の括弧**は答えそのものでなければならない（解説は答えに至る道
    # なので、最後に答えが出ないなら道が途切れている）。
    "解説の最後の手が答えで終わっていない": lambda q, a, e, h: _last_step_not_answer(a, e),
    # ヒントに答えが入っていたら先出し（G-Q5t の走査版。ゲートは問題文とヒントを
    # 見るが、こちらは**答えの文字列そのもの**が現れていないかを見る）。
    "ヒントに答えがそのまま出ている": lambda q, a, e, h: _hint_leaks_answer(a, h),
    # `Step.detail` を入れるときに**目的を落とす**退行の見張り（3回踏んだ）。
    "解説の指示文が計算式だけ": lambda q, a, e, h: bool(_instruction_is_bare_arithmetic(e)),
    # 括弧が指示の言い直しで、値も式も無い（`_restated_steps` の取りこぼし）。
    "解説の括弧に値も式も無い": lambda q, a, e, h: bool(_restated_no_value(e, a)),
}


def main() -> None:
    rows = load()
    hits: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)
    for cell, q, a, e, h in rows:
        for name, fn in _CHECKS.items():
            try:
                if fn(q, a, e, h):  # type: ignore[operator]
                    hits[name].append((cell, q, a, e))
            except Exception:  # noqa: BLE001
                pass
    print(f"走査した問題 {len(rows)} 個（解説つき {sum(1 for r in rows if r[3])} 個）\n")
    for name in _CHECKS:
        found = hits.get(name, [])
        cells = sorted({c for c, _, _, _ in found})
        print(f"■ {name}: {len(found)} 問 / {len(cells)} セル")
        for cell, q, a, e in found[:4]:
            print(f"    {cell}")
            print(f"      Q {q.replace(chr(10), ' / ')[:76]}")
            print(f"      A {a[:56]}")
            print(f"      解説 {e.replace(chr(10), ' / ')[:76]}")
        if len(cells) > 4:
            print(f"    … ほか {len(cells) - 4} セル")
        print()


if __name__ == "__main__":
    main()
