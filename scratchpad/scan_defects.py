"""コーパスを機械で走査して、質の疑わしい箇所を型ごとに数える。

読むだけでは規模が分からない。**同じ粗さが何セルに出ているか**を先に測ってから、
実物と突き合わせる。ここで拾うのは「疑い」であって、確定した欠陥ではない。

実行: PYTHONPATH=. .venv/bin/python scratchpad/scan_defects.py
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_SRC = Path("scratchpad/corpus/INDEX.md")

_CELL_RE = re.compile(r"^##\s+((?:exam|g[123])_l\d+\.\w+\.Lv\d+)")


def load() -> list[tuple[str, str, str]]:
    """(セル, 問題文, 答え) の一覧。"""
    out = []
    cell = ""
    pending_cell = ""   # いま溜めている問題が属するセル（次のセルに入っても書き換えない）
    q: list[str] = []
    a: list[str] = []
    mode = None
    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cell = m.group(1)
            continue
        if line.startswith("**問題**"):
            if q:
                out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip()))
            pending_cell = cell
            q, a, mode = [], [], "q"
            continue
        if line.startswith("**問い**"):
            mode = None
            continue
        if line.startswith("**答え**"):
            a = [line.removeprefix("**答え**").strip()]
            mode = "a"
            continue
        if line.startswith("**解説**") or line.startswith("**ヒント**") or line.startswith("**図**"):
            mode = None
            continue
        if mode == "q":
            q.append(line)
        elif mode == "a":
            a.append(line)
    if q:
        out.append((pending_cell, "\n".join(q).strip(), "\n".join(a).strip()))
    return out


_CHECKS: dict[str, callable] = {
    "答えが分母13以上の分数": lambda q, a: bool(
        re.search(r"-?\d+/(1[3-9]|[2-9]\d+)\b", a)
    ),
    "問題文に絶対値記号があるのに『絶対値を求めよ』": lambda q, a: (
        "絶対値を求め" in q and "|" in q
    ),
    "かなと語の間の半角スペース": lambda q, a: _stray_space(q),
    "『である』が二重": lambda q, a: bool(re.search(r"である\s*であること", q)),
    "小数と分数が混在": lambda q, a: bool(
        re.search(r"\d/\d", q) and re.search(r"\d\.\d", q)
    ),
    "答えが空": lambda q, a: not a.strip(),
    "問題文に英字の符号が残る": lambda q, a: bool(
        re.search(r"\b(choice|value|proof_text|draw_\w+|read_\w+)\b", q)
    ),
    "答えの分数が帯分数にすべき大きさ": lambda q, a: bool(
        re.search(r"-?(\d{3,})/(\d+)", a)
    ),
    # --- ここから 2026-08-10 追加（D-28 の7件のうち5件をこの2つが釣り上げた） ---
    # **存在しない道具**（D-13 の再発検査）。さいころは6面、硬貨は2面。
    # カードは教材の枚数（〜20枚）まで。1セル直しても同じ単元の別セルに残る。
    # **例外**: 倍数の問題だけは50枚まで許す。包除（4の倍数または5の倍数）は
    # lcm 以上の枚数がないと重なりが実在せず、教科書も「1から30まで」「1から50まで」
    # の形で出す（3周目の走査で当たった `g2_l51.word_problem.Lv3` の21枚がこれ）。
    "存在しない面数の道具": lambda q, a: bool(
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
    "相対度数・割合を分数で答えている": lambda q, a: bool(
        re.search(r"(相対度数|割合|確率を.{0,6}推定)", q) and re.search(r"\d+/\d+", a)
        and "確率を求め" not in q  # 確率そのものは分数で答えるのが作法
    ),
    # --- ここから 2026-08-10 の3周目で見つけた分（R-1/R-2/D-29 の再発検査） ---
    # **代表値は小数で書き切れるなら小数**（R-1。`平均値 271/8` が出ていた）。
    "代表値を分数で答えている": lambda q, a: bool(
        re.search(r"(平均値|中央値|最頻値|第[一二三]四分位数)\s*-?\d+/\d+", a)
    ),
    # **角の大きさは整数**（D-23 の再発検査。R-2 で `225/2°` が出ていた）。
    "角の大きさが分数": lambda q, a: bool(re.search(r"\d+/\d+\s*°", a)),
    # **数を問うているのに、その数を与えている**（D-29。「ある湖にすむ魚のおよその数を
    # 調べたい。対象は全部で270匹ある」は場面として成り立たない）。
    "問うている数を問題文が与えている": lambda q, a: bool(
        re.search(r"およその(数|個数|総数)を(調べ|求め)", q)
        and re.search(r"(対象|母集団)は全部で", q)
    ),
    # **長さ・個数・角度は負にならない**（S-1。`EM=-5cm` が出ていた）。
    # 温度や座標は負でありうるので、単位を持つ量だけを見る。
    "長さ・個数が負": lambda q, a: bool(
        re.search(r"-\d+\s*(cm|mm|km|m²|cm²|cm³|人|個|本|枚|冊|回|匹|台|軒|°)(?![/\d])", q)
    ),
    # **三角形として成り立たない3辺**（S-9。`3辺の長さが 5cm, 12cm, 19cm` が出ていた）。
    "3辺が三角形にならない": lambda q, a: _sides_not_a_triangle(q),
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
    for cell, q, a in rows:
        for name, fn in _CHECKS.items():
            try:
                if fn(q, a):
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
