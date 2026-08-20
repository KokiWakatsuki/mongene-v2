#!/usr/bin/env python3
"""生成された問題が、その**学年でまだ習っていない道具**を使っていないかを見る。

## なぜ要るか

AI に数式を書かせて量産する（理想型の関門⑤）。そのとき出る壊れ方のひとつが
**先取り**——中1の方程式の単元に、平方根や相似が混ざった問題ができてしまう。

既存のゲートはこれを見ていない。`spec_lint R6` は recipe が宣言した概念タグの
部分集合検査なので、**新しい数式が持ち込む道具**は宣言に出てこない。
`eval` の7ゲート（coverage / dup / level_sep / retry / text_quality / answer_size /
statement_size）はどれも学年を見ない。

## 何を「未習」と決めるか（★列挙せず、台帳から測る）

道具の導入学年は**私が決めない**。`units.generated.yaml` の desc / example を
学年ごとに数え、**その道具が最初に現れる学年**を導入学年とする。
中3の example に32回出て中1・中2に0回なら、√ の導入学年は中3。

見る道具（印）は宣言する。ただし**印の選び方で3回外した**ので、実測を残す:

    「因数分解」  中1に4件 …… すべて **素因数分解**（中1の正の数と負の数）
    「展開」      中1に5件 …… すべて **展開図**（中1の空間図形）
    「²」         中1に10件 … cm²・r²・(-3)²。**中1に `-x²+2x` の値を求める問題が実在する**

包含語をそのまま印にすると、この3つがまるごと誤検出になる。だから印は
**打ち消し付きの正規表現**で宣言し、`--self-test` に「引っかかってはいけない例」を持つ。

★印がどの学年にも一度も出なければ、その印は**死んでいる**（台帳の言い方と合っていない）。
黙って0件を返さないよう、走査の最初に落とす。

実行:
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/check_unit_fit.py [--seeds N]
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/check_unit_fit.py --self-test
"""
from __future__ import annotations

import pathlib
import re
import sys

import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

sys.path.insert(0, "records/work")
from engine_paths import UNITS_YAML  # エンジンの場所は1か所で解決する

_UNITS = UNITS_YAML
_GRADES = ("g1", "g2", "g3")

# 見る道具の印。値は (正規表現, なぜこの書き方か)。
# ★包含語をそのまま印にしない——上の docstring の実測を参照。
_MARKERS: dict[str, tuple[str, str]] = {
    "√": (r"√", "記号そのもの。ほかの語に含まれない"),
    "平方根": (r"平方根", "「平方根」は他の語の一部にならない"),
    "相似": (r"相似", "同上"),
    "三平方": (r"三平方", "同上"),
    "標本": (r"標本", "同上"),
    "連立": (r"連立", "同上"),
    "因数分解": (r"(?<!素)因数分解", "★素因数分解（中1）を外す。付けないと中1が全部鳴る"),
}


# **先取りだが正しい**と判断したもの（理由つきで宣言する。黙って外さない）。
# 鍵は (単元, form, レベル, 印)。★宣言は毎回印字する——見えないところに例外を貯めると、
# 検査があることだけが残って中身が無くなる（`dup_rate_max` と同じ作法）。
_DECLARED: dict[tuple[str, str, int, str], str] = {
    ("g2_l36", "knowledge", 1, "相似"):
        "合同の記号 ≡ を教える解説で、∽ と書き分けさせている。"
        "「形が同じで大きさがちがう」と**その場で定義してから**使っており、"
        "記号の対比は合同の理解を助ける。語を持ち込んでいるのではない。",
}


def _grade_of(unit: str) -> str | None:
    """単元名から学年。入試対策（exam_*）は学年をまたぐので対象外。"""
    head = unit.split("_")[0]
    return head if head in _GRADES else None


