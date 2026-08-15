import sys
from engine.tools.coverage_page import measure
kw = sys.argv[1]
for u in measure():
    if kw not in (u.chapter or "") and kw not in u.title and kw not in u.unit:
        continue
    cells = u.cells
    ok = sum(1 for c in cells if c.covered)
    print(f"{u.unit:8s} {u.title[:30]:32s} {ok}/{len(cells)}")
    for c in cells:
        print(f"    {'OK ' if c.covered else '-- '}{c.form:12s} Lv{c.level}")
