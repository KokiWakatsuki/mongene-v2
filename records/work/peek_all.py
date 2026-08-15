import sys
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

env = make_env()
cells = [(a.split(':')[0], int(a.split(':')[1])) for a in sys.argv[1:]]
for unit, lv in cells:
    for seed in (1, 3):
        req = GenerateRequest(subject="math", unit=unit, form="word_problem", level=lv, seed=seed)
        res = generate(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
        print(f"\n===== {unit}.Lv{lv} seed{seed}")
        if isinstance(res, Unsupported):
            print("  UNSUPPORTED:", res.code, res.detail); continue
        print(res.problem_text)
        for sq in res.sub_questions:
            print(f"  {sq.label} 答え: {getattr(sq.answer,'display',None)}")
            print(f"      hints: {sq.hints}")
            print(f"      expl : {sq.explanation}")
