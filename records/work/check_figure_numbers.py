"""図に印字された数値が、**座標から測った実際の図**と合っているかを見る。

## なぜ要るか（既存の検査の盲点）

`check_figure_matches_givens.py` は `*.proof.yaml` の `construction` を持つセルだけを
見ている（構成の facts にある等長・等角・直角を座標で照合する）。**`find_value` と
`graph_table` の図は一度も検査されていない。**「調べた図 905 / 食い違い 0」は
proof の構成図をパラメータ違いで905通り見た数で、セル数ではない。

G-BT（図つき）で読み手に図を渡したら、この盲点にあった欠陥が出た。実測の1例:

    本文「平行四辺形DEFGで、DE=16cm、∠E=41°」
    図に印字されているのは「41°」／座標から測った ∠DEF は **116.6°**

生徒は図を見て考えるので、これは解けない問題になる。

## 見るもの（2つ）

1. **角度**: 印字された `N°` の近くの頂点で、そこに集まる2本の線がなす角を測り、N と比べる
2. **長さの縮尺**: 同じ図の中に長さラベルが2つ以上あるとき、
   「印字された値 ÷ 画素の長さ」がどのラベルでもだいたい同じか
   （5cm と 6cm が 1:3.4 で描かれていた、4cm が 9cm より長く描かれていた）

どちらも**図の中だけ**で完結する（本文を読まない）ので、機械で全数見られる。

## 見ないもの

- 弧（`<path ... A ...>`）は角の印なので線分として数えない
- 白フチの複製テキストは1つに畳む
- 目盛ラベルだけの方眼（点が無い図）は対象外＝角も長さも測れない

実行:
  .venv/bin/python records/work/check_figure_numbers.py [--seeds N]
  .venv/bin/python records/work/check_figure_numbers.py --self-test
"""
from __future__ import annotations

import math
import re
import sys

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

sys.path.insert(0, "records/work")

_ANGLE_TOL = 8.0        # 度。ラベルの置き位置のぶれを見込む
_SCALE_TOL = 0.28       # 縮尺のばらつき（比で 28%）
_MIN_EDGE_PX = 20.0     # これより短い線分は等長マーク・直角の印（辺ではない）
_MAX_LABEL_DIST = 90.0  # ラベルと辺の中点がこれ以上離れていたら対応づけない
_TEXT = re.compile(r"<text[^>]*x=\"([\d.-]+)\"[^>]*y=\"([\d.-]+)\"[^>]*>(.*?)</text>", re.S)
_LINE = re.compile(r"<line[^>]*x1=\"([\d.-]+)\"[^>]*y1=\"([\d.-]+)\"[^>]*"
                   r"x2=\"([\d.-]+)\"[^>]*y2=\"([\d.-]+)\"")
_CIRCLE = re.compile(r"<circle[^>]*cx=\"([\d.-]+)\"[^>]*cy=\"([\d.-]+)\"")
_ANG_TXT = re.compile(r"^(\d+(?:\.\d+)?)°$")
_LEN_TXT = re.compile(r"^(\d+(?:\.\d+)?)\s*cm$")


def _texts(svg: str) -> list[tuple[float, float, str]]:
    """テキスト（位置と中身）。白フチの複製は畳む。"""
    seen: dict[tuple[float, float, str], None] = {}
    for m in _TEXT.finditer(svg):
        seen[(round(float(m.group(1)), 1), round(float(m.group(2)), 1),
              m.group(3).strip())] = None
    return [(x, y, t) for (x, y, t) in seen]


