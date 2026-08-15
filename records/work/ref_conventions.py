"""実物の教材から**表記の慣習だけ**を数える。

## なぜ「慣習だけ」か

私たちが知りたいのは「市販品はどう書くか」であって、他社の問題そのものではない。
問題文は他人の著作物なので**貯めない**。数えた結果（頻度）と、根拠として要る
ごく短い一文だけを残す。慣習（文末を敬体にする・点名は全角、など）は事実であって
著作物ではないので、これは規範として自由に使える。

## なぜ出典を散らすか

同じ出典を大量に集めると、その出典の癖に寄る。全国学力調査だけを見れば
「学力調査の体裁」が、入試だけを見れば「入試の体裁」が一般だと錯覚する。
**複数系統で共通するものだけを慣習として採る。**

系統（増えたら足す。**混ぜない**——混ぜると系統ごとの差が消える）:
  chousa   … 全国学力・学習状況調査（国立教育政策研究所）
  nyushi   … 公立高校入試（都道府県教育委員会）
  kyokasho … 教科書会社の練習プリント・内容解説
  kyoiku   … 教育委員会が配る補充プリント
  market   … 無料プリント配布サイト
  cram     … 塾・解説サイト

実行:
  # 1つのテキストを測る
  .venv/bin/python records/work/ref_conventions.py records/work/ref/<file>.txt
  # ref/ 以下を全部измеり、系統ごとに集計
  .venv/bin/python records/work/ref_conventions.py --all
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

_REF = Path("records/work/ref")

# 出典の系統。ファイル名の接頭辞で決める（`nier_*` → official）。
# **入試と学力調査は分ける。** 同じ「公的」でも体裁が違いうる（入試は市販問題集の
# 手本になっているので、market 寄りの可能性がある）。混ぜると差が見えなくなる。
_LINEAGE = {
    "nier": "chousa",       # 全国学力・学習状況調査
    "pref": "nyushi",       # 公立高校入試（都道府県）
    "kyoiku": "kyoiku",     # 教育委員会が配る補充プリント
    "kyokasho": "kyokasho", # 教科書会社の練習プリント・内容解説
    "market": "market", "startoo": "market", "okadori": "market",
    "005net": "market", "chibimusu": "market", "mathfree": "market",
    "juku": "cram", "morijuku": "cram", "eboard": "cram", "yorikuwa": "cram",
}

_ASK_KEITAI = ("求めなさい", "答えなさい", "表しなさい", "かきなさい", "書きなさい",
               "示しなさい", "選びなさい", "説明しなさい", "求めましょう")
_ASK_JOTAI = ("求めよ", "答えよ", "表せ", "かけ", "示せ", "選べ", "説明せよ")
_FIG_REF = ("下の図", "右の図", "上の図", "次の図", "左の図", "下の表", "右の表", "図のように")
_SYMBOLS = ("∠", "△", "∥", "≡", "∽", "⊥", "°", "π", "√", "㎠", "㎤", "≦", "≧")


def measure(text: str) -> dict:
    """字間のスペースを詰めてから数える（PDF由来のテキストは1字ずつ空く）。"""
    t = re.sub(r"[ 　\t]+", "", text)
    keitai = {k: t.count(k) for k in _ASK_KEITAI if t.count(k)}
    jotai = {k: t.count(k) for k in _ASK_JOTAI if t.count(k)}
    return {
        "文字数": len(t),
        "文末_敬体": keitai, "文末_敬体_計": sum(keitai.values()),
        "文末_常体": jotai, "文末_常体_計": sum(jotai.values()),
        "図への参照": {k: t.count(k) for k in _FIG_REF if t.count(k)},
        "記号": {k: t.count(k) for k in _SYMBOLS if t.count(k)},
        "点名_全角": len(re.findall(r"[Ａ-Ｚ]", t)),
        "点名_半角": len(re.findall(r"(?<![A-Za-z])[A-Z](?![a-z])", t)),
        "単位を括弧に入れる": len(re.findall(r"[）)]\s*$|（[ｃｍ度個円本枚人分秒ｍＬ]+）", t, re.M)),
        "証明の接続": {k: t.count(k) for k in ("よって、", "したがって、", "ゆえに、", "であるから、", "より、")
                       if t.count(k)},
        "事実の番号": {k: len(re.findall(re.escape(k) + r"[①-⑨]", t))
                      for k in ("……", "…", "・・・") if re.search(re.escape(k) + r"[①-⑨]", t)},
    }


def _lineage(name: str) -> str:
    for prefix, lin in _LINEAGE.items():
        if name.startswith(prefix):
            return lin
    return "unknown"


def main() -> int:
    if "--all" not in sys.argv:
        p = Path(sys.argv[1])
        print(json.dumps(measure(p.read_text(encoding="utf-8")), ensure_ascii=False, indent=1))
        return 0

    per_lineage: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    files: list[tuple[str, str, dict]] = []
    for p in sorted(_REF.glob("*.txt")):
        m = measure(p.read_text(encoding="utf-8"))
        lin = _lineage(p.name)
        files.append((p.name, lin, m))
        per_lineage[lin]["文末_敬体"] += m["文末_敬体_計"]
        per_lineage[lin]["文末_常体"] += m["文末_常体_計"]
        per_lineage[lin]["点名_全角"] += m["点名_全角"]
        per_lineage[lin]["点名_半角"] += m["点名_半角"]
        per_lineage[lin]["文字数"] += m["文字数"]

    print(f"{'出典':<34}{'系統':<10}{'敬体':>6}{'常体':>6}{'全角':>7}{'半角':>7}")
    for name, lin, m in files:
        print(f"{name[:33]:<34}{lin:<10}{m['文末_敬体_計']:>6}{m['文末_常体_計']:>6}"
              f"{m['点名_全角']:>7}{m['点名_半角']:>7}")
    print()
    print(f"{'系統':<12}{'敬体':>7}{'常体':>7}{'敬体率':>8}{'全角':>8}{'半角':>8}{'全角率':>8}")
    for lin, c in sorted(per_lineage.items()):
        ask = c["文末_敬体"] + c["文末_常体"]
        name_n = c["点名_全角"] + c["点名_半角"]
        print(f"{lin:<12}{c['文末_敬体']:>7}{c['文末_常体']:>7}"
              f"{(c['文末_敬体'] / ask if ask else 0):>7.0%}"
              f"{c['点名_全角']:>8}{c['点名_半角']:>8}"
              f"{(c['点名_全角'] / name_n if name_n else 0):>7.0%}")
    (_REF / "conventions.json").write_text(
        json.dumps({n: m for n, _, m in files}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ records/work/ref/conventions.json に測定値を保存（{len(files)} 出典）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
