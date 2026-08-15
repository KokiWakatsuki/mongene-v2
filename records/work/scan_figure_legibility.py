"""図が**教材として読めるか**を、SVG の座標から測る。

`check_figure_matches_givens.py` は「座標が仮定と食い違わないか」を見る道具で、
図の**中身の正しさ**しか見ていない。生徒が図を読むときに困るのはそこではなく、

  ・ラベルが重なって読めない
  ・ラベルが図からはみ出して切れている
  ・ラベルが線の上に乗っていて、どちらも読めない
  ・問題文が「点 D」と言っているのに図に D が無い（逆もある）

の4つ。ここはそれを測る。**図は正しいが読めない**という欠陥はこれでしか出ない。

## 測り方

SVG の `<text>` を全部拾い、フォントサイズから文字の箱を見積もる（全角は 1.0em、
半角は 0.55em、箱の上端は baseline − 0.78em）。あとは箱同士・箱と枠・箱と線分の
交わりを数えるだけ。

**線との衝突は「線分が箱を貫くか」で見る。** 辺の長さラベルは辺のすぐ横に置くのが
普通なので、「近い」で数えると全部が引っかかる。貫いているものだけを出す。

実行:
  PYTHONPATH=engine_core .venv/bin/python records/work/scan_figure_legibility.py [--seeds N]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from engine.core.contracts import Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import capability_cells, cell_request, make_env

_OUT = Path("records/work/fig_scan")

_TEXT = re.compile(r"<text\b([^>]*)>(.*?)</text>", re.S)
_LINE = re.compile(r"<line\b([^>]*?)/?>")
_POLY = re.compile(r"<(polygon|polyline)\b([^>]*?)/?>")
_PATH = re.compile(r"<path\b([^>]*?)/?>")
# 属性名に数字が入る（x1, y2）。`[a-zA-Z-]+` だと x1/y1 が取れず、
# **線が1本も拾えないのに0件だから合格と読める**状態になっていた。
_ATTR = re.compile(r'([a-zA-Z][a-zA-Z0-9-]*)\s*=\s*"([^"]*)"')
_VIEWBOX = re.compile(r'viewBox="([^"]*)"')
_NUMS = re.compile(r"-?\d+(?:\.\d+)?")

# 図の骨格でない線（方眼・目盛り）はラベルの下を通ってよい。
_FAINT = {"#bbbbbb", "#cccccc", "#dddddd", "#eeeeee", "#e5e5e5", "#f0f0f0"}

_MIN_FONT = 9.0


def _attrs(chunk: str) -> dict[str, str]:
    return {k: v for k, v in _ATTR.findall(chunk)}


def _char_width(ch: str) -> float:
    """1文字の幅を em で見積もる。"""
    if unicodedata.east_asian_width(ch) in ("W", "F", "A"):
        return 1.0
    if ch in "‾¯′″":
        return 0.6
    return 0.55


def _text_boxes(svg: str) -> list[dict[str, object]]:
    """`<text>` の箱。白フチ（同じ文字を白で太らせた下敷き）は箱にしない。

    下敷きは同じ位置に同じ文字を2枚重ねる書き方なので、そのまま数えると
    「ラベルが重なる」が全件で立つ。白フチが付いていることだけ覚えて捨てる。
    """
    boxes: list[dict[str, object]] = []
    haloed = False
    for chunk, body in _TEXT.findall(svg):
        a = _attrs(chunk)
        label = re.sub(r"<[^>]*>", "", body)
        if not label.strip():
            continue
        if a.get("stroke", "").lower() == "#ffffff":
            haloed = True
            continue
        try:
            x, y = float(a.get("x", "0")), float(a.get("y", "0"))
            size = float(a.get("font-size", "12"))
        except ValueError:
            continue
        w = sum(_char_width(c) for c in label) * size
        anchor = a.get("text-anchor", "start")
        x0 = x - w / 2 if anchor == "middle" else (x - w if anchor == "end" else x)
        boxes.append({
            "label": label, "size": size, "haloed": haloed,
            "x0": x0, "x1": x0 + w, "y0": y - size * 0.78, "y1": y + size * 0.22,
        })
        haloed = False
    return boxes


def _segments(svg: str) -> list[tuple[float, float, float, float]]:
    """図の骨格の線分。line / polygon / polyline / path（直線命令のみ）を拾う。"""
    segs: list[tuple[float, float, float, float]] = []

    def faint(a: dict[str, str]) -> bool:
        return a.get("stroke", "").lower() in _FAINT or a.get("stroke", "") == "none"

    for chunk in _LINE.findall(svg):
        a = _attrs(chunk)
        if faint(a):
            continue
        try:
            segs.append((float(a["x1"]), float(a["y1"]), float(a["x2"]), float(a["y2"])))
        except (KeyError, ValueError):
            continue

    for tag, chunk in _POLY.findall(svg):
        a = _attrs(chunk)
        if faint(a):
            continue
        nums = [float(t) for t in _NUMS.findall(a.get("points", ""))]
        pts = list(zip(nums[0::2], nums[1::2]))
        if tag == "polygon" and len(pts) > 2:
            pts = pts + [pts[0]]
        segs += [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                 for i in range(len(pts) - 1)]

    for chunk in _PATH.findall(svg):
        a = _attrs(chunk)
        if faint(a):
            continue
        # 曲線命令（A/C/Q）は測らない。直線でつないだ折れ線だけを見る。
        d = a.get("d", "")
        if re.search(r"[AaCcQqSsTt]", d):
            continue
        nums = [float(t) for t in _NUMS.findall(d)]
        pts = list(zip(nums[0::2], nums[1::2]))
        segs += [(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1])
                 for i in range(len(pts) - 1)]

    return segs


def _overlap_area(p: dict, q: dict) -> float:
    w = min(p["x1"], q["x1"]) - max(p["x0"], q["x0"])
    h = min(p["y1"], q["y1"]) - max(p["y0"], q["y0"])
    return w * h if w > 0 and h > 0 else 0.0


def _crosses(seg: tuple[float, float, float, float], b: dict) -> bool:
    """線分が箱を**貫く**か（端が箱の中で終わるのは、指し示しているので許す）。"""
    x1, y1, x2, y2 = seg
    inside = lambda x, y: b["x0"] <= x <= b["x1"] and b["y0"] <= y <= b["y1"]  # noqa: E731
    if inside(x1, y1) or inside(x2, y2):
        return False
    # 箱の4辺と交わる回数。貫いていれば2回。
    hits = 0
    for ax, ay, bx, by in (
        (b["x0"], b["y0"], b["x1"], b["y0"]), (b["x0"], b["y1"], b["x1"], b["y1"]),
        (b["x0"], b["y0"], b["x0"], b["y1"]), (b["x1"], b["y0"], b["x1"], b["y1"]),
    ):
        d = (x2 - x1) * (by - ay) - (y2 - y1) * (bx - ax)
        if abs(d) < 1e-9:
            continue
        t = ((ax - x1) * (by - ay) - (ay - y1) * (bx - ax)) / d
        u = ((ax - x1) * (y2 - y1) - (ay - y1) * (x2 - x1)) / d
        if 0 <= t <= 1 and 0 <= u <= 1:
            hits += 1
    return hits >= 2


# 図に置かれる「点の名前」らしいラベル（1文字の大文字、'（ダッシュ）付きも可）。
_POINT = re.compile(r"^[A-Z]['′]?$")


# 「点Pを作図によって求めよ」「三角形A'B'C'をかけ」——**生徒がこれから作るもの**は
# 図に無くて当たり前。名前から30字以内に作る動詞があるものは、無くてよいとみなす。
_TO_BE_MADE = re.compile(r"を[^。]{0,30}?(作図|かけ|かき|かこ|求め|しるし|とれ|とり)")


def _expected_absent(name: str, text: str) -> bool:
    """一度でも「…を求めよ／かけ」の対象になっていれば、図に無くてよい。

    「回転の中心を点Qとするとき、…点Qの位置を求め」のように、名前は先に導入されて
    後で求められる。全部の出現に作る動詞を求めると、この形が取りこぼされる。
    図に描かれている点は `drawn` 側で拾えるので、緩めても見落としにはならない。
    """
    return any(
        _TO_BE_MADE.search(text[m.end():m.end() + 34])
        for m in re.finditer(re.escape(name), text)
    )


def _point_names_in_text(text: str) -> set[str]:
    """問題文が名指ししている点の名前。

    `△ABC` `AB` `∠BAC` のように続けて書かれるので、**大文字の連なりを1字ずつ**割る。
    小文字が続くもの（`Lv`, `cm`）は名前でないので外す。
    """
    out: set[str] = set()
    for run in re.findall(r"[A-Z]['′]?(?:[A-Z]['′]?)*", text):
        if len(run) == 1:
            # 単独の大文字は変数（S, V, x の相方）かもしれないので、
            # 「点A」「頂点A」の形で出たものだけを採る（呼び出し側で足す）。
            continue
        out.update(re.findall(r"[A-Z]['′]?", run))
    # 「2点M、Nと直線ℓ」「3点A、B、C」のように、点の名前は読点で並ぶ。
    # 先頭の1つだけを採ると、残りが「図にしか無い名前」に見えてしまう。
    for m in re.finditer(r"(?:点|頂点|中点|交点|端点)\s*((?:[A-Z]['′]?[、,]?\s*)+)", text):
        out.update(re.findall(r"[A-Z]['′]?", m.group(1)))
    return out


def _named_loose(text: str) -> set[str]:
    """本文に出る大文字を、**まわりが日本語なら名前とみなして**全部拾う。

    `cm` `Lv` のような英字の並びの一部は除く。ここは「図にしか無い名前」を
    見つけるための集合なので、広く採るほうが誤った指摘が減る。
    """
    out: set[str] = set()
    for m in re.finditer(r"[A-Z]['′]?", text):
        before = text[m.start() - 1] if m.start() else " "
        after = text[m.end()] if m.end() < len(text) else " "
        # `cm` `Lv` のような英単語の一部だけを外す。`ABC` の B・C は名前なので残す。
        if before.isascii() and before.isalpha() and before.islower():
            continue
        if after.isascii() and after.isalpha() and after.islower():
            continue
        out.add(m.group(0))
    return out


def main() -> int:
    seeds = 3
    if "--seeds" in sys.argv:
        seeds = int(sys.argv[sys.argv.index("--seeds") + 1])

    env = make_env()
    _OUT.mkdir(parents=True, exist_ok=True)
    findings: list[dict[str, object]] = []
    n_fig = 0

    for coord in capability_cells(env):
        for seed in range(1, seeds + 1):
            try:
                res = generate(
                    cell_request(coord, seed),
                    curriculum=env.curriculum, families=env.families, registry=env.registry,
                )
            except Exception as e:  # noqa: BLE001
                findings.append({"cell": f"{coord.unit}.{coord.form}.Lv{coord.level}",
                                 "seed": seed, "kind": "生成できない", "detail": str(e)[:120]})
                continue
            if isinstance(res, Unsupported) or not res.visual_svg:
                continue
            n_fig += 1
            svg = res.visual_svg
            cell = f"{coord.unit}.{coord.form}.Lv{coord.level}"
            here = lambda k, d: findings.append(  # noqa: E731
                {"cell": cell, "seed": seed, "kind": k, "detail": d})

            boxes = _text_boxes(svg)
            segs = _segments(svg)
            vb = _VIEWBOX.search(svg)
            if vb:
                vx, vy, vw, vh = (float(t) for t in vb.group(1).split())
                # 「線が枠の外へ出る」は**測らない**。座標平面のグラフは枠の外まで
                # 引いて枠で切るのが正しい描き方で、はみ出し＝欠陥ではない
                # （14件出したが全部これだった）。度数折れ線が軸の外へ突き抜けて
                # いた本物の欠陥は目で見て見つけたもので、この走査では出せない。
                for b in boxes:
                    if (b["x0"] < vx - 0.5 or b["y0"] < vy - 0.5
                            or b["x1"] > vx + vw + 0.5 or b["y1"] > vy + vh + 0.5):
                        here("枠からはみ出す", f"{b['label']!r} at ({b['x0']:.0f},{b['y0']:.0f})")

            for i, p in enumerate(boxes):
                if p["size"] < _MIN_FONT:
                    here("文字が小さい", f"{p['label']!r} {p['size']}px")
                for q in boxes[i + 1:]:
                    a = _overlap_area(p, q)
                    if a <= 0:
                        continue
                    small = min((p["x1"] - p["x0"]) * (p["y1"] - p["y0"]),
                                (q["x1"] - q["x0"]) * (q["y1"] - q["y0"]))
                    if a / small > 0.15:
                        here("ラベルが重なる",
                             f"{p['label']!r} × {q['label']!r} 重なり {a / small:.0%}")
                for s in segs:
                    if _crosses(s, p):
                        # 白フチ付きは、線が通っても文字は浮いて読める（目視で確認済み）。
                        # 消さずに別の見出しで数える——「直した」を「見なくなった」に
                        # すり替えないため。
                        here("線がラベルを貫く（白フチあり）" if p["haloed"]
                             else "線がラベルを貫く", f"{p['label']!r}")
                        break

            # 図の点名 ↔ 問題文の点名
            body = res.problem_text + " " + " ".join(
                (sq.prompt_text or "") for sq in res.sub_questions)
            named = _point_names_in_text(body)
            drawn = {str(b["label"]) for b in boxes if _POINT.match(str(b["label"]))}
            missing = sorted(n for n in named - drawn if not _expected_absent(n, body))
            if missing and drawn:
                here("問題文の点が図に無い", "".join(missing))
            # 「図にあるのに本文に無い」側は**緩く**採る。「垂線の足をIとし」「円Oの
            # 直径」のように、点は「点」を付けずに導入されることがある。厳しい
            # 取り方のままだと、正しく名指しされた点が余計な指摘になる。
            stray = sorted(d for d in drawn - _named_loose(body))
            if stray:
                here("図の点が問題文に無い", "".join(stray))

    _OUT.mkdir(parents=True, exist_ok=True)
    (_OUT / "findings.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    tally = Counter(str(f["kind"]) for f in findings)
    print(f"図 {n_fig} 枚（{seeds} seed）を見た。指摘 {len(findings)} 件")
    for kind, n in tally.most_common():
        print(f"  {kind:<16} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
