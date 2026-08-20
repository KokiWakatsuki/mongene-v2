import sys

import yaml
from engine_paths import UNITS_YAML  # エンジンの場所は1か所で解決する

doc = yaml.safe_load(open(UNITS_YAML, encoding="utf-8"))
units = doc["units"]
for uid in sys.argv[1:]:
    u = units[uid]
    print(f"=== {uid} {u.get('title')} / {u.get('section')}")
    if u.get("notes"):
        print(f"    notes: {u['notes']}")
    for form, fd in (u.get("forms") or {}).items():
        print(f"  -- form={form}  rationale={fd.get('rationale')}")
        for lv, c in (fd.get("levels") or {}).items():
            print(f"     [Lv{lv} {c.get('band')}] {c.get('desc')}")
            if c.get("example"):
                print(f"        ex: {c.get('example')}")
            if c.get("market_ref"):
                print(f"        ref: {c.get('market_ref')}")