def _segments(svg: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """線分（`<line>` だけ。弧の `<path A>` は角の印なので数えない）。"""
    return [((float(a), float(b)), (float(c), float(d)))
            for a, b, c, d in _LINE.findall(svg)]


def _on_segment(a: tuple[float, float], b: tuple[float, float],
                v: tuple[float, float], tol: float = 2.0) -> bool:
    """点 v が線分 ab の（端点を除く）途中にあるか。"""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy
    if not n2:
        return False
    t = ((v[0] - a[0]) * dx + (v[1] - a[1]) * dy) / n2
    if not 0.02 < t < 0.98:
        return False
    px, py = a[0] + t * dx, a[1] + t * dy
    return math.hypot(v[0] - px, v[1] - py) < tol


def _angle(a: tuple[float, float], b: tuple[float, float],
           c: tuple[float, float]) -> float:
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n = math.hypot(*v1) * math.hypot(*v2)
    if not n:
        return 0.0
    d = (v1[0] * v2[0] + v1[1] * v2[1]) / n
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


_NAMED_ANG = re.compile(r"(∠[A-Za-z]|∠[a-z]\d?)\s*[=＝]\s*(\d+(?:\.\d+)?)\s*°")


def named_angles(text: str) -> dict[str, float]:
    """本文が名前に結びつけている角の値。「∠a = 70°、∠b = 36°」→ {∠a:70, ∠b:36}。

    ★**これが `check_figure_numbers.py` の最初の版の盲点だった。**
    図の印が数字（70°）なら測れるが、印が**名前**（∠a）で値が本文にある形は
    一度も照合されていなかった。g2_l31/l32 の折れ線の図は座標が固定で、
    本文が ∠a=70° でも図の角は 32.4°、答えが 106° でも折れ点は 63.3° だった。
    印字だけ見る検査は 749 枚を通して 0 件を返していた。
    """
    return {m.group(1): float(m.group(2)) for m in _NAMED_ANG.finditer(text)}


def angle_findings(svg: str, named: dict[str, float] | None = None) -> list[str]:
    """印字された角度（および本文が名前で与えた角）と、座標から測った角の食い違い。"""
    pts = [(float(x), float(y)) for x, y in _CIRCLE.findall(svg)]
    segs = _segments(svg)
    if not pts or len(segs) < 2:
        return []
    out: list[str] = []
    for tx, ty, text in _texts(svg):
        m = _ANG_TXT.match(text)
        if m:
            printed = float(m.group(1))
        elif named and text.strip() in named:
            printed = named[text.strip()]
        else:
            continue
        # 角のラベルは頂点のすぐ内側に置かれる。いちばん近い点を頂点とみなす。
        vx, vy = min(pts, key=lambda p: (p[0] - tx) ** 2 + (p[1] - ty) ** 2)
        # その頂点から出ている線分の向き
        arms: list[tuple[float, float]] = []
        for (x1, y1), (x2, y2) in segs:
            # ★**短い線分は辺ではない**（平行の印・等長マーク・直角の印）。
            # 平行の印は 7.5px の V 字で、その先端が頂点の 1px 以内に落ちることが
            # ある。前は印の2本を辺として数え、正しい図に「∠a は 75° /
            # 図の角 41.7°」を出していた（実測2件）。
            if math.hypot(x2 - x1, y2 - y1) < _MIN_EDGE_PX:
                continue
            if math.hypot(x1 - vx, y1 - vy) < 2.0:
                arms.append((x2, y2))
            elif math.hypot(x2 - vx, y2 - vy) < 2.0:
                arms.append((x1, y1))
            elif _on_segment((x1, y1), (x2, y2), (vx, vy)):
                # ★**頂点が線分の途中にある形**（直線 ℓ 上の点 A、横断線と交わる点）。
                # 端点しか見ていなかったので、この形の角は**一度も測られていなかった**。
                # g2_l31 の ∠a はまさにこれで、固定座標の誤り（本文 70° / 図 32.4°）を
                # 検査は素通りしていた。線分は両向きに辺を出す。
                arms.append((x1, y1))
                arms.append((x2, y2))
        if len(arms) < 2:
            continue
        # ★**ラベルに近い2本を選ぶ、では駄目。** 頂点に3本以上集まる図
        # （対頂角・平行線と横断線）だと、ほぼ同じ向きの2本を選んでしまい
        # 「図の角 0.0°」を出す（実測で誤検出が4件出た）。
        # **2等分線がラベルの向きにいちばん近い組**を選ぶ——角のラベルは
        # その角の内側、2辺のあいだに置かれているから。
        def bisector_gap(pair: tuple[tuple[float, float], tuple[float, float]]) -> float:
            (ax, ay), (bx, by) = pair
            n1 = math.hypot(ax - vx, ay - vy) or 1.0
            n2 = math.hypot(bx - vx, by - vy) or 1.0
            mid = ((ax - vx) / n1 + (bx - vx) / n2, (ay - vy) / n1 + (by - vy) / n2)
            if not math.hypot(*mid):
                return 999.0        # 向かい合う2本（180°）は角にならない
            return _angle((vx + mid[0], vy + mid[1]), (vx, vy), (tx, ty))

        pairs = [(arms[i], arms[j])
                 for i in range(len(arms)) for j in range(i + 1, len(arms))]
        # ★**ラベルが角の内側にある組だけを候補にする。** 2等分線の向きだけで選ぶと、
        # 頂点に3本以上集まる図（P に PQ・PR・PS）で誤った組を選び、正しい図に
        # 「印字 60° / 図の角 72.8°」を出した（実測 20件の誤検出）。**図を直したのに
        # 検査が鳴る**という形で出たので、点の座標で測り直して私の側の誤りと分かった。
        def inside(pair: tuple[tuple[float, float], tuple[float, float]]) -> bool:
            span = _angle(pair[0], (vx, vy), pair[1])
            a1 = _angle(pair[0], (vx, vy), (tx, ty))
            a2 = _angle(pair[1], (vx, vy), (tx, ty))
            return abs(a1 + a2 - span) < 6.0      # ラベルが2辺のあいだにある
        pairs = [q for q in pairs if _angle(q[0], (vx, vy), q[1]) > 1.0 and inside(q)]
        if not pairs:
            continue
        # 内側に入る組が複数あるときは、いちばん狭い角（＝その角のために置かれた
        # ラベルが指しているはずのもの）を採る。
        chosen = min(pairs, key=lambda q: _angle(q[0], (vx, vy), q[1]))
        drawn = _angle(chosen[0], (vx, vy), chosen[1])
        # ★**180°を超える角（おうぎ形の中心角300°など）は、座標からは 60° と出る。**
        # 反射角は「向こう側」なので、印字が 180° より大きいときは 360−測定値と比べる。
        if printed > 180.0:
            drawn = 360.0 - drawn
        if abs(drawn - printed) > _ANGLE_TOL:
            out.append(f"{text.strip()} は {printed:g}° / 図の角 {drawn:.1f}°"
                       f"（頂点 ({vx:.0f},{vy:.0f})）")
    return out


def to_scale(svg: str, form: str) -> bool:
    """その図は**縮尺どおりに描くもの**か。

    ★縮尺を測ってよい図は限られる。ここを宣言しないと、正しい図に文句をつける
    （実測で7件すべてが誤検出だった）:

    - **見取図（立体）は奥行きを縮めて描く**のが正しい。隠れ稜線の破線が目印
      （「辺STが6cm、辺TUが7cm、高さが2cmの直方体…の見取図」で 2cm=210px、
      7cm=30px になるのは、斜めに描いているから）
    - **`proof` の図は意図的に縮尺を崩す**。「∠PQR が直角であることを説明せよ」
      という問題で直角に見える形に描いたら、結論を図に書いたことになる
      （描き手の docstring に明記されている）
    """
    if form == "proof":
        return False
    return "stroke-dasharray" not in svg


def scale_findings(svg: str) -> list[str]:
    """長さラベルの縮尺のばらつき（同じ図なら「値÷画素」はほぼ一定）。

    呼ぶ前に `to_scale` で「縮尺どおりに描く図か」を確かめること。
    """
    # ★**短い線分は等長マーク・直角の印**（実測 8px）。辺として数えると
    # 「4cm=8px」が出て縮尺が壊れているように見える（誤検出が6セル分出た）。
    segs = [s for s in _segments(svg)
            if math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]) >= _MIN_EDGE_PX]
    if len(segs) < 2:
        return []
    # ★**1つの辺に2つ以上のラベルを割り当てない。** いちばん近い辺を独立に選ぶと、
    # 長い辺に3つのラベルが集まって「7cm=247px、56cm=247px、3cm=247px」になる
    # （誤検出）。近い順に、辺を使い切る形で割り当てる。
    cands: list[tuple[float, float, tuple]] = []
    for tx, ty, text in _texts(svg):
        m = _LEN_TXT.match(text)
        if not m:
            continue
        for seg in segs:
            mx, my = (seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2
            cands.append((math.hypot(mx - tx, my - ty), float(m.group(1)), seg))
    # ★**部分に名前を付けている図では測らない。** 円の中で交わる2本の弦は
    # 1本の線として描かれ、ラベル（DQ=7cm・DR=56cm・DT=3cm）はその**部分**を指す。
    # 描かれた線の画素長は、どのラベルの長さでもない。1本の線の近くに長さラベルが
    # 2つ以上あったら、その図の縮尺は測れない（実測でここを誤検出していた）。
    # ★判定は「その辺が**いちばん近い**ラベルの数」で数える。垂直距離だけで
    # 「近い」と数えたら、小さい図で縦横のラベルが両方1本の辺に数えられて、
    # 合成データの「5cm と 6cm が 5:1」が通ってしまった（自己検査が落ちた）。
    labels = [(tx, ty) for tx, ty, t in _texts(svg) if _LEN_TXT.match(t)]
    owner: dict[tuple, int] = {}
    for tx, ty in labels:
        near = min(segs, key=lambda sg: ((sg[0][0] + sg[1][0]) / 2 - tx) ** 2
                   + ((sg[0][1] + sg[1][1]) / 2 - ty) ** 2)
        owner[near] = owner.get(near, 0) + 1
    if any(v >= 2 for v in owner.values()):
        return []

    cands.sort(key=lambda c: c[0])
    used: set[tuple] = set()
    taken: set[float] = set()
    ratios: list[tuple[float, float, float]] = []
    for dist, printed, seg in cands:
        if seg in used or printed in taken or dist > _MAX_LABEL_DIST:
            continue
        # ★**対応づけが一意でないなら測らない。** 円の中で交わる2本の弦のように、
        # ラベルの指す部分（DQ・DR・DS）が線分として描かれていない図があり、
        # そこでは同じ距離に複数の辺が並ぶ。無理に割り当てると
        # 「3cm=247px、56cm=247px」という誤検出になる（実測1セル）。
        rivals = [d for d, v, sg in cands
                  if v == printed and sg not in used and sg is not seg]
        if rivals and min(rivals) < dist * 1.5:
            continue
        px = math.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1])
        used.add(seg)
        taken.add(printed)
        ratios.append((printed, px, printed / px))
    if len(ratios) < 2:
        return []
    scales = [r for _, _, r in ratios]
    lo, hi = min(scales), max(scales)
    if hi > lo * (1 + _SCALE_TOL) * 2:      # 2倍以上ばらけたら図として読めない
        detail = "、".join(f"{v:g}cm={px:.0f}px" for v, px, _ in ratios)
        return [f"長さの縮尺がばらけている（{detail}）"]
    return []


