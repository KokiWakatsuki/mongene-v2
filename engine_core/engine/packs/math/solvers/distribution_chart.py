"""分布のグラフ（ヒストグラム・度数折れ線・累積折れ線）の独立再計算ソルバ群（§6.2 double-solve）。

C11（データ・統計）クラスタのうち g1_l54/l55/l56/l58 の **graph_table**（読む／かく）セルを
対象にする。solver は**問題パラメータだけ**（階級の下限・階級の幅・度数列・生データ列）から
答えと steps を導く（recipe の構成値は見ない）。純粋・決定論。乱数は引かない。

  - `math.read_distribution_chart`   : g1_l54.graph_table Lv1 / g1_l55.graph_table Lv1
                                       （グラフから度数を読む・最頻の階級を読む）
  - `math.tabulate_and_draw_histogram`: g1_l54.graph_table Lv2（生データ→度数分布表→ヒストグラム）
  - `math.compare_distribution_shape`: g1_l54.graph_table Lv3 / g1_l58.graph_table Lv2
                                       （2つの分布の散らばりと偏りを比べる）
  - `math.relative_frequency_polygon`: g1_l55.graph_table Lv2（相対度数の表＋度数折れ線）
  - `math.cumulative_frequency_chart`: g1_l56.graph_table Lv2（累積度数の表＋累積折れ線）
  - `math.median_class_from_cumulative`: g1_l56.graph_table Lv3（累積分布から中央値の階級）
  - `math.overlay_frequency_polygons` : g1_l58.graph_table Lv3（2分布の度数折れ線を重ねてかく）
（g1_l55.graph_table Lv3 は既存 `math.compare_relative_frequency`（statistics_distribution.py）
 をそのまま再利用する＝新 solver ゼロ。）

narration には数字を書かない（BRIEF の失敗パターン2: 解答由来の値の誤検出を避ける）。
"""
from __future__ import annotations

from typing import cast

import sympy

from engine.core.contracts import ChoiceAnswer, Feature, GraphAnswer, Solution, Step, SymbolicAnswer
from engine.core.registry import register_solver


def _ints(values: object) -> list[int]:
    return [int(str(v)) for v in cast("list[object]", values)]


def _fmt_decimal(value: sympy.Rational) -> str:
    """割り切れるなら小数、割り切れなければ分数のまま。

    相対度数は小数で答えるのが教材の作法（EVALUATION D-24）。recipe が割り切れる
    組だけを引くので、実際には常に小数になる——割り切れない値がここに来たら、
    recipe 側の構成が崩れた合図なので分数のまま出して見えるようにする。
    """
    q = int(value.q)
    while q % 2 == 0:
        q //= 2
    while q % 5 == 0:
        q //= 5
    if q != 1:
        return str(value)
    digits, r = 0, sympy.Rational(value)
    while r.q != 1:
        r *= 10
        digits += 1
    return f"{float(value):.{digits}f}" if digits else str(int(value))


def _class_bounds(class_lo: int, class_width: int, index: int) -> tuple[int, int]:
    lo = class_lo + class_width * index
    return lo, lo + class_width


def _modal_index(freqs: list[int]) -> int:
    """度数が最大の階級の番号。最大が一意でないときは例外（退化を通さない）。"""
    top = max(freqs)
    hits = [i for i, f in enumerate(freqs) if f == top]
    if len(hits) != 1:
        raise ValueError(f"度数が最大の階級が一意でない: {freqs}")
    return hits[0]


def _cumulative(freqs: list[int]) -> list[int]:
    out: list[int] = []
    total = 0
    for f in freqs:
        total += f
        out.append(total)
    return out


