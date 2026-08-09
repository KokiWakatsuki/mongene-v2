"""図が仮定どおりに描かれているかを、座標で確かめる。

ゲートは「事実が正しく導かれているか」しか見ていない。**図がその事実のとおりに
描かれているか**は誰も見ていないので、「AB ＝ AC ＝ BC である」と書いてあるのに
不等辺三角形が描かれる、といったことが起きる。生徒は図を見て考えるので、これは
解けない問題になる。

ここでやるのは1つだけ:
  構成の facts にある等長・等角・直角を取り出し、**座標から測った実際の長さ・角度**と
  食い違っていないかを見る。

実行: PYTHONPATH=. .venv/bin/python scratchpad/check_figure_matches_givens.py
"""
from __future__ import annotations

import glob
import math

import yaml

from engine.packs.math.geometry import (  # noqa: F401  登録の副作用
    constructions_congruence,
    constructions_right_triangle,
)
from engine.packs.math.recipes.geometry_proof import build_problem

# 相対誤差でこれを超えたら「図が仮定と違う」とみなす。
_LEN_TOL = 0.05      # 5%
_ANG_TOL = 3.0       # 度


def _dist(con, p: str, q: str) -> float:
    (x1, y1), (x2, y2) = con.coords[p], con.coords[q]
    return math.hypot(x2 - x1, y2 - y1)


def _angle(con, a: str, v: str, b: str) -> float:
    (ax, ay), (vx, vy), (bx, by) = con.coords[a], con.coords[v], con.coords[b]
    ux, uy = ax - vx, ay - vy
    wx, wy = bx - vx, by - vy
    nu, nw = math.hypot(ux, uy), math.hypot(wx, wy)
    if nu < 1e-9 or nw < 1e-9:
        return 0.0
    c = max(-1.0, min(1.0, (ux * wx + uy * wy) / (nu * nw)))
    return math.degrees(math.acos(c))


def problems_for(con, facts) -> list[str]:
    out: list[str] = []
    for f in facts:
        if f.kind == "seg_eq":
            (p1, q1), (p2, q2) = f.args
            d1, d2 = _dist(con, p1, q1), _dist(con, p2, q2)
            if max(d1, d2) > 0 and abs(d1 - d2) / max(d1, d2) > _LEN_TOL:
                out.append(
                    f"{p1}{q1}＝{p2}{q2} と書いてあるのに、図では "
                    f"{d1:.2f} と {d2:.2f}（{abs(d1 - d2) / max(d1, d2) * 100:.0f}%ちがう）"
                )
        elif f.kind == "ang_eq":
            # **先頭が頂点**（`facts.ang(vertex, arm1, arm2)`）。
            # (a, v, b) だと思って測ると、正しい図を「食い違っている」と言ってしまう
            # （実際 g2_l49 の ∠BAC＝∠ACB を 114°と33° と誤読した）。
            (v1, a1, b1), (v2, a2, b2) = f.args
            t1, t2 = _angle(con, a1, v1, b1), _angle(con, a2, v2, b2)
            if abs(t1 - t2) > _ANG_TOL:
                out.append(
                    f"∠{a1}{v1}{b1}＝∠{a2}{v2}{b2} と書いてあるのに、図では "
                    f"{t1:.0f}° と {t2:.0f}°"
                )
        elif f.kind == "perp":
            try:
                (p, q), (r, s) = f.args
            except ValueError:
                continue
            shared = ({p, q} & {r, s})
            if len(shared) != 1:
                continue
            v = shared.pop()
            a = q if p == v else p
            b = s if r == v else r
            t = _angle(con, a, v, b)
            if abs(t - 90.0) > _ANG_TOL:
                out.append(f"{p}{q} ⊥ {r}{s} と書いてあるのに、図では ∠{a}{v}{b}＝{t:.0f}°")
    return out


def main() -> None:
    bad = 0
    checked = 0
    for path in sorted(glob.glob("engine/curriculum/math/families/*.proof.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit = doc["family"].removeprefix("math.").removesuffix(".proof")
        for lv, spec in (doc.get("levels") or {}).items():
            p = spec.get("params") or {}
            kind = p.get("construction")
            if not kind:
                continue   # 図を作らないセル（文字式の説明・三平方など）
            # recipe と同じ引き方（`recipes/geometry_proof.py:158`）。
            # 範囲の端と真ん中を当たれば、極端な形も普通の形も見られる。
            def span(dom: dict) -> list[int]:
                lo, hi = dom["int_range"]
                return sorted({lo, (lo + hi) // 2, hi})

            shown = False
            for base in span(p["base_domain"]):
                for angle in span(p["angle_domain"]):
                    for offset in span(p["offset_domain"]):
                        params = {
                            "base": base / 10.0, "angle": angle, "offset": offset / 10.0
                        }
                        built = build_problem(
                            kind, params, level=int(lv),
                            topic_set=str(p.get("topic_set") or "congruence"),
                            exclude_rules=tuple(
                                str(x) for x in p.get("exclude_rules", ())
                            ),
                            depth=(
                                int(p["proof_depth"])
                                if p.get("proof_depth") is not None else None
                            ),
                            prefer=str(p["prefer"]) if p.get("prefer") else None,
                        )
                        if built is None:
                            continue
                        con = built[0]
                        checked += 1
                        issues = problems_for(con, getattr(con, "givens", []) or [])
                        if issues and not shown:
                            bad += 1
                            shown = True
                            print(
                                f"■ {unit}.proof.Lv{lv} "
                                f"(base={base / 10}, angle={angle}, offset={offset / 10})"
                            )
                            for i in issues:
                                print(f"    {i}")
    print(f"\n調べた図 {checked} / 仮定と食い違う図 {bad}")


if __name__ == "__main__":
    main()