_GOOD_SVG = '''<svg><circle cx="0" cy="0"/><circle cx="100" cy="0"/><circle cx="0" cy="100"/>
<line x1="0" y1="0" x2="100" y2="0"/><line x1="0" y1="0" x2="0" y2="100"/>
<text x="14" y="14">90°</text><text x="50" y="10">10cm</text><text x="10" y="50">10cm</text></svg>'''
_BAD_ANGLE = _GOOD_SVG.replace(">90°<", ">41°<")
_BAD_SCALE = '''<svg><circle cx="0" cy="0"/><circle cx="100" cy="0"/><circle cx="0" cy="20"/>
<line x1="0" y1="0" x2="100" y2="0"/><line x1="0" y1="0" x2="0" y2="20"/>
<text x="50" y="10">5cm</text><text x="6" y="10">6cm</text></svg>'''


# 名前の印（∠a）だけがあり、値は本文にある形。図の角は 90°。
_NAMED_SVG = '''<svg><circle cx="0" cy="0"/><circle cx="100" cy="0"/><circle cx="0" cy="100"/>
<line x1="0" y1="0" x2="100" y2="0"/><line x1="0" y1="0" x2="0" y2="100"/>
<text x="14" y="14">∠a</text></svg>'''


# 頂点が線分の途中にある形。A=(215,88) は直線 (46,88)-(374,88) の途中。
# P=(197,148) なので ∠a（左向きの ℓ と AP）は 180-atan2(60,18)=106.7°… ではなく
# 左向き(-1,0) と (−18,60) のなす角 = 73.3°。平行の印（短い V 字）も置いてある。
_MID_SVG = ("<svg><circle cx=\"215\" cy=\"88\"/><circle cx=\"197\" cy=\"148\"/>"
            "<line x1=\"46\" y1=\"88\" x2=\"374\" y2=\"88\"/>"
            "<line x1=\"215\" y1=\"88\" x2=\"197\" y2=\"148\"/>"
            "<line x1=\"208\" y1=\"92.5\" x2=\"214\" y2=\"88\"/>"
            "<line x1=\"208\" y1=\"83.5\" x2=\"214\" y2=\"88\"/>"
            "<text x=\"200\" y=\"104\">∠a</text></svg>")


