import yaml
from engine.tools.coverage_page import measure
from engine_paths import UNITS_YAML  # エンジンの場所は1か所で解決する
units = {u.unit: u for u in measure()}
doc = yaml.safe_load(open(UNITS_YAML, encoding="utf-8"))
rows = []
for uid, u in units.items():
    miss = [c for c in u.cells if c.form == "word_problem" and not c.covered]
    if miss:
        rows.append((u.grade, uid, u.chapter, u.title, [c.level for c in miss]))
rows.sort(key=lambda r: (r[0], r[2]))
cur = None
for g, uid, ch, title, lv in rows:
    key = (g, ch)
    if key != cur:
        print(f"\n### {g} / {ch}")
        cur = key
    print(f"  {uid:10s} {title:32s} Lv{lv}")
print("\n未実装 word_problem セル数:", sum(len(r[4]) for r in rows))
