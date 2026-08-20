"""「理由とともに答えよ」と問うているのに、答えが結論だけになっていないかを数える。

## なぜ要るか

`g1_l41.knowledge.Lv1` は「その理由となる性質の名前とともに答えよ」と問いながら、
答えが「等しい」だけだった（求められたものの半分しか返していない）。
入力仕様（`units.generated.yaml`）には「理由とともに」「根拠とともに」を求める
example が10件あり、**同じ形の取りこぼしが他にもあるはず**という読みで作った。

## 判定

問題文が理由を求めていて、答えに理由らしい語（から・ので・より・性質・条件・
ため）がひとつも無ければ挙げる。**語の一覧で測るので取りこぼしはある**——
挙がったものを人が読んで決める道具であって、0 件を合格の根拠にはしない。

## 使い方

    .venv/bin/python records/work/scan_reason_asked.py
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict

from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, make_env

#: 問いが理由を求めている印。
#: ★言い回しを1つ落とすと、そのぶん丸ごと見えなくなる。「理由を考えたうえで」を
#: 入れていなかったので g3_l57 / g3_l58 の word_problem 26型を取りこぼしていた。
_ASKS_REASON = re.compile(
    r"理由とともに|根拠とともに|理由となる[^。]*とともに"
    r"|理由を(?:あわせて|合わせて|考えたうえで|考えた上で|つけて|添えて)"
    r"|根拠を(?:あげて|挙げて|つけて|示して)"
)
#: 答えに理由が入っている印。
#: 末尾の `[ぁ-ん]く、` は「偏りが生じにく**く、**適切といえる」の形
#: ——理由の節を先に置いて結論につなぐ書き方で、`から`・`ので` が出てこない。
#: これを入れる前は g3_l58 を偽陽性で挙げていた。
_HAS_REASON = re.compile(r"から|ので|より|性質|条件|ため|わけ|なぜ|[ぁ-ん]く、")


def _answer_text(answer: object) -> str:
    """答えの本文。**ProofAnswer は `display` が None・本文は `text`。**"""
    return (
        getattr(answer, "display", None)
        or getattr(answer, "text", None)
        or str(getattr(answer, "correct", "") or "")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    args = ap.parse_args()

    env = make_env()
    asked = 0
    missing: dict[str, str] = {}
    per_cell: dict[str, int] = defaultdict(int)

    for coord in capability_cells(env):
        assert isinstance(coord, Coordinate)
        for seed in range(1, args.seeds + 1):
            res = generate(
                GenerateRequest(
                    subject=coord.subject, unit=coord.unit, form=coord.form,
                    level=coord.level, seed=seed,
                ),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            if not _ASKS_REASON.search(res.problem_text):
                continue
            asked += 1
            cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
            per_cell[cell] += 1
            for sq in res.sub_questions:
                text = _answer_text(sq.answer)
                if text and not _HAS_REASON.search(text):
                    missing.setdefault(cell, text)

    # **0 件を信じる前に、そもそも何件が対象だったかを出す。**
    print(f"理由を求めている問題: {asked} 件 / {len(per_cell)} セル")
    print(f"■ 答えに理由が入っていない: {len(missing)} セル")
    for cell, text in sorted(missing.items()):
        print(f"    {cell}  答え「{text[:60]}」")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
