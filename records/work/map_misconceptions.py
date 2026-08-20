"""掘り出した誤答要因を、**私たちの単元・概念に突き合わせる**。

`mine_misconceptions.py` が実物の解説資料から取り出した要因（101件）は、
そのままでは私たちの台帳に載らない。載せるには2つ決める必要がある:

  ① どの単元のものか   … 実物の見出し（「外角」「相対度数」）→ 私たちの unit（g2_l35 等）
  ② 戻り先はどこか     … 「AとBを混同」なら B の単元へ戻す

**ここでやるのは①の候補出しまで。** ②と最終的な採否は教育者が決める
（設計上、カリキュラムモデルの中身は共有データ資産で、エンジンの仕事ではない）。
機械が勝手に埋めると「誰も検証していないカリキュラムモデル」ができる。

## 突き合わせ方

実物の見出し（「外角」「相対度数」「資料の散らばりと代表値」）と、
私たちの単元の `desc` / 概念の `label` を**語で照合**する。完全一致は狙わない。
候補を出して、人が見て選ぶ形にする。

実行: .venv/bin/python records/work/map_misconceptions.py [--json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml
from engine_paths import CURRICULUM_DIR  # エンジンの場所は1か所で解決する

_ROOT = CURRICULUM_DIR
_REF = Path("records/work/ref")

# 照合に使わない語（どの単元にも出るので手がかりにならない）
_STOP = set("こと もの ため場合 とき 問題 数学 考察 判断 表現 説明 求める 用いる 使う "
            "統合 発展 構想 日常 事象 について における 関する 捉え 理解".split())


def _words(s: str) -> set[str]:
    """照合用の語。2文字以上の漢字・カタカナのかたまりを拾う。"""
    return {w for w in re.findall(r"[一-龠]{2,}|[ァ-ヶー]{3,}", s) if w not in _STOP}


def main() -> int:
    mis = json.loads((_REF / "misconceptions.json").read_text(encoding="utf-8"))
    wrong = [m for m in mis if not m["正答の類型か"]]

    units = yaml.safe_load((_ROOT / "units.generated.yaml").read_text(encoding="utf-8"))["units"]
    # 単元 → 説明文（forms/levels の desc を全部つなぐ）
    unit_text: dict[str, str] = {}
    for uid, u in units.items():
        parts = []
        for f in (u.get("forms") or {}).values():
            for lv in (f.get("levels") or {}).values():
                parts.append(str(lv.get("desc", "")))
        unit_text[uid] = " ".join(parts)

    concepts = yaml.safe_load((_ROOT / "concepts.yaml").read_text(encoding="utf-8"))["concepts"]
    by_unit: dict[str, list[dict]] = {}
    for c in concepts:
        by_unit.setdefault(c.get("unit", ""), []).append(c)

    rows = []
    for m in wrong:
        key = _words(m["単元"]) | _words(m["要因"])
        scored = []
        for uid, txt in unit_text.items():
            hit = key & _words(txt)
            if hit:
                scored.append((len(hit), uid, sorted(hit)))
        scored.sort(reverse=True)
        top = scored[:3]
        rows.append({
            "要因": m["要因"], "実物の単元": m["単元"], "出典": m["出典"],
            "候補": [{"unit": uid, "一致語": hit,
                      "概念": [c["id"] for c in by_unit.get(uid, [])][:3]} for _, uid, hit in top],
        })

    matched = [r for r in rows if r["候補"]]
    strong = [r for r in matched if len(r["候補"][0]["一致語"]) >= 2]
    weak = [r for r in matched if len(r["候補"][0]["一致語"]) == 1]

    # **「候補が付いた率」を「当たった率」と読ませない。**
    # 語が1つ重なっただけで候補は付く。目で見たら、1語だけのものは
    # 「素数と奇数を混同」が統計の単元に付くなど、ほとんど外れていた。
    print(f"誤答要因 {len(wrong)} 件")
    print(f"  一致語2語以上（見る価値がある） {len(strong):>3} 件 "
          f"({len(strong)/len(wrong):.0%})")
    print(f"  一致語1語だけ（当てにならない） {len(weak):>3} 件 "
          f"— 目視では大半が外れ")
    print(f"  候補ゼロ                    {len(wrong)-len(matched):>3} 件\n")

    print("=== 一致語2語以上のもの（人が見る対象）===")
    for r in strong:
        c = r["候補"][0]
        print(f"  {c['unit']:<9} ← {r['要因'][:50]}")
        print(f"            語 {','.join(c['一致語'][:4])}  概念 {c['概念'][:2]}")

    if "--json" in sys.argv:
        out = _REF / "misconception_candidates.json"
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n→ {out} に保存")
    return 0


if __name__ == "__main__":
    sys.exit(main())
