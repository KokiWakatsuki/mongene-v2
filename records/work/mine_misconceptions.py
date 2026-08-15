"""実物の解説資料から**誤答要因**を掘り出す。

## なぜこれが要るか

カリキュラムモデルの中身が空のまま残っている（概念577に対し、前提関係の辺2・
誤答要因3・要因タグ付きのセル 5/630）。配線（要因→戻り先→供給）は動くことを
実測済みだが、中身が無いので UC-2「前提単元へ戻る」が動かない。

**中身は「教育者が入れる共有データ資産」**だが、材料は実在する。
全国学力・学習状況調査の**解説資料**が、問題ごとに「解答類型」を立て、
一つ一つについて「生徒がどう捉えていると考えられるか」を書いている。
これはそのまま誤答要因である。

```
【解答類型６】は、素数と奇数を混同していると考えられる
【解答類型３】は、頂点Ａにおける外角と内角を混同していると考えられる
【解答類型２】は、yの増加量と変化の割合を混同していると考えられる
```

## 取り出すもの

  誤答要因 … 「【解答類型N】は、<これ>と考えられる」の <これ>
  単元     … その類型が属する問題の見出し（「数学 ３ 外角」など）
  正答か   … 類型1は正答であることが多い（◎）。正答の類型は要因ではない

**掘るのは材料であって、そのまま入れる完成品ではない。** 単元との対応づけと、
私たちの概念IDへの割り当ては人が見て決める（教育者の仕事）。ここは下ごしらえ。

実行:
  .venv/bin/python records/work/mine_misconceptions.py            # 一覧
  .venv/bin/python records/work/mine_misconceptions.py --json     # 機械可読で保存
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

_REF = Path("records/work/ref")
_OUT = _REF / "misconceptions.json"

# 「数学 ３ 外角」「数学 ６ 構想を立てて説明し…」のような問題の見出し。
_HEADING = re.compile(r"数学([０-９0-9]{1,2})([ぁ-んァ-ヶ一-龠・（）()、，,]{2,40})")
# 「【解答類型N】は、…と考えられる」
# **句読点は年度で違う。** 令和のものは「、」、平成〜令和3年ごろは「，」（全角カンマ）。
# 「、」だけを見ていたとき、3年度ぶんが**まるごと0件**になった（抽出漏れに気づけたのは
# 「0件」が出たから。0が出たら、まず検査が動いているかを疑う）。
_TYPE = re.compile(r"【解答類型([０-９0-9]+)】は[、，](.{5,120}?)と考えられる")
# 正答の類型は「意味を理解している」「できている」など肯定形で終わることが多い。
_IS_CORRECT = re.compile(r"(理解している|正しく|できている|求めている$)")


def _norm(s: str) -> str:
    return re.sub(r"[ 　\n]+", "", s)


def mine(text: str) -> list[dict]:
    t = _norm(text)
    # 見出しの位置を先に拾い、各類型がどの見出しの配下かを決める
    heads = [(m.start(), m.group(1), m.group(2)) for m in _HEADING.finditer(t)]
    out: list[dict] = []
    for m in _TYPE.finditer(t):
        pos = m.start()
        head = ("", "")
        for hpos, num, name in heads:
            if hpos < pos:
                head = (num, name)
            else:
                break
        cause = m.group(2)
        out.append({
            "問題番号": head[0], "単元": head[1],
            "類型": m.group(1), "要因": cause,
            "正答の類型か": bool(_IS_CORRECT.search(cause)),
        })
    return out


def main() -> int:
    rows: list[dict] = []
    for p in sorted(_REF.glob("*kaisetsu*.txt")):
        got = mine(p.read_text(encoding="utf-8"))
        for g in got:
            g["出典"] = p.stem
        rows += got
        print(f"  {p.stem:<24} {len(got):>3} 類型")

    wrong = [r for r in rows if not r["正答の類型か"]]
    print(f"\n合計 {len(rows)} 類型 / うち誤答の要因 {len(wrong)} 件")

    # 同じ言い回しはまとめる（「AとBを混同している」は年度をまたいで繰り返し出る）
    by_cause = collections.Counter(r["要因"] for r in wrong)
    print(f"言い回しの異なり {len(by_cause)} 種\n")
    print("=== 繰り返し出るもの（＝典型的なつまずき）===")
    for cause, n in by_cause.most_common(12):
        if n >= 2:
            print(f"  {n}回  {cause[:64]}")
    print("\n=== 「混同」型（別の概念と取り違える＝戻り先が決めやすい）===")
    conf = [r for r in wrong if "混同" in r["要因"]]
    for r in conf[:15]:
        print(f"  [{r['単元'][:12]:<12}] {r['要因'][:60]}")
    print(f"  … 計 {len(conf)} 件")

    if "--json" in sys.argv:
        _OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {_OUT} に保存（{len(rows)} 件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