def _nonempty_span(freqs: list[int]) -> int:
    """度数が 1 以上の階級が占める幅（階級いくつぶんか）＝分布の散らばりの目安。"""
    hits = [i for i, f in enumerate(freqs) if f > 0]
    if not hits:
        raise ValueError("度数がすべて 0 の分布")
    return hits[-1] - hits[0] + 1


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv1 / g1_l55.graph_table Lv1: グラフから読む
# ---------------------------------------------------------------------------
@register_solver("math.read_distribution_chart")
def read_distribution_chart(
    frequencies: object,
    class_lo: object,
    class_width: object,
    target_index: object,
    unit: object = "",
) -> Solution:
    """指定した階級の度数と、度数が最大の階級を読み取る（graph_table「読む」Lv1）。

    度数列・階級の下限・階級の幅・対象の階級番号だけから求める（double-solve）。
    `unit` は表示のための単位記号で計算には関与しない。
    答えは Tuple(対象階級の度数, 度数が最大の階級の下限) の SymbolicAnswer。
    """
    freqs = _ints(frequencies)
    lo = int(str(class_lo))
    width = int(str(class_width))
    idx = int(str(target_index))
    u = str(unit)
    if not (0 <= idx < len(freqs)):
        raise ValueError(f"target_index が範囲外: {idx}")

    target_freq = sympy.Integer(freqs[idx])
    m_idx = _modal_index(freqs)
    m_lo, m_hi = _class_bounds(lo, width, m_idx)
    t_lo, t_hi = _class_bounds(lo, width, idx)

    disp = (
        f"{t_lo}{u}以上{t_hi}{u}未満の階級の度数は{target_freq}人、"
        f"度数が最も大きい階級は{m_lo}{u}以上{m_hi}{u}未満"
    )
    srepr = sympy.srepr(sympy.Tuple(target_freq, sympy.Integer(m_lo)))
    steps = [
        Step(
            op="read_class_frequency",
            args=[],
            result_srepr=sympy.srepr(target_freq),
            # 「対象の階級」では、どの階級のことか括弧から分からない。
            result_display=f"{t_lo}{u}以上{t_hi}{u}未満の階級の度数は{target_freq}",
            narration="対象の階級の位置をグラフの横軸で見つけ、その高さを縦軸の目盛で読み取る。",
        ),
        Step(
            op="find_modal_class",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            # 括弧には答え全体（度数＋最頻の階級）が出るので、narration も
            # 両方に触れる。片方しか言っていないと括弧の中身と噛み合わない。
            narration=(
                "グラフでいちばん高くなっている階級を探してその範囲を横軸から読み取り、"
                "先に読んだ度数とあわせて答える。"
            ),
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv2: 生データ → 度数分布表 → ヒストグラム
# ---------------------------------------------------------------------------
@register_solver("math.tabulate_and_draw_histogram")
def tabulate_and_draw_histogram(
    data: object,
    class_lo: object,
    class_width: object,
    n_classes: object,
    unit: object = "",
) -> Solution:
    """生データを階級に振り分けて度数分布表を作り、ヒストグラムの各階級の高さを決める。

    生データ列・階級の下限・階級の幅・階級の個数だけから度数を数え直す（double-solve）。
    `unit` は表示のための単位記号で計算には関与しない。答えは GraphAnswer（各階級の度数が特徴）。
    """
    values = _ints(data)
    lo = int(str(class_lo))
    width = int(str(class_width))
    n = int(str(n_classes))
    u = str(unit)
    if width <= 0 or n <= 0:
        raise ValueError("階級の幅・階級の個数は正であること")

    freqs = [0] * n
    for v in values:
        k = (v - lo) // width
        if not (0 <= k < n):
            raise ValueError(f"階級の範囲に入らないデータ: {v}")
        freqs[k] += 1

    features: list[Feature] = []
    for i, f in enumerate(freqs):
        c_lo, c_hi = _class_bounds(lo, width, i)
        features.append(
            Feature(
                kind="class_frequency",
                srepr=sympy.srepr(sympy.Tuple(sympy.Integer(c_lo), sympy.Integer(f))),
                display=f"{c_lo}{u}以上{c_hi}{u}未満…{f}人",
            )
        )

    steps = [
        Step(
            op="tally_into_classes",
            args=[],
            result_srepr="",
            result_display="、".join(str(f) for f in freqs),
            narration="データを一つずつ見て、どの階級にふくまれるかを調べ、正の字などで数え上げる。",
        ),
        Step(
            op="build_frequency_table",
            args=[],
            result_srepr="",
            result_display=f"度数の合計は{sum(freqs)}",
            narration="数え上げた個数を階級ごとに書き入れ、度数分布表を完成させる。",
        ),
        Step(
            op="draw_histogram",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*[sympy.Integer(f) for f in freqs])),
            result_display="、".join(f.display for f in features),
            narration="階級の幅を横、度数を縦の長さとする長方形を、すきまなく並べてかく。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features), steps=steps)


# ---------------------------------------------------------------------------
# g1_l54.graph_table Lv3 / g1_l58.graph_table Lv2: 2つの分布の形を比べる
# ---------------------------------------------------------------------------
_SPREAD_LABEL = "散らばりが大きいのは"
_SKEW_LABEL = "値の大きいほうの階級に偏っているのは"


def _shape_choice(spread: str, skew: str) -> str:
    return f"{_SPREAD_LABEL}{spread}、{_SKEW_LABEL}{skew}"


@register_solver("math.compare_distribution_shape")
def compare_distribution_shape(
    frequencies: object, frequencies_b: object, group_a: object, group_b: object
) -> Solution:
    """2つの分布について、散らばりの大きいほうと、高い階級に偏っているほうを判定する。

    2本の度数列と2つの組の名前だけから判定する（double-solve）。散らばりは度数が
    1 以上の階級が占める幅、偏りは度数が最大の階級の位置で測る。どちらも同点なら
    比較にならない退化なので例外にする。答えは ChoiceAnswer（4通りの組合せから1つ）。
    """
    fa, fb = _ints(frequencies), _ints(frequencies_b)
    if len(fa) != len(fb):
        raise ValueError("2つの度数列の階級数が違う")
    name_a, name_b = str(group_a), str(group_b)
    if name_a == name_b:
        raise ValueError("2つの組の名前が同じ")

    span_a, span_b = _nonempty_span(fa), _nonempty_span(fb)
    if span_a == span_b:
        raise ValueError(f"散らばりが同じで比較にならない: {span_a}")
    mode_a, mode_b = _modal_index(fa), _modal_index(fb)
    if mode_a == mode_b:
        raise ValueError(f"最も度数の大きい階級が同じ位置で比較にならない: {mode_a}")

    wider = name_a if span_a > span_b else name_b
    higher = name_a if mode_a > mode_b else name_b
    correct = _shape_choice(wider, higher)
    distractors = [
        _shape_choice(s, k)
        for s in (name_a, name_b)
        for k in (name_a, name_b)
        if _shape_choice(s, k) != correct
    ]

    steps = [
        Step(
            op="compare_distribution_spread",
            args=[],
            result_srepr=wider,
            result_display=f"{_SPREAD_LABEL}{wider}",
            narration="度数が入っている階級が横にどこまで広がっているかを、両方のグラフで見比べる。",
        ),
        Step(
            op="compare_distribution_skew",
            args=[],
            result_srepr=correct,
            result_display=correct,
            narration=(
                "山がいちばん高くなる階級が、両方のグラフでどちら寄りにあるかを見比べ、"
                "先に見た散らばりとあわせて答える。"
            ),
        ),
    ]
    answer = ChoiceAnswer(
        correct=correct,
        distractors=distractors,
        fact_id="distribution_comparison.shape_from_chart",
    )
    return Solution(answer=answer, steps=steps)


# ---------------------------------------------------------------------------
# g1_l55.graph_table Lv2: 相対度数の表 ＋ 度数折れ線
# ---------------------------------------------------------------------------
@register_solver("math.relative_frequency_polygon")
def relative_frequency_polygon(
    frequencies: object, class_lo: object, class_width: object, unit: object = ""
) -> Solution:
    """各階級の相対度数を求め、度数折れ線の各頂点（階級値と度数）を決める。

    度数列・階級の下限・階級の幅だけから求める（double-solve）。`unit` は表示のための
    単位記号で計算には関与しない。答えは GraphAnswer（相対度数と折れ線の頂点の両方を
    特徴に持つ）。
    """
    freqs = _ints(frequencies)
    lo = int(str(class_lo))
    width = int(str(class_width))
    u = str(unit)
    total = sum(freqs)
    if total <= 0:
        raise ValueError("総度数が 0 以下")

    features: list[Feature] = []
    for i, f in enumerate(freqs):
        rel = sympy.Rational(f, total)
        if not (0 < rel < 1):
            raise ValueError(f"相対度数が 0 または 1 に潰れている: {rel}")
        c_lo, c_hi = _class_bounds(lo, width, i)
        features.append(
            Feature(
                kind="relative_frequency",
                srepr=sympy.srepr(sympy.Tuple(sympy.Integer(c_lo), rel)),
                # **相対度数は小数で書く**（EVALUATION D-24。`1/6` と出ていた）。
                # recipe が「総度数が 20・25・40・50」の組だけを引くので必ず割り切れる。
                display=f"{c_lo}{u}以上{c_hi}{u}未満の相対度数は{_fmt_decimal(rel)}",
            )
        )
    for i, f in enumerate(freqs):
        mid = sympy.Rational(2 * (lo + width * i) + width, 2)
        features.append(
            Feature(
                kind="polygon_vertex",
                srepr=sympy.srepr(sympy.Tuple(mid, sympy.Integer(f))),
                # 階級値は「下端と上端の平均」なので階級幅が奇数だと x.5 になる。
                # **小数で書き切れるなら小数**（EVALUATION D-5/R-11。`25/2kg` と
                # 仮分数で出ていた）。
                display=f"折れ線の頂点（階級値{_fmt_decimal(mid)}{u}、度数{f}人）",
            )
        )

    steps = [
        Step(
            op="compute_total_frequency",
            args=[],
            result_srepr=sympy.srepr(sympy.Integer(total)),
            result_display=f"度数の合計は{total}",
            narration="すべての階級の度数を足し合わせ、総度数を求める。",
        ),
        Step(
            op="divide_each_by_total",
            args=[],
            result_srepr="",
            result_display="、".join(
                _fmt_decimal(sympy.Rational(f, total)) for f in freqs
            ),
            narration="階級ごとに、その階級の度数を総度数でわって相対度数を求め、表に書き入れる。",
        ),
        Step(
            op="draw_frequency_polygon",
            args=[],
            result_srepr="",
            # かいたもの（＝この手で得た図）。指示の言い直しは置かない（面③）。
            result_display="度数折れ線",
            narration="各階級の階級値の位置にその階級の度数の高さで点を打ち、順に線分で結ぶ（両端は度数のない階級まで下ろす）。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features), steps=steps)


# ---------------------------------------------------------------------------
# g1_l56.graph_table Lv2: 累積度数の表 ＋ 累積折れ線
# ---------------------------------------------------------------------------
@register_solver("math.cumulative_frequency_chart")
def cumulative_frequency_chart(
    frequencies: object, class_lo: object, class_width: object, unit: object = ""
) -> Solution:
    """各階級までの累積度数を求め、累積度数の折れ線の各頂点を決める。

    度数列・階級の下限・階級の幅だけから求める（double-solve）。`unit` は表示のための
    単位記号で計算には関与しない。答えは GraphAnswer（各階級の上端における累積度数が特徴）。
    """
    freqs = _ints(frequencies)
    lo = int(str(class_lo))
    width = int(str(class_width))
    u = str(unit)
    cums = _cumulative(freqs)
    if any(cums[i] >= cums[i + 1] for i in range(len(cums) - 1)):
        raise ValueError(f"累積度数が真に増加しない（度数 0 の階級がある）: {freqs}")

    features: list[Feature] = []
    for i, c in enumerate(cums):
        _c_lo, c_hi = _class_bounds(lo, width, i)
        features.append(
            Feature(
                kind="cumulative_frequency",
                srepr=sympy.srepr(sympy.Tuple(sympy.Integer(c_hi), sympy.Integer(c))),
                display=f"{c_hi}{u}未満の累積度数は{c}人",
            )
        )

    steps = [
        Step(
            op="accumulate_frequency_table",
            args=[],
            result_srepr="",
            result_display="、".join(str(c) for c in cums),
            narration="いちばん小さい階級から順に度数を足し上げ、各階級までの累積度数を表に書き入れる。",
        ),
        Step(
            op="plot_cumulative_points",
            args=[],
            result_srepr="",
            result_display="、".join(
                f"({lo + width * (i + 1)}, {c})" for i, c in enumerate(cums)
            ),
            narration="累積度数はその階級の上の端までの合計なので、点は階級の上端の位置に打つ。",
        ),
        Step(
            op="connect_cumulative_polyline",
            args=[],
            result_srepr=sympy.srepr(sympy.Tuple(*[sympy.Integer(c) for c in cums])),
            result_display="、".join(f.display for f in features),
            narration="いちばん小さい階級の下端の高さのない点から順に、打った点を線分で結ぶ。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features), steps=steps)


# ---------------------------------------------------------------------------
# g1_l56.graph_table Lv3: 累積分布から中央値のふくまれる階級を読む
# ---------------------------------------------------------------------------
@register_solver("math.median_class_from_cumulative")
def median_class_from_cumulative(
    frequencies: object, class_lo: object, class_width: object, unit: object = ""
) -> Solution:
    """累積度数が全体の半分に達する階級＝中央値がふくまれる階級を求める。

    度数列・階級の下限・階級の幅だけから求める（double-solve）。総度数が奇数のときのみ
    「ちょうど半分」の同点が起きないので、偶数の総度数は例外にする（読み取りが一意に
    決まらない退化を通さない）。答えは Tuple(階級の下端, 階級の上端) の SymbolicAnswer。
    """
    freqs = _ints(frequencies)
    lo = int(str(class_lo))
    width = int(str(class_width))
    total = sum(freqs)
    if total % 2 == 0:
        raise ValueError(f"総度数が偶数で中央値の階級が一意に決まらないおそれ: {total}")

    u = str(unit)
    cums = _cumulative(freqs)
    idx = next(i for i, c in enumerate(cums) if 2 * c > total)
    m_lo, m_hi = _class_bounds(lo, width, idx)

    disp = f"{m_lo}{u}以上{m_hi}{u}未満"
    srepr = sympy.srepr(sympy.Tuple(sympy.Integer(m_lo), sympy.Integer(m_hi)))
    steps = [
        Step(
            op="read_half_of_total",
            args=[],
            result_srepr="",
            result_display=f"{_fmt_decimal(sympy.Rational(sum(freqs), 2))}",
            narration="縦軸で総度数の半分にあたる高さを決め、その高さの横線を引く。",
        ),
        Step(
            op="locate_median_class",
            args=[],
            result_srepr=srepr,
            result_display=disp,
            narration="折れ線がその高さを初めて上回る位置を見つけ、横軸でその階級の範囲を読み取る。",
        ),
    ]
    return Solution(answer=SymbolicAnswer(srepr=srepr, display=disp), steps=steps)


# ---------------------------------------------------------------------------
# g1_l58.graph_table Lv3: 2分布の度数折れ線を1つのグラフに重ねてかく
# ---------------------------------------------------------------------------
@register_solver("math.overlay_frequency_polygons")
def overlay_frequency_polygons(
    frequencies: object,
    frequencies_b: object,
    class_lo: object,
    class_width: object,
    group_a: object = "A",
    group_b: object = "B",
    unit: object = "",
) -> Solution:
    """2つの分布の度数折れ線の頂点を、同じ階級の目盛の上で決める。

    2本の度数列・階級の下限・階級の幅だけから求める（double-solve）。2本が同一なら
    重ねて比べる意味がない退化なので例外にする。組の名前と単位は表示のためだけに使い、
    どちらの系列かの機械的な区別は特徴の kind と srepr の記号が担う。
    答えは GraphAnswer（2本ぶんの頂点）。
    """
    fa, fb = _ints(frequencies), _ints(frequencies_b)
    if len(fa) != len(fb):
        raise ValueError("2つの度数列の階級数が違う")
    if fa == fb:
        raise ValueError("2つの分布が同一で重ねて比べる意味がない")
    lo = int(str(class_lo))
    width = int(str(class_width))
    u = str(unit)
    names = {"polygon_vertex_a": str(group_a), "polygon_vertex_b": str(group_b)}

    features: list[Feature] = []
    for kind, series in (("polygon_vertex_a", fa), ("polygon_vertex_b", fb)):
        for i, f in enumerate(series):
            mid = sympy.Rational(2 * (lo + width * i) + width, 2)
            features.append(
                Feature(
                    kind=kind,
                    srepr=sympy.srepr(sympy.Tuple(sympy.Symbol(kind), mid, sympy.Integer(f))),
                    display=f"{names[kind]}の折れ線の頂点（階級値{_fmt_decimal(mid)}{u}、度数{f}人）",
                )
            )

    steps = [
        Step(
            op="plot_first_polygon",
            args=[],
            result_srepr="",
            result_display="1本目の折れ線",
            narration="一方の組について、各階級の階級値の位置にその階級の度数の高さで点を打ち、順に結ぶ。",
        ),
        Step(
            op="plot_second_polygon",
            args=[],
            result_srepr="",
            result_display="同じ目盛の上に重ねた2本の折れ線",
            narration="もう一方の組も、同じ横軸・縦軸の目盛の上に同じ手順でかく。",
        ),
        Step(
            op="overlay_for_comparison",
            args=[],
            result_srepr="",
            result_display="線の種類を変えて重ねる",
            narration="どちらの折れ線かを見分けられるよう、片方を実線、もう片方を破線にして重ねてかく。",
        ),
    ]
    return Solution(answer=GraphAnswer(features=features), steps=steps)


__all__ = [
    "read_distribution_chart",
    "tabulate_and_draw_histogram",
    "compare_distribution_shape",
    "relative_frequency_polygon",
    "cumulative_frequency_chart",
    "median_class_from_cumulative",
    "overlay_frequency_polygons",
]
