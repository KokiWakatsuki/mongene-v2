"""営業デモ用: 2次方程式クラスタの生成サンプルを markdown で出す。"""
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

CELLS = [
    ("g3_l27", "calculation", 1, "因数分解による解き方", [11, 12]),
    ("g3_l26", "calculation", 2, "解の公式の利用", [11]),
    ("g3_l26", "calculation", 3, "解の公式（根号の簡約）", [11]),
    ("g3_l28", "calculation", 2, "いろいろな2次方程式（整理してから解く）", [11]),
    ("g3_l29", "word_problem", 2, "利用・数の問題（誘導あり）", [11]),
    ("g3_l30", "word_problem", 3, "利用・図形の問題（誘導なし）", [11]),
    ("g3_l30", "find_value", 2, "図形条件から立式して求値", [11]),
    ("g3_l26", "knowledge", 1, "a,b,c の対応（知識）", [11]),
]
env = make_env()
out = []
for unit, form, lv, title, seeds in CELLS:
    for seed in seeds:
        req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
        res = generate(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
        out.append(f"\n## {title}  〔{unit} / {form} / Lv{lv} / seed={seed}〕")
        if isinstance(res, Unsupported):
            out.append(f"UNSUPPORTED: {res.code} {res.detail}")
            continue
        out.append("\n**問題**\n")
        out.append(res.problem_text)
        for sq in res.sub_questions:
            ans = getattr(sq.answer, "display", None) or sq.answer
            out.append(f"\n- {sq.label} {sq.prompt_text}")
            out.append(f"  - **答え**: {ans}")
            if sq.hints:
                out.append(f"  - ヒント: {' / '.join(sq.hints)}")
            out.append(f"  - 解説: {sq.explanation}")
print("\n".join(out))
