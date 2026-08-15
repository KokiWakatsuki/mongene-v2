from collections import Counter
from engine.tools.coverage_page import measure
units = measure()
byform = Counter()
rows = []
for u in units:
    miss = [c for c in u.cells if not c.covered]
    if miss:
        for c in miss:
            byform[c.form] += 1
        rows.append((u.grade, u.unit, u.chapter, u.title, miss))
rows.sort(key=lambda r: (r[0], r[2]))
cur = None
for g, uid, ch, title, miss in rows:
    if (g, ch) != cur:
        print(f"\n### {g} / {ch}")
        cur = (g, ch)
    s = " ".join(f"{c.form}:Lv{c.level}" for c in miss)
    print(f"  {uid:10s} {title[:28]:30s} {s}")
print("\n未実装 form 別:", dict(byform), "計", sum(byform.values()))
