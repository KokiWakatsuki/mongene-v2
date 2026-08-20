"""解説の手（Step）の括弧に**値が入っているか**を、MR から直接走査する（面③）。

`scan_explanations.py` は書き上がった解説文から測る。文からでは「括弧が無い手」と
「複数文の narration」を区別できないので、こちらは **MR の Step そのもの**を見る。

判定は3つ:

  空          `result_display` が空 → 括弧なしの行になる
  言い直し     `result_display` が `narration` の言い直し（文字の重なり 0.9 以上）
  値なし       `result_display` に数字も記号（= < > ≡ ∥ ° √）も無い

出力は **op（ソルバ演算名）ごと**。直す単位が solver なので、op で括らないと
どこを直せばよいか分からない。

実行:
    PYTHONPATH=engine_core .venv/bin/python records/work/scan_step_values.py [--seeds N]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict

from engine.eval._harness import build_mr, capability_cells, make_env
from engine_paths import PACKS_DIR  # エンジンの場所は1か所で解決する

_HAS_VALUE = re.compile(r"[0-9=<>≦≧≡∥°√±×÷∠△]")

# 括弧が**指示のまま**になっている手。「〜を読み取る」「〜する」で終わるのは、
# その手で得たものではなく、その手でやることの言い直し。
# 名詞で終わるもの（`整数`・`錯角`・`点Cを中心とする弧`）は結果なので落とさない
# ——用語を答える手・図をかく手では、名詞こそが得たもの。
# **句点で終わる括弧は見ない。** 証明の文（`c、n を整数とする。`・`…正方形をつくる。`）は
# 括弧に入るのが正しく、動詞で終わる。指示の言い直しは句点を付けない書き方なので、
# 「。で終わらない」を条件に足すと証明文だけを外せる。
# **紛らわしい語尾は入れない。** 「条件を満たす」「同じ機会になる」「垂直に交わる」は
# どれも**その手で分かったこと**で、指示ではない。`たす`（満たす）・`なる`・`わる`（交わる）
# を入れていたせいで、直したあとの正しい括弧まで挙がっていた。
_INSTRUCTION_TAIL = re.compile(
    r"(する|読み取る|読みとる|読む|よむ|求める|考える|数える|数え上げる|比べる|見比べる|"
    r"そろえる|もどす|わける|分ける|使う|調べる|作る|つくる|当てはめる|あてはめる|"
    r"確かめる|たしかめる|決める|きめる|選ぶ|えらぶ|示す|しめす|まとめる|見分ける|"
    r"見つける|書き出す|かき出す|結ぶ|打つ|ひく|引く)$"
)


def _overlap(a: str, b: str) -> float:
    if not b:
        return 0.0
    ca, cb = Counter(a), Counter(b)
    return sum(min(cb[ch], ca[ch]) for ch in cb) / len(b)


# 「問題を読み取る／見分ける」だけの手には、計算した値が無い。**括弧は空でよい**
# （空なら「まず、〜を読み取る。」という文だけが出る）。言い直しを入れるより読みやすい。
_ORIENTING = re.compile(
    r"(読み取る|読みとる|見分ける|見比べる|確かめる|思い出す|見つける|考える|はっきりさせる)。?$"
)


def classify(narration: str, result_display: str) -> str | None:
    """この手の括弧の状態。問題なければ None。"""
    r = result_display.strip()
    if not r:
        return None if _ORIENTING.search(narration.strip()) else "空"
    # **指示の語尾を先に見る。** 値の有無で先に通すと、`2つの項の文字の部分を比べる`
    # のように**数字を含む指示文**が素通りしていた（コーパス側の走査が拾って発覚）。
    if not _INSTRUCTION_TAIL.search(r):
        if _HAS_VALUE.search(r):
            return None
        # 名詞で終わる括弧は**その手で得たもの**（`整数`・`錯角`・`閉じていない`・
        # `点Cを中心とする弧`）。値が無くてもこれは正しい。
        return None
    n = re.sub(r"^(まず|次に|最後に|さらに)、", "", narration.strip())
    return "言い直し" if _overlap(n, r) >= 0.9 else "指示形"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=2)
    ap.add_argument("--op", default="", help="この op だけを詳しく出す")
    args = ap.parse_args()

    env = make_env()
    cells = capability_cells(env)
    per_op: dict[str, Counter] = defaultdict(Counter)
    examples: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
    total_steps = 0
    bad_cells: dict[str, set[str]] = defaultdict(set)

    for coord in cells:
        for seed in range(1, args.seeds + 1):
            res = build_mr(coord, seed, env)
            if not res.ok:
                continue
            for sq in res.mr.sub_questions:
                # **最後の手は答えそのもの**なので見ない（「全員に聞いて比べる」の
                # ような答えは動詞で終わるが、指示の言い直しではない）。
                for st in sq.steps[:-1]:
                    total_steps += 1
                    verdict = classify(st.narration, st.result_display)
                    per_op[st.op][verdict or "ok"] += 1
                    if verdict:
                        cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
                        bad_cells[st.op].add(cell)
                        if len(examples[(st.op, verdict)]) < 3:
                            examples[(st.op, verdict)].append(
                                (cell, st.narration, st.result_display)
                            )

    # op が書かれているファイル（直す単位）。同じ op 名が複数ファイルに出ることがある。
    from pathlib import Path
    src_of: dict[str, list[str]] = defaultdict(list)
    for p in sorted(PACKS_DIR.rglob("*.py")):
        txt = p.read_text(encoding="utf-8")
        for op in per_op:
            if f'"{op}"' in txt or f"'{op}'" in txt:
                src_of[op].append(p.name)

    rows = []
    for op, c in per_op.items():
        bad = sum(v for k, v in c.items() if k != "ok")
        if bad:
            rows.append((bad, op, c))
    rows.sort(reverse=True)

    n_bad = sum(r[0] for r in rows)
    print(f"走査 {len(cells)} セル × {args.seeds} seed / 手 {total_steps} 個")
    print(f"括弧に値が入っていない手 {n_bad} 個 / op {len(rows)} 個\n")

    for bad, op, c in rows:
        if args.op and args.op != op:
            continue
        detail = "・".join(f"{k}{v}" for k, v in sorted(c.items()) if k != "ok")
        where = ",".join(src_of.get(op, [])) or "?"
        print(f"■ {op}  [{where}]: {bad}手（{detail}）ok{c['ok']} / {len(bad_cells[op])}セル")
        for verdict in ("空", "言い直し", "指示形"):
            for cell, nar, disp in examples.get((op, verdict), []):
                print(f"    [{verdict}] {cell}")
                print(f"        narration      {nar[:70]}")
                print(f"        result_display {disp[:70]!r}")
        if args.op:
            print("    --- 該当セル ---")
            for cell in sorted(bad_cells[op]):
                print("   ", cell)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
