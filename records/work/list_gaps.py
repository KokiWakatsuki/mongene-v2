"""未実装セルを unit/form/level で列挙。引数で unit 接頭辞フィルタ。"""
import sys, yaml
from pathlib import Path
from engine.bootstrap import bootstrap
from engine.core.pipeline import capabilities
from engine.tools.goal_progress import _UNITS_PATH

bootstrap()
caps = {(c.unit, c.form, c.level) for c in capabilities()}
doc = yaml.safe_load(Path(_UNITS_PATH).read_text())
pref = sys.argv[1] if len(sys.argv) > 1 else ""
rows = []
for uid, u in doc["units"].items():
    if pref and not uid.startswith(pref):
        continue
    for form, fdef in (u.get("forms") or {}).items():
        for lv in (fdef.get("levels") or {}):
            if (uid, form, int(lv)) not in caps:
                rows.append((uid, u.get("title", ""), form, int(lv)))
rows.sort()
for r in rows:
    print(f"{r[0]:<10} {r[2]:<14} Lv{r[3]}  {r[1]}")
print(f"--- {len(rows)} cells ---")