def self_test() -> int:
    fails = 0
    for name, text, want in [
        ("線分の途中の頂点でも測る（∠a=73°）", "∠a = 73° のとき", False),
        ("線分の途中の頂点の食い違いを見つける", "∠a = 40° のとき", True),
    ]:
        got = angle_findings(_MID_SVG, named_angles(text))
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    for name, text, want in [
        ("名前の角 ∠a=90° は図と合う", "∠a = 90° のとき", False),
        ("名前の角 ∠a=41° なのに図は 90°", "∠a = 41° のとき", True),
        ("本文が値を与えていなければ測らない", "∠a の大きさを求めよ", False),
    ]:
        got = angle_findings(_NAMED_SVG, named_angles(text))
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    for name, svg, want in [
        ("正しい図は通る（直角に 90°）", _GOOD_SVG, False),
        ("直角に 41° と印字", _BAD_ANGLE, True),
    ]:
        got = angle_findings(svg)
        ok = bool(got) == want
        fails += 0 if ok else 1
        print(f"{'OK  ' if ok else 'NG  '}合成「{name}」: {got or '合格'}")
    got = scale_findings(_BAD_SCALE)
    ok = bool(got)
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}合成「5cm と 6cm が 5:1 で描かれている」: {got or '合格'}")
    got = scale_findings(_GOOD_SVG)
    ok = not got
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}縮尺のそろった図は通る: {got or '合格'}")
    return fails


