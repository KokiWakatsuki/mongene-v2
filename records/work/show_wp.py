import sys
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

env = make_env()
unit, form, lv, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
shown = 0
for seed in range(1, 400):
    res = generate(GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed),
                   curriculum=env.curriculum, families=env.families, registry=env.registry)
    if isinstance(res, Unsupported):
        continue
    print(f"--- seed={seed} ---")
    print(res.problem_text)
    for sq in res.sub_questions:
        ans = sq.answer
        print(f"  [{sq.label}] 答: {getattr(ans,'display',None) or getattr(ans,'correct',ans)}")
        for h in sq.hints:
            print(f"     hint: {h}")
        print(f"     解説: {sq.explanation}")
    shown += 1
    if shown >= n:
        break
