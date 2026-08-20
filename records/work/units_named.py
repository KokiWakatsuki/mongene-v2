"""生成できるセルを「単元名つき」で一覧にする。

★API の `/units` は ID（g1_l25）しか返さないので、これだけでは何の単元か分からない。
名前は台帳（units.generated.yaml）にある。引数で絞れる。

    python units_named.py            # 全部
    python units_named.py 一次方程式  # 章の名前や単元名で絞る
    python units_named.py g1_l25     # ID で絞る
"""
import sys
import yaml
from engine_paths import UNITS_YAML

kw = sys.argv[1] if len(sys.argv) > 1 else ""
doc = yaml.safe_load(UNITS_YAML.read_text())
units = doc["units"] if "units" in doc else doc

n = 0
for uid, u in units.items():
    blob = f"{uid} {u.get('section','')} {u.get('title','')}"
    if kw and kw not in blob:
        continue
    forms = {f: sorted(int(k) for k in v["levels"]) for f, v in u.get("forms", {}).items()}
    print(f"{uid:9} {u.get('section',''):32} {u.get('title','')}")
    for f, lvs in forms.items():
        d = u["forms"][f]["levels"]
        for lv in lvs:
            print(f"          └ {f:13} Lv{lv}  {d[str(lv)].get('desc','')}")
    n += 1
print(f"\n{n} 単元" + (f"（絞り込み: {kw!r}）" if kw else ""))
