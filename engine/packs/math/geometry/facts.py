"""幾何の事実（述語）の表現（docs/proof_engine_design_2026-08-08.md §5）。

前向き推論の対象になる事実を、**正規形をもつハッシュ可能な値**として表す。
正規形にするのは「同じ事実が別の書き方で2回入る」のを防ぐため——たとえば
線分 AB と BA は同じ、∠BAC と ∠CAB は同じ。ここを緩めると推論が飽和しない
（同じ事実を延々と作り続ける）。

**事実は構成手順が持つ。座標から測って作らない。** 座標は図を描くためだけにある
（浮動小数の一致で事実を作ると、丸めで偽の事実が混じる）。

合同・相似は**対応の順序を持つ**（△ABC≡△DEF と △ABC≡△EDF は別の主張）。
だから頂点の三つ組は順序つきタプルのまま持ち、辺・角のように並べ替えない。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Point = str  # 点の名前（"A" など）


def seg(a: Point, b: Point) -> tuple[Point, Point]:
    """線分の正規形（端点を並べ替える。AB と BA は同じ線分）。"""
    if a == b:
        raise ValueError(f"線分の端点が同じ: {a}")
    return (a, b) if a <= b else (b, a)


def ang(vertex: Point, arm1: Point, arm2: Point) -> tuple[Point, Point, Point]:
    """角の正規形（頂点はそのまま・2辺の向きを並べ替える。∠BAC と ∠CAB は同じ角）。"""
    if len({vertex, arm1, arm2}) != 3:
        raise ValueError(f"角の3点が相異でない: {vertex}, {arm1}, {arm2}")
    lo, hi = (arm1, arm2) if arm1 <= arm2 else (arm2, arm1)
    return (vertex, lo, hi)


def tri(a: Point, b: Point, c: Point) -> tuple[Point, Point, Point]:
    """三角形の頂点の三つ組。**並べ替えない**（合同・相似の対応を表すため）。"""
    if len({a, b, c}) != 3:
        raise ValueError(f"三角形の3頂点が相異でない: {a}, {b}, {c}")
    return (a, b, c)


FactKind = Literal[
    "seg_eq",      # 2つの線分の長さが等しい
    "ang_eq",      # 2つの角の大きさが等しい
    "tri_cong",    # 2つの三角形が合同（対応つき）
    "tri_sim",     # 2つの三角形が相似（対応つき）
    "parallel",    # 2直線が平行（向きは問わない）
    "parallel_dir",  # 2つの**向きつき**の線分が同じ向きに平行
    "perp",        # 2直線が垂直
    "midpoint",    # ある点が線分の中点
    "collinear",   # 3点が一直線上
    "right_angle",   # ある角が直角
    "parallelogram",  # 四角形が平行四辺形
    "rectangle",   # 四角形が長方形
    "rhombus",     # 四角形がひし形
    "square",      # 四角形が正方形
    "seg_half",    # 一方の線分の長さが他方の半分
    "ratio_eq",    # 2つの線分の比が、別の2つの線分の比に等しい
    "on_circle",   # ある点が、ある中心の円周上にある
]


@dataclass(frozen=True, order=True)
class Fact:
    """1つの事実。`args` は述語ごとに決まった形の入れ子タプル（正規形済み）。

    例:
      Fact("seg_eq", (("A","B"), ("A","D")))
      Fact("ang_eq", (("A","B","C"), ("A","C","B")))
      Fact("tri_cong", (("A","B","C"), ("A","D","C")))
      Fact("midpoint", ("M", ("A","B")))
    """

    kind: FactKind
    args: tuple

    def __str__(self) -> str:  # pragma: no cover - 表示のみ
        return f"{self.kind}{self.args}"


# ---------------------------------------------------------------------------
# 構築ヘルパ（正規形をここだけで作る。呼び出し側で組み立てない）
# ---------------------------------------------------------------------------
def is_common_segment(f: Fact) -> bool:
    """「AC は共通」の形か（同じ線分どうしの等号）。証明文の書き方が変わる。"""
    return f.kind == "seg_eq" and f.args[0] == f.args[1]


def seg_eq(s1: tuple[Point, Point], s2: tuple[Point, Point]) -> Fact:
    """線分の長さが等しい。2つの線分も並べ替える（対称な関係なので）。"""
    a, b = (s1, s2) if s1 <= s2 else (s2, s1)
    return Fact("seg_eq", (a, b))


def ang_eq(a1: tuple[Point, Point, Point], a2: tuple[Point, Point, Point]) -> Fact:
    a, b = (a1, a2) if a1 <= a2 else (a2, a1)
    return Fact("ang_eq", (a, b))


def _canonical_correspondence(
    t1: tuple[Point, Point, Point], t2: tuple[Point, Point, Point]
) -> tuple[tuple[Point, Point, Point], tuple[Point, Point, Point]]:
    """合同・相似の**同じ対応を表す6通りの書き方**から代表を1つ選ぶ。

    △ABC≡△ADC は A↔A・B↔D・C↔C という対応で、これは △ACB≡△ACD とも
    △BCA≡△DCA とも書ける（回転3通り × 向き2通り）。**同じ主張を6件の別の事実として
    持ってしまうと**、推論が6倍に膨らみ「どの対応を示すのか」も定まらない
    （最初に実装したときそうなった）。頂点の並びが辞書順で最小になる書き方を代表にする
    ——凧形なら △ABC≡△ADC が選ばれ、これは教科書の書き方そのものになる。
    """
    writings = []
    for r in range(3):
        rot1 = (t1[r % 3], t1[(r + 1) % 3], t1[(r + 2) % 3])
        rot2 = (t2[r % 3], t2[(r + 1) % 3], t2[(r + 2) % 3])
        writings.append((rot1, rot2))
        writings.append(((rot1[0], rot1[2], rot1[1]), (rot2[0], rot2[2], rot2[1])))
    # 「どちらを先に書くか」も対称なので、2つの三角形の入れかえも候補に入れる。
    writings += [(b, a) for a, b in writings]
    return min(writings)


def tri_cong(t1: tuple[Point, Point, Point], t2: tuple[Point, Point, Point]) -> Fact:
    """三角形の合同（対応つき）。同じ対応の6通りの書き方を1つに正規化する。"""
    return Fact("tri_cong", _canonical_correspondence(t1, t2))


def tri_sim(t1: tuple[Point, Point, Point], t2: tuple[Point, Point, Point]) -> Fact:
    """三角形の相似（対応つき）。正規化は合同と同じ。"""
    return Fact("tri_sim", _canonical_correspondence(t1, t2))


def parallel(s1: tuple[Point, Point], s2: tuple[Point, Point]) -> Fact:
    a, b = (s1, s2) if s1 <= s2 else (s2, s1)
    return Fact("parallel", (a, b))


def parallel_dir(
    u: tuple[Point, Point], v: tuple[Point, Point]
) -> Fact:
    """向きつきの平行（ベクトル PQ とベクトル RS が**同じ向き**に平行）。

    錯角・同位角のどちらになるかは**向き**で決まるので、向きを持たない平行だけでは
    角の等式を機械的に出せない（座標を見て判定するのは原則に反する）。平行移動で
    作った点は向きまで分かっているので、そこから向きつきの事実を出す。

    正規形: 2つの組の入れかえと、**両方を同時に逆向きにする**操作で不変。
    """
    cands = [(u, v), (v, u), ((u[1], u[0]), (v[1], v[0])), ((v[1], v[0]), (u[1], u[0]))]
    return Fact("parallel_dir", min(cands))


def perp(s1: tuple[Point, Point], s2: tuple[Point, Point]) -> Fact:
    a, b = (s1, s2) if s1 <= s2 else (s2, s1)
    return Fact("perp", (a, b))


def midpoint(m: Point, s: tuple[Point, Point]) -> Fact:
    return Fact("midpoint", (m, s))


def collinear(a: Point, b: Point, c: Point) -> Fact:
    """3点が一直線上（順序は並べ替える）。"""
    if len({a, b, c}) != 3:
        raise ValueError("一直線上の3点が相異でない")
    return Fact("collinear", tuple(sorted((a, b, c))))


def right_angle(vertex: Point, arm1: Point, arm2: Point) -> Fact:
    """ある角が直角（∠ABC ＝ 90°）。

    `perp`（2直線が垂直）と分けてあるのは、**証明文で書き分けるから**である——
    教科書は「∠ABC ＝ 90°」と書く行と「AB ⊥ CD」と書く行を使い分ける。
    直角三角形の合同条件は「直角である角がどれか」を要求するので、角の側で持つ。
    """
    return Fact("right_angle", (ang(vertex, arm1, arm2),))


def _canonical_quad(
    q: tuple[Point, Point, Point, Point]
) -> tuple[Point, Point, Point, Point]:
    """四角形 ABCD の**同じ四角形を表す8通りの書き方**から代表を1つ選ぶ。

    四角形は頂点を周にそって読むので、どこから読み始めても（4通り）、どちら回りに
    読んでも（2通り）同じ図形である。合同・相似の対応と違い、四角形が
    平行四辺形であるという主張に「対応」は無いので、8通りを1つにまとめてよい。
    """
    if len(set(q)) != 4:
        raise ValueError(f"四角形の4頂点が相異でない: {q}")
    rots = [tuple(q[(i + k) % 4] for k in range(4)) for i in range(4)]
    rots += [tuple(reversed(r)) for r in rots]
    return min(rots)


def parallelogram(a: Point, b: Point, c: Point, d: Point) -> Fact:
    """四角形 ABCD が平行四辺形（頂点は周にそって並べる）。"""
    return Fact("parallelogram", (_canonical_quad((a, b, c, d)),))


def rectangle(a: Point, b: Point, c: Point, d: Point) -> Fact:
    return Fact("rectangle", (_canonical_quad((a, b, c, d)),))


def rhombus(a: Point, b: Point, c: Point, d: Point) -> Fact:
    return Fact("rhombus", (_canonical_quad((a, b, c, d)),))


def square(a: Point, b: Point, c: Point, d: Point) -> Fact:
    return Fact("square", (_canonical_quad((a, b, c, d)),))


def seg_half(half: tuple[Point, Point], whole: tuple[Point, Point]) -> Fact:
    """`half` の長さが `whole` の半分（中点連結定理の結論の形）。**並べ替えない。**"""
    if half == whole:
        raise ValueError("同じ線分の半分にはならない")
    return Fact("seg_half", (half, whole))


def ratio_eq(
    s1: tuple[Point, Point],
    s2: tuple[Point, Point],
    s3: tuple[Point, Point],
    s4: tuple[Point, Point],
) -> Fact:
    """比の等式 s1 : s2 ＝ s3 : s4（平行線と線分の比の結論の形）。

    正規形: 左右の比の入れかえで不変。**比の中の順序は入れかえない**（2:3 と 3:2 は
    別の主張）。
    """
    left, right = (s1, s2), (s3, s4)
    a, b = (left, right) if left <= right else (right, left)
    return Fact("ratio_eq", (a, b))


def on_circle(p: Point, center: Point) -> Fact:
    """点 p が、center を中心とする円の周上にある。"""
    if p == center:
        raise ValueError("中心は円周上にない")
    return Fact("on_circle", (p, center))


# ---------------------------------------------------------------------------
# 表示（証明文にそのまま出る形。ここを1か所に集めておく）
# ---------------------------------------------------------------------------
def seg_text(s: tuple[Point, Point]) -> str:
    return f"{s[0]}{s[1]}"


def ang_text(a: tuple[Point, Point, Point]) -> str:
    """∠BAC の形（頂点を中央に置く。教科書の書き方）。"""
    return f"∠{a[1]}{a[0]}{a[2]}"


def tri_text(t: tuple[Point, Point, Point]) -> str:
    return f"△{t[0]}{t[1]}{t[2]}"


def fact_text(f: Fact) -> str:
    """事実の日本語（証明文の「主張」欄に入る文字列）。"""
    if f.kind == "seg_eq":
        if is_common_segment(f):
            # 「AC ＝ AC」ではなく「AC は共通」と書く（教科書の書き方）。
            return f"{seg_text(f.args[0])} は共通"
        return f"{seg_text(f.args[0])} ＝ {seg_text(f.args[1])}"
    if f.kind == "ang_eq":
        return f"{ang_text(f.args[0])} ＝ {ang_text(f.args[1])}"
    if f.kind == "tri_cong":
        return f"{tri_text(f.args[0])} ≡ {tri_text(f.args[1])}"
    if f.kind == "tri_sim":
        return f"{tri_text(f.args[0])} ∽ {tri_text(f.args[1])}"
    if f.kind in ("parallel", "parallel_dir"):
        return f"{seg_text(f.args[0])} ∥ {seg_text(f.args[1])}"
    if f.kind == "perp":
        return f"{seg_text(f.args[0])} ⊥ {seg_text(f.args[1])}"
    if f.kind == "midpoint":
        return f"{f.args[0]} は {seg_text(f.args[1])} の中点"
    if f.kind == "collinear":
        return f"{'、'.join(f.args)} は一直線上にある"
    if f.kind == "right_angle":
        return f"{ang_text(f.args[0])} ＝ 90°"
    if f.kind in ("parallelogram", "rectangle", "rhombus", "square"):
        name = {
            "parallelogram": "平行四辺形",
            "rectangle": "長方形",
            "rhombus": "ひし形",
            "square": "正方形",
        }[f.kind]
        return f"四角形{''.join(f.args[0])} は{name}である"
    if f.kind == "seg_half":
        return f"{seg_text(f.args[0])} ＝ ½{seg_text(f.args[1])}"
    if f.kind == "ratio_eq":
        (a, b), (c, d) = f.args
        return f"{seg_text(a)}：{seg_text(b)} ＝ {seg_text(c)}：{seg_text(d)}"
    if f.kind == "on_circle":
        return f"点{f.args[0]} は点{f.args[1]}を中心とする円の周上にある"
    raise ValueError(f"未知の述語: {f.kind}")


__all__ = [
    "Fact",
    "FactKind",
    "Point",
    "ang",
    "ang_eq",
    "ang_text",
    "collinear",
    "fact_text",
    "is_common_segment",
    "midpoint",
    "parallel",
    "parallel_dir",
    "perp",
    "seg",
    "seg_eq",
    "seg_text",
    "tri",
    "tri_cong",
    "tri_sim",
    "tri_text",
]
