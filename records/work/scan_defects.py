"""コーパスを機械で走査して、質の疑わしい箇所を型ごとに数える。

読むだけでは規模が分からない。**同じ粗さが何セルに出ているか**を先に測ってから、
実物と突き合わせる。ここで拾うのは「疑い」であって、確定した欠陥ではない。

実行: .venv/bin/python records/work/scan_defects.py
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_SRC = Path("records/work/corpus/INDEX.md")

_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def load() -> list[tuple[str, str, str, str]]:
    """(セル, 問題文, 答え, 図) の一覧。

    図は「図に言及しているのに図が無い」の検査に要る。コーパスは図を持たない
    型にも `**図** （図なし）` を必ず出すので、有無はこの1行で判定できる。
    """
    out = []
    cell = ""
    pending_cell = ""   # いま溜めている問題が属するセル（次のセルに入っても書き換えない）
    q: list[str] = []
    a: list[str] = []
    fig = ""
    mode = None
    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cell = m.group(1)
            continue
        if line.startswith("**問題**"):
            if q:
                out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip(), fig))
            pending_cell = cell
            q, a, fig, mode = [], [], "", "q"
            continue
        if line.startswith("**問い**"):
            mode = None
            continue
        if line.startswith("**答え**"):
            a = [line.removeprefix("**答え**").strip()]
            mode = "a"
            continue
        if line.startswith("**図**"):
            fig = line.removeprefix("**図**").strip()
            mode = None
            continue
        if line.startswith("**解説**") or line.startswith("**ヒント**"):
            mode = None
            continue
        if mode == "q":
            q.append(line)
        elif mode == "a":
            a.append(line)
    if q:
        out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip(), fig))
    return out


def _num_token_in(num: str, text: str) -> bool:
    """数 `num` が、より長い数の一部としてではなく単独で本文に出るか。

    `-1.4` の絶対値の答え `1.4` は文字列としては本文に含まれるが、答えを
    与えているわけではない。前後が数字・小数点でないことを見る。
    """
    for m in re.finditer(re.escape(num), text):
        before = text[m.start() - 1] if m.start() else ""
        after = text[m.end()] if m.end() < len(text) else ""
        # 直前が「-」で答えに符号が無いなら、負の数の一部を切り出しただけ
        # （-1.4 の絶対値の答え 1.4 が本文にある、とは言えない）。
        if before == "-" and not num.startswith("-"):
            continue
        if not (before.isdigit() or before == ".") and not (after.isdigit() or after == "."):
            return True
    return False


_CHECKS: dict[str, callable] = {
    "答えが分母13以上の分数": lambda q, a, fig: bool(
        re.search(r"-?\d+/(1[3-9]|[2-9]\d+)\b", a)
    ),
    "問題文に絶対値記号があるのに『絶対値を求めよ』": lambda q, a, fig: (
        "絶対値を求め" in q and "|" in q
    ),
    "かなと語の間の半角スペース": lambda q, a, fig: _stray_space(q),
    "『である』が二重": lambda q, a, fig: bool(re.search(r"である\s*であること", q)),
    "小数と分数が混在": lambda q, a, fig: bool(
        re.search(r"\d/\d", q) and re.search(r"\d\.\d", q)
    ),
    "答えが空": lambda q, a, fig: not a.strip(),
    "問題文に英字の符号が残る": lambda q, a, fig: bool(
        re.search(r"\b(choice|value|proof_text|draw_\w+|read_\w+)\b", q)
    ),
    "答えの分数が帯分数にすべき大きさ": lambda q, a, fig: bool(
        re.search(r"-?(\d{3,})/(\d+)", a)
    ),
    # --- ここから 2026-08-10 追加（D-28 の7件のうち5件をこの2つが釣り上げた） ---
    # **存在しない道具**（D-13 の再発検査）。さいころは6面、硬貨は2面。
    # カードは教材の枚数（〜20枚）まで。1セル直しても同じ単元の別セルに残る。
    # **例外**: 倍数の問題だけは50枚まで許す。包除（4の倍数または5の倍数）は
    # lcm 以上の枚数がないと重なりが実在せず、教科書も「1から30まで」「1から50まで」
    # の形で出す（3周目の走査で当たった `g2_l51.word_problem.Lv3` の21枚がこれ）。
    "存在しない面数の道具": lambda q, a, fig: bool(
        re.search(r"1から([7-9]|[1-9]\d+)までの目が出る", q)
        or (
            re.search(r"1から([2-9]\d+)までの番号", q)
            and not (
                "の倍数" in q
                and int(re.search(r"1から(\d+)までの番号", q).group(1)) <= 50
            )
        )
    ),
    # **相対度数・割合は小数で答える**（D-19/D-24 の再発検査）。
    "相対度数・割合を分数で答えている": lambda q, a, fig: bool(
        re.search(r"(相対度数|割合|確率を.{0,6}推定)", q) and re.search(r"\d+/\d+", a)
        and "確率を求め" not in q  # 確率そのものは分数で答えるのが作法
    ),
    # --- ここから 2026-08-10 の3周目で見つけた分（R-1/R-2/D-29 の再発検査） ---
    # **代表値は小数で書き切れるなら小数**（R-1。`平均値 271/8` が出ていた）。
    "代表値を分数で答えている": lambda q, a, fig: bool(
        re.search(r"(平均値|中央値|最頻値|第[一二三]四分位数)\s*-?\d+/\d+", a)
    ),
    # **角の大きさは整数**（D-23 の再発検査。R-2 で `225/2°` が出ていた）。
    "角の大きさが分数": lambda q, a, fig: bool(re.search(r"\d+/\d+\s*°", a)),
    # **数を問うているのに、その数を与えている**（D-29。「ある湖にすむ魚のおよその数を
    # 調べたい。対象は全部で270匹ある」は場面として成り立たない）。
    "問うている数を問題文が与えている": lambda q, a, fig: bool(
        re.search(r"およその(数|個数|総数)を(調べ|求め)", q)
        and re.search(r"(対象|母集団)は全部で", q)
    ),
    # **長さ・個数・角度は負にならない**（S-1。`EM=-5cm` が出ていた）。
    # 温度や座標は負でありうるので、単位を持つ量だけを見る。
    "長さ・個数が負": lambda q, a, fig: bool(
        re.search(r"-\d+\s*(cm|mm|km|m²|cm²|cm³|人|個|本|枚|冊|回|匹|台|軒|°)(?![/\d])", q)
    ),
    # **三角形として成り立たない3辺**（S-9。`3辺の長さが 5cm, 12cm, 19cm` が出ていた）。
    "3辺が三角形にならない": lambda q, a, fig: _sides_not_a_triangle(q),

    # --- EVALUATION.md「足りないゲート」で未実装のまま残っていた2つ ---
    # D-6: 本文が図を指しているのに図が無い。生徒は読んでも解けない。
    # 「図形」「図書館」のような複合語で釣れないよう、図を指す言い方に限る。
    "図に言及しているのに図が無い": lambda q, a, fig: (
        fig == "（図なし）"
        and bool(re.search(r"(右|下|上|左|次)の図|図のよう|図を見|図に示|図において|下図|右図", q))
    ),
    # D-8: 答えが問題文にそのまま書いてある＝読むだけで解ける。
    # 除くもの（どれも答えが本文に出るのが正しい形）:
    #   選択式        … 選択肢に正解が並ぶ
    #   判定・二択     … 「平行であるかどうか」→「平行である」は問いの言い直し
    #   証明          … 結論が本文の「〜を証明せよ」と一致するのが当たり前
    # 数の答えは、より長い数の一部（-1.4 の中の 1.4）で釣れないよう境界を見る。
    #
    # 【既知の当たり6件・どれも欠陥ではない（2026-08-13 に全件精査）】
    # 答えが本文の値と一致すること自体が、その単元で学ぶ性質だから一致する:
    #   g2_l32.find_value.Lv1  同位角は等しい          → 131 と 131
    #   g3_l48.find_value.Lv2  円周角の定理            → 45° と 45°
    #   g2_l50.find_value.Lv2  等積変形（面積が等しい）→ 219 と 219
    #   g3_l14.calculation.Lv1 (√105)² = 105
    #   g3_l19.calculation.Lv1 19/√19 = √19（有理化）
    #   g2_l10.calculation.Lv1 代入して右辺と一致＝「成り立つ」側の枝
    #                          （family YAML が holds で両方出すと明記）
    # これ以外が出たら実物を見ること。
    "答えが問題文にそのまま出ている": lambda q, a, fig: (
        len(a) >= 3
        and not re.search(r"選べ|選びなさい|つ選|どちら|どれ|いずれ", q)
        and not re.search(r"かどうか|といえ|ますか|妥当|正しいですか|答えよ。$", q)
        and not a.startswith("（証明）")
        and (
            _num_token_in(a.split("／")[0].strip(), q)
            if re.fullmatch(r"-?\d+(?:\.\d+)?", a.split("／")[0].strip())
            else a.split("／")[0].strip() in q
        )
    ),
}


def _stray_space(q: str) -> bool:
    """語と助詞の間に半角スペースが入っているか（D-3 / R-4 / S-10）。

    選択肢は「ア 直線 イ 放物線」のように記号のあとを1つ空ける書き方なので、
    記号と直後の空白を落としてから見る。これを除かないと偽陽性ばかりになる。
    """
    stripped = re.sub(r"\s*[アイウエオ]\s", "", q)
    return bool(re.search(r"[ぁ-んァ-ン一-龥] [ぁ-んァ-ン一-龥]", stripped))


def _sides_not_a_triangle(q: str) -> bool:
    """「3辺の長さが a, b, c」の形で与えられた3辺が三角形をつくらないか。"""
    m = re.search(r"3辺の長さが\s*(-?\d+)\D+?(-?\d+)\D+?(-?\d+)\s*(?:cm|m|mm)", q)
    if not m:
        return False
    x, y, z = sorted(int(v) for v in m.groups())
    return x <= 0 or x + y <= z


def main() -> None:
    rows = load()
    hits: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for cell, q, a, fig in rows:
        for name, fn in _CHECKS.items():
            try:
                if fn(q, a, fig):
                    hits[name].append((cell, q, a))
            except Exception:  # noqa: BLE001
                pass
    print(f"走査した問題 {len(rows)} 個\n")
    for name in _CHECKS:
        found = hits.get(name, [])
        cells = sorted({c for c, _, _ in found})
        print(f"■ {name}: {len(found)} 問 / {len(cells)} セル")
        for cell, q, a in found[:4]:
            one = q.replace("\n", " / ")[:78]
            print(f"    {cell}\n      Q {one}\n      A {a[:60]}")
        if len(cells) > 4:
            print(f"    … ほか {len(cells) - 4} セル")
        print()


if __name__ == "__main__":
    main()
