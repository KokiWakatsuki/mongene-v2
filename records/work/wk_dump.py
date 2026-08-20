#!/usr/bin/env python3
"""G-WK（世界知識ゲート）の入力を作る — 判定させる問題を、**対照を混ぜて**書き出す。

## なぜ人の目が要っていたか

場面を6つ足したとき、機械検査5つ（G-SC1〜5）を**全部通ったうえで**読み手が4件
見つけた——美術館の「入園料」・遊覧船の「乗車券」・180円切手・大人2500円と
中学生2000円。どれも**数としては解ける**ので、G-BT の値の突き合わせでは出ない。
engine の宣言からも導けない（施設と料金名の対応はどこにも書いていない世界の事実）。

だからここだけは読み手（LLM）が要る。**人の目を外すために要るのは読み手を消すことでは
なく、読み手の出力を機械が判定できる形にすること**。

## 対照を混ぜる（★この検査の要）

読み手が「該当なし」と返したとき、それが
  ①本当に問題が無い  ②読み手が見ていない
のどちらなのかは、実物だけを渡していると区別がつかない。だから
`failure_catalog.yaml` の **`対照: true` の悪い例**（過去に実際に engine が出した文）を
問題群に混ぜ、id を伏せる。**対照を見落とした回の判定は採用しない。**

これは「0件を返す走査は、まず検査が動いているか疑う」を、LLM を含む検査に対して
実装したもの。合成データの自己検査に相当するものが、ここでは対照になる。

## 読み手に渡すもの・渡さないもの

渡す: `records/work/wk/items.md`（問題文と、カタログから作った判定の項目だけ）
渡さない: `records/work/wk/key.json`（どれが対照か）・params・答え・場面のコード

実行:
  # 先に (関係×場面) の全組を作る（G-BT と同じ入力を使う）
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/bt_dump_scenes.py --per 3
  PYTHONPATH=engine_core:records/work .venv/bin/python records/work/wk_dump.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

sys.path.insert(0, "records/work")

_BT = Path("records/work/bt/scenes.json")
_CATALOG = Path("records/work/failure_catalog.yaml")
_OUT = Path("records/work/wk")
# 並べ替えの種は固定する（同じ入力なら同じ並び＝判定を貼り直せる）。
_SHUFFLE_SEED = 20260820


def _checklist(catalog: list[dict]) -> list[tuple[str, str]]:
    """カタログの「種類」を、読み手に渡す判定の項目にする（重複は畳む）。

    ★項目をここで書き足さない。**カタログが唯一の出典**にする——2か所に書くと、
    片方を直しても判定が変わらない（頂点名から I を外す作業で4か所に散っていた）。
    """
    seen: dict[str, str] = {}
    for e in catalog:
        seen.setdefault(str(e["種類"]), str(e["なぜ悪い"]))
    return sorted(seen.items())


def main(argv: list[str]) -> int:
    bootstrap()
    if not _BT.exists():
        print(f"先に bt_dump_scenes.py を回すこと（{_BT} が無い）")
        return 1
    catalog = yaml.safe_load(_CATALOG.read_text())
    rows = json.loads(_BT.read_text())
    env = make_env()

    items: list[dict] = []
    for r in rows:
        res = generate(
            GenerateRequest(subject="math", unit=r["unit"], form=r["form"],
                            level=r["level"], seed=r["seed"]),
            curriculum=env.curriculum, families=env.families, registry=env.registry,
        )
        if isinstance(res, Unsupported):
            continue
        text = res.problem_text.strip()
        asks = " / ".join(
            t for t in (sq.prompt_text or "" for sq in res.sub_questions) if t.strip()
        )
        if asks.strip():
            text += f"\n（問い） {asks.strip()}"
        items.append({"kind": "実物", "source": f"{r['unit']}.{r['form']}."
                                                f"Lv{r['level']}#{r['seed']}", "text": text})

    controls = [e for e in catalog if e.get("対照")]
    for e in controls:
        items.append({"kind": "対照", "source": str(e["id"]),
                      "種類": str(e["種類"]), "text": str(e["悪い例"]).strip()})

    random.Random(_SHUFFLE_SEED).shuffle(items)
    for i, it in enumerate(items, 1):
        it["id"] = f"wk-{i:03d}"

    checklist = _checklist(catalog)
    lines = [
        "# 場面として成り立っているか（世界知識の判定）",
        "",
        "各問について、**問題文だけ**を読み、下の項目に該当するものがあるかを答える。",
        "**数学として解けるかは見ない**（それは別の検査が見ている）。見るのは",
        "「この文が描いている場面が、現実として成り立っているか」だけ。",
        "",
        "## 判定の項目",
        "",
    ]
    for kind, why in checklist:
        lines += [f"- **{kind}** — 例: {why}"]
    lines += [
        "",
        "## 書き方",
        "",
        "`records/work/wk/verdicts.tsv` に、**全問**について1行ずつ書く。",
        "",
        "```",
        "wk-001<TAB>ok",
        "wk-002<TAB>該当<TAB>語の対<TAB>美術館なのに「入園料」（館なら入館料）",
        "```",
        "",
        "該当が無ければ 2 列目を `ok` だけにする。該当があれば",
        "`該当<TAB>項目名<TAB>本文のどこがなぜ悪いか` を書く。**1問も飛ばさない。**",
        "",
        "---",
        "",
    ]
    for it in items:
        lines += [f"## {it['id']}", "", it["text"], ""]

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "items.md").write_text("\n".join(lines), encoding="utf-8")
    (_OUT / "key.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(items)} 問（実物 {len(items) - len(controls)} ＋ 対照 {len(controls)}）"
          f" → {_OUT / 'items.md'}")
    print(f"判定の項目 {len(checklist)} 種類: " + " / ".join(k for k, _ in checklist))
    if not controls:
        print("★対照が0件＝この回の「該当なし」は信用できない（カタログの 対照: true を確認）")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
