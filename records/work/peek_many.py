"""複数セルを一度に素で見る。

  PYTHONPATH=engine_core .venv/bin/python records/work/peek_many.py [--seeds N] unit.form.Lv ...
"""
import sys

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

args = sys.argv[1:]
seeds = 1
if args and args[0] == "--seeds":
    seeds = int(args[1])
    args = args[2:]

env = make_env()
for spec in args:
    unit, form, lv = spec.rsplit(".", 2)
    lv = int(lv.lstrip("Lv"))
    for seed in range(1, seeds + 1):
        print(f"\n================ {unit}.{form}.Lv{lv} seed={seed}")
        req = GenerateRequest(subject="math", unit=unit, form=form, level=lv, seed=seed)
        res = generate(req, curriculum=env.curriculum, families=env.families, registry=env.registry)
        if isinstance(res, Unsupported):
            print("UNSUPPORTED:", res.code, res.detail)
            continue
        print(res.problem_text)
        for sq in res.sub_questions:
            ans = sq.answer
            print(f"--- {sq.label} prompt={sq.prompt_text!r}")
            print(f"    answer: {getattr(ans, 'display', None) or ans}")
            for h in sq.hints:
                print(f"    hint  : {h}")
            for st in sq.solution_steps:
                print(f"    step[{st.op}] {st.result_display!r} :: {st.narration}")
            print(f"    expl  : {sq.explanation}")
