"""1セル1seedの生成結果を素で見る。"""
import sys
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

unit, form, lv, seed = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
env = make_env()
req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
res = generate(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
if isinstance(res, Unsupported):
    print("UNSUPPORTED:", res.code, res.detail)
    raise SystemExit(1)
print(res.problem_text)
for sq in res.sub_questions:
    ans = sq.answer
    print(f"--- {sq.label} prompt={sq.prompt_text!r}")
    print(f"    answer: {getattr(ans,'display',None) or ans}")
    print(f"    hints : {sq.hints}")
    print(f"    expl  : {sq.explanation}")
