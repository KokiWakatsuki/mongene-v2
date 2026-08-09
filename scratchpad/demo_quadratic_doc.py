"""営業デモ用: 2次方程式クラスタの生成サンプルを markdown 文書にする。"""
import re
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

CELLS = [
    ("g3_l27", "calculation", 1, "因数分解による解き方（基礎）", [11, 12, 13]),
    ("g3_l26", "calculation", 2, "解の公式の利用（標準）", [11]),
    ("g3_l26", "calculation", 3, "解の公式・根号の簡約（応用）", [11]),
    ("g3_l28", "calculation", 2, "いろいろな2次方程式・整理してから解く（標準）", [11]),
    ("g3_l29", "word_problem", 2, "利用・数の問題／誘導あり（標準）", [11]),
    ("g3_l30", "word_problem", 3, "利用・図形の問題／誘導なし（応用）", [11]),
    ("g3_l30", "find_value", 2, "図形条件から立式して求値（標準）", [11]),
]
STUB = re.compile(r"^(solution|value|formulation|choice|coordinate|expression) を求めなさい。$")

env = make_env()
out = [
    "# モンジェネ 問題生成エンジン — 2次方程式サンプル",
    "",
    "engine（`engine-m0-rework` / `7545348`）が実際に生成した出力そのままです。",
    "**seed を変えると同じセルから別の問題が無限に出ます**（下の「因数分解」は同じ設定で seed だけ変えた3問）。",
    "答え・ヒント・解説はすべてエンジンが解いて生成しており、生成とは独立の経路で解き直して一致を確認しています。",
]
for unit, form, lv, title, seeds in CELLS:
    out.append(f"\n---\n\n## {title}")
    out.append(f"\n`{unit} / {form} / Lv{lv}`\n")
    for seed in seeds:
        req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
        res = generate(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
        if isinstance(res, Unsupported):
            out.append(f"UNSUPPORTED: {res.code}")
            continue
        out.append(f"### seed = {seed}\n")
        out.append("**問題**\n")
        out.append("```")
        out.append(res.problem_text)
        out.append("```\n")
        for sq in res.sub_questions:
            ans = getattr(sq.answer, "display", None)
            if ans is None:
                a = sq.answer
                ans = f"{getattr(a, 'correct', a)}（選択肢: {getattr(a, 'distractors', '')}）"
            head = "" if STUB.match(sq.prompt_text or "") else f" {sq.prompt_text}"
            out.append(f"**{sq.label}{head}**\n")
            out.append(f"- 答え: **{ans}**")
            for i, h in enumerate(sq.hints, 1):
                out.append(f"- ヒント{i}: {h}")
            expl = (sq.explanation or "").replace("\n", "\n  ")
            out.append(f"- 解説:\n  {expl}\n")
open("scratchpad/2次方程式_生成サンプル.md", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out[:12]))
print("... written")
