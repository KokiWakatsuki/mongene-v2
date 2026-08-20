#!/usr/bin/env python3
"""ヒストグラムの棒の合計が、本文が述べた人数と合っているかを見る。

読み手が「A組の度数が18人しかない（本文は24人）」と報告してきたので測った。
実測すると 4+10+4+3+3+0 = 24 人で**図は正しく、報告が誤り**だった。
それでも検査として残すのは、**棒の高さは印字された数ではないので、
`check_figure_numbers.py` では一度も照合されない**から。

★**最初に書いた測り方は壊れていた**（実線と破線の合計が同じ値・244人）。
壊れた口は2つ。①y 軸の目盛を「いちばん上と下」で換算していたが、拾った
テキストに x 軸の階級の数字が混ざっていた ②`stroke-dasharray` の有無で
分けるつもりが、1本の rect を切り出す正規表現が入れ子で効かず全部が両方に
入っていた。**過大に出た数字を鵜呑みにせず生の SVG を見て気づいた。**

    PYTHONPATH=records/work .venv/bin/python records/work/check_histogram_total.py [--seeds N]
    PYTHONPATH=records/work .venv/bin/python records/work/check_histogram_total.py --self-test
"""

from __future__ import annotations

import re
import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_TOL = 1.0  # 人。px→人数の換算の丸め
_RECT = re.compile(r"<rect\b[^>]*?/?>")
_ATTR = {k: re.compile(rf'{k}="([\d.-]+)"') for k in ("x", "y", "width", "height")}
# 「どちらも24人」「A組は30人」など、本文が述べた1組の人数
_TOTAL = re.compile(r"(?:どちらも|それぞれ)(\d+)人")


def _rects(svg: str) -> list[tuple[float, float, float, float, bool]]:
    """棒（x, y, 幅, 高さ, 破線か）。背景の全面 rect は外す。"""
    out = []
    for m in _RECT.finditer(svg):
        tag = m.group(0)
        try:
            x, y, w, h = (float(_ATTR[k].search(tag).group(1)) for k in ("x", "y", "width", "height"))
        except AttributeError:
            continue
        if w > 300.0:            # canvas 全面の下地
            continue
        out.append((x, y, w, h, "stroke-dasharray" in tag))
    return out


def _people_per_px(svg: str) -> float | None:
    """y 軸の目盛から「1px あたり何人」を出す。

    ★**x 軸の階級の数字を混ぜてはいけない。** 縦軸の目盛は左端に `text-anchor="end"`
    で置かれている。x で切ると階級の数字（40, 50, …）を拾って換算が壊れる。
    """
    ticks: set[tuple[float, int]] = set()
    for m in re.finditer(
        r'<text[^>]*y="([\d.-]+)"[^>]*text-anchor="end"[^>]*>(\d+)</text>', svg
    ):
        ticks.add((float(m.group(1)), int(m.group(2))))
    if len(ticks) < 2:
        return None
    pts = sorted(ticks)
    (y_lo, v_lo), (y_hi, v_hi) = pts[0], pts[-1]
    if y_lo == y_hi or v_lo == v_hi:
        return None
    return abs((v_hi - v_lo) / (y_hi - y_lo))


def findings(svg: str, stated: int) -> list[str]:
    per = _people_per_px(svg)
    bars = _rects(svg)
    if per is None or not bars:
        return []
    for dashed in (False, True):
        group = [b for b in bars if b[4] is dashed]
        if not group:
            continue
        total = sum(b[3] for b in group) * per
        if abs(total - stated) > _TOL:
            kind = "破線" if dashed else "実線"
            return [f"{kind}の棒の合計 {total:.1f}人 / 本文は {stated}人"]
    return []


_GOOD = ('<svg><rect x="0" y="0" width="460" height="400"/>'
         '<rect x="40" y="308" width="60" height="58"/>'
         '<rect x="100" y="250" width="60" height="116"/>'
         '<text y="369" text-anchor="end">0</text>'
         '<text y="311.33" text-anchor="end">2</text>'
         '<text x="40" y="380" text-anchor="middle">40</text></svg>')
_BAD = _GOOD.replace('height="116"', 'height="58"')


def self_test() -> int:
    fails = 0
    for name, svg, stated, want in [
        ("棒の合計が本文と合う（2+4=6人）", _GOOD, 6, False),
        ("棒の合計が足りない（2+2=4人なのに6人）", _BAD, 6, True),
        ("x 軸の数字（40）を目盛に混ぜていない", _GOOD, 6, False),
    ]:
        got = findings(svg, stated)
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    if "--self-test" in argv:
        return 1 if self_test() else 0
    from build_corpus import load_cells  # noqa: PLC0415

    seeds = int(argv[argv.index("--seeds") + 1]) if "--seeds" in argv else 4
    env = make_env()
    n_seen = 0
    bad: list[str] = []
    for unit, form, level, _c, _e, _f in load_cells():
        for seed in range(1, seeds + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form, level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported) or not res.visual_svg:
                continue
            m = _TOTAL.search(res.problem_text)
            if not m:
                continue
            n_seen += 1
            for v in findings(res.visual_svg, int(m.group(1))):
                bad.append(f"{unit}.{form}.Lv{level} seed{seed}: {v}")
    print(f"本文が人数を述べている図 {n_seen} 枚（seed 1..{seeds}）")
    if not n_seen:
        print("=== 1枚も見ていない＝検査が動いていない ===")
        return 1
    if bad:
        print(f"=== 棒の合計と本文の食い違い {len(bad)} 件 ===")
        for b in bad[:40]:
            print(f"  {b}")
        return 1
    print("=== 棒の合計は本文の人数と合っている ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