def introduced_at(ledger: dict) -> dict[str, str]:
    """印ごとの導入学年を台帳から測る（最初に現れる学年）。"""
    texts: dict[str, list[str]] = {g: [] for g in _GRADES}
    for unit, body in ledger["units"].items():
        grade = _grade_of(unit)
        if grade is None:
            continue
        for fbody in (body.get("forms") or {}).values():
            for lbody in (fbody.get("levels") or {}).values():
                texts[grade] += [str(lbody.get(k, "")) for k in ("desc", "example")]

    out: dict[str, str] = {}
    dead: list[str] = []
    for name, (pattern, _why) in _MARKERS.items():
        rx = re.compile(pattern)
        hits = {g: sum(bool(rx.search(t)) for t in texts[g]) for g in _GRADES}
        first = next((g for g in _GRADES if hits[g]), None)
        if first is None:
            dead.append(f"{name}（どの学年の台帳にも出ない＝印が台帳の言い方と合っていない）")
        else:
            out[name] = first
    if dead:
        raise SystemExit("印が死んでいる:\n  " + "\n  ".join(dead))
    return out


def findings(unit: str, text: str, first_seen: dict[str, str]) -> list[str]:
    """その学年より後で導入される道具が出ていないか。"""
    grade = _grade_of(unit)
    if grade is None:
        return []
    out = []
    for name, intro in first_seen.items():
        if _GRADES.index(intro) <= _GRADES.index(grade):
            continue
        m = re.search(_MARKERS[name][0], text)
        if m:
            i = m.start()
            out.append(
                f"{grade} なのに「{name}」（導入は {intro}）: …{text[max(0, i - 16):i + 16]}…"
            )
    return out


def self_test() -> int:
    """★落ちる側と、引っかかってはいけない側の両方を持つ。"""
    first_seen = {"√": "g3", "相似": "g3", "連立": "g2", "因数分解": "g3"}
    cases = [
        ("中1に √ が出る", "g1_l25", "√2 を含む長さを求めよ。", True),
        ("中3の √ は正しい", "g3_l23", "√2 を含む長さを求めよ。", False),
        ("中1に相似", "g1_l50", "相似な図形の辺の比を求めよ。", True),
        ("中2に連立は正しい", "g2_l16", "連立方程式を解け。", False),
        ("中1に連立", "g1_l25", "連立方程式を解け。", True),
        # ★印の選び方で外した3つ（引っかかってはいけない）
        ("中1の素因数分解", "g1_l11", "504 を素因数分解せよ。", False),
        ("中1の展開図", "g1_l51", "この立体の展開図をかけ。", False),
        ("中1の cm²", "g1_l33", "面積が24cm²の長方形の縦をx cmとする。", False),
    ]
    fails = 0
    for name, unit, text, want in cases:
        got = findings(unit, text, first_seen)
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    if "--self-test" in argv:
        return 1 if self_test() else 0

    ledger = yaml.safe_load(_UNITS.read_text())
    first_seen = introduced_at(ledger)
    print("台帳から測った導入学年: "
          + " / ".join(f"{k}={v}" for k, v in sorted(first_seen.items(), key=lambda kv: kv[1])))

    from build_corpus import load_cells  # noqa: PLC0415

    seeds = int(argv[argv.index("--seeds") + 1]) if "--seeds" in argv else 3
    env = make_env()
    bad: list[str] = []
    cells = skipped = declared_hits = 0
    for unit, form, level, _c, _e, _f in load_cells():
        if _grade_of(unit) is None:
            skipped += 1
            continue
        for seed in range(1, seeds + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            cells += 1
            # ★小問を全部読む（本文だけを見ると、問い・解説に出る道具を落とす）。
            parts = [res.problem_text]
            for sq in res.sub_questions:
                parts += [sq.prompt_text, sq.explanation, *sq.hints]
            for v in findings(unit, "\n".join(parts), first_seen):
                marker = v.split("「")[1].split("」")[0]
                if (unit, form, level, marker) in _DECLARED:
                    declared_hits += 1
                    continue
                bad.append(f"{unit}.{form}.Lv{level} seed{seed}: {v}")

    print(f"見た問題 {cells}（seed 1..{seeds}）／学年をまたぐ入試対策セルは対象外 {skipped}")
    for (u, f, lv, marker), why in _DECLARED.items():
        print(f"宣言（先取りだが正しい）: {u}.{f}.Lv{lv} の「{marker}」— {why}")
    print(f"宣言で通した件数: {declared_hits}"
          + ("  ★宣言が一度も当たっていない＝もう要らないか、印が変わった"
             if _DECLARED and not declared_hits else ""))
    if not cells:
        print("=== 1問も見ていない＝検査が動いていない ===")
        return 1
    if bad:
        print(f"=== 学年で未習の道具 {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== 未習の道具は出ていない ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