def main(argv: list[str]) -> int:
    bootstrap()
    if "--self-test" in argv:
        return 1 if self_test() else 0
    from build_corpus import load_cells  # noqa: PLC0415

    seeds = int(argv[argv.index("--seeds") + 1]) if "--seeds" in argv else 3
    env = make_env()
    n_fig = n_scale = n_named = 0
    bad: list[str] = []
    for unit, form, level, _c, _e, _f in load_cells():
        for seed in range(1, seeds + 1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported) or not res.visual_svg:
                continue
            n_fig += 1
            cell = f"{unit}.{form}.Lv{level} seed{seed}"
            named = named_angles(res.problem_text)
            n_named += len(named)
            found = angle_findings(res.visual_svg, named)
            if to_scale(res.visual_svg, form):
                n_scale += 1
                found += scale_findings(res.visual_svg)
            bad.extend(f"{cell}: {v}" for v in found)
    print(f"見た図 {n_fig} 枚（seed 1..{seeds}）"
          f"／うち縮尺を測れる図 {n_scale} 枚"
          f"（見取図と proof は縮尺を崩して描くので外す）"
          f"／本文が名前で与えた角 {n_named} 個")
    if not n_fig:
        print("=== 1枚も見ていない＝検査が動いていない ===")
        return 1
    if bad:
        cells = {b.split(" seed")[0] for b in bad}
        print(f"=== 図と印字の食い違い {len(bad)} 件 / {len(cells)} セル ===")
        for b in bad[:60]:
            print(f"  {b}")
        return 1
    print("=== 図と印字の食い違いは無い ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
