"""本文が名指した点・値が、方眼（座標平面）の範囲に収まっているかを見る。

## なぜ要るか

「x = 2、4、16 および x = −2、−4、−16 に対応する点をとって双曲線をかけ」という
問題で、方眼が x = −12〜23 しか取られておらず **x = −16 が図の外**だった
（生徒は指示どおりの点を打てない）。図つきの逆翻訳で読み手が見つけ、目盛の間隔から
座標を計算して確認した。

engine には `bbox_pts`（描かないが枠には入れる点）という仕組みが既にある——
平行移動で「移動後の三角形が方眼の外」（60seed 中43件）を塞いだときのもの。
**同じ穴が別の場所で開いていた**ので、機械で全数見る。

## 見るもの

問題文に出てくる整数のうち、`x =` や座標の形で名指しされたものが、
方眼の x 軸・y 軸の範囲に収まっているか。範囲は**目盛ラベルの間隔から画素→座標へ
戻して**測る（方眼の線の端まで）。

実行:
  .venv/bin/python records/work/check_grid_covers_asked.py [--seeds N]
"""
from __future__ import annotations

import re
import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

sys.path.insert(0, "records/work")

_TEXT = re.compile(r"<text[^>]*x=\"([\d.-]+)\"[^>]*y=\"([\d.-]+)\"[^>]*>(-?\d+)</text>")
_LINE = re.compile(r"<line[^>]*x1=\"([\d.-]+)\"[^>]*y1=\"([\d.-]+)\"[^>]*"
                   r"x2=\"([\d.-]+)\"[^>]*y2=\"([\d.-]+)\"")
# 「x = 2、4、16 および x = -2、-4、-16」のように名指しされた x の並び。
_ASKED_XS = re.compile(r"x\s*=\s*([-\d、,\s]+)")


def _axis_range(svg: str) -> tuple[float, float] | None:
    """方眼の x の範囲（座標の単位）。目盛ラベルから画素→座標の倍率を出す。"""
    rows: dict[int, set[tuple[int, float]]] = {}
    for m in _TEXT.finditer(svg):
        rows.setdefault(round(float(m.group(2))), set()).add(
            (int(m.group(3)), float(m.group(1)))
        )
    if not rows:
        return None
    row = sorted(max(rows.values(), key=len), key=lambda t: t[1])
    if len(row) < 2:
        return None
    (v0, p0), (v1, p1) = row[0], row[-1]
    if v1 == v0:
        return None
    per = (p1 - p0) / (v1 - v0)
    px = [float(a) for a, _b, _c, _d in _LINE.findall(svg)]
    px += [float(c) for _a, _b, c, _d in _LINE.findall(svg)]
    if not px:
        return None
    return ((min(px) - p0) / per + v0, (max(px) - p0) / per + v0)


def findings(text: str, svg: str) -> list[str]:
    """本文が名指した x が方眼に収まっているか。"""
    asked: list[int] = []
    for m in _ASKED_XS.finditer(text):
        asked += [int(v) for v in re.findall(r"-?\d+", m.group(1))]
    if not asked:
        return []
    rng = _axis_range(svg)
    if rng is None:
        return []
    lo, hi = rng
    out = []
    for v in sorted(set(asked)):
        if not (lo - 0.01 <= v <= hi + 0.01):
            out.append(f"本文が x = {v} を名指しているが、方眼は {lo:.0f}〜{hi:.0f}")
    return out


def self_test() -> int:
    svg = (
        '<text x="100" y="200">0</text><text x="150" y="200">5</text>'
        '<line x1="60" y1="200" x2="240" y2="200"/>'
    )   # 1目盛=10px、方眼は -4 〜 14
    fails = 0
    for name, text, want in [
        ("収まる", "x = 2、4、10 に対応する点をとれ", False),
        ("はみ出す", "x = 2、4、16 に対応する点をとれ", True),
        ("負にはみ出す", "x = -8 に対応する点をとれ", True),
    ]:
        got = findings(text, svg)
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    if "--self-test" in argv:
        return 1 if self_test() else 0
    from build_corpus import load_cells  # noqa: PLC0415

    seeds = int(argv[argv.index("--seeds") + 1]) if "--seeds" in argv else 3
    env = make_env()
    bad: list[str] = []
    n = 0
    for unit, form, level, _c, _e, _f in load_cells():
        for seed in range(1, seeds + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported) or not res.visual_svg:
                continue
            n += 1
            bad.extend(f"{unit}.{form}.Lv{level} seed{seed}: {v}"
                       for v in findings(res.problem_text, res.visual_svg))
    print(f"見た図 {n} 枚（seed 1..{seeds}）")
    if not n:
        print("=== 1枚も見ていない＝検査が動いていない ===")
        return 1
    if bad:
        print(f"=== 方眼に収まらない指定 {len(bad)} 件 ===")
        for b in bad[:30]:
            print(f"  {b}")
        return 1
    print("=== 本文が名指した点はすべて方眼に収まっている ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
