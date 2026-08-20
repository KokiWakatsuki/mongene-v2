"""場面の置き場（**日本語と語彙だけ**）。式も数の抽選も持たない。

## この file だけを触れば場面が増える

「式と場面の切り離し」の目的は、1つの関係（式の型）に**何通りもの場面**を乗せられる
ようにすることだった（記録 records/docs/scene_formulation_charter_2026-08-19.md）。
関係・語彙・場面に割ったのが作業1で、ここは**場面だけを集めた置き場**である。

場面を1つ足すときに触るのはこの file だけ——式（`formulate_*`）・checker・テストには
何も足さない。それが「切り離せた」の判定になる（charter §4 作業3）。

## 役割の型（`roles`）が同じなら、場面は関係をまたいで乗る

    ax + b(N − x) = T   合わせて N 個      roles = ("rate", "rate", "total", "amount")
    ax + b(x + d) = T   B は A より d 多い  roles = ("rate", "rate", "diff",  "amount")

言う中身（1つあたり・個数・合計）は同じで、**個数の与え方だけが違う**。だから場面は
「合わせて N」の言い方と「d 多い」の言い方を両方持ち、どちらの関係にも乗る。
`SceneSpec.render` が役割の型ごとの書き手を持つのはこのためである。

## 語彙は宣言する（数は引かない）

`vocab` は `scene_vocab.draw_vocab` に渡す宣言。場面の書き手（`render`）は
**引かれた数 `n` と語彙 `v` を受け取って文を組むだけ**で、`rng` を受け取らない。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from engine.core.rng import Rng, draw
from engine.packs.math.recipes.scene_vocab import VocabStep

# 役割の型。`total` は「合わせて N」、`diff` は「B は A より d 多い」。
ROLES_TOTAL = ("rate", "rate", "total", "amount")
ROLES_DIFF = ("rate", "rate", "diff", "amount")
# 作業3 で足した式の役割の型。
# ★**新しい式は新しい役割の型を作る。** charter §3 は「役割の型が既存と同じなら
# 新しい式は既存の場面にそのまま乗る」としていたが、実際には「合わせて N 個」は
# 同じでも「代金の合計は T 円」が「A は B より D 円多い」に変わるので、
# **乗せたい場面の数だけ書き手が増える**（1つあたり 12〜16行）。
ROLES_GAP = ("rate", "rate", "total", "gap")      # 合わせて N 個・代金の差が D
ROLES_LESS = ("rate", "rate", "less", "amount")   # B は A より d 個少ない


@dataclass(frozen=True)
class SceneText:
    """場面が組んだ日本語。recipe 側の Scene に写して使う。"""

    scenario: str
    quantities: str
    ask_formulation: str
    ask_value: str
    relation_label: str
    answer_unit: str
    slots: dict[str, str]


@dataclass(frozen=True)
class SceneSpec:
    """1つの場面。**日本語と語彙の宣言だけ**を持つ。

    - `id`: params に載る（`dup_key` は params だけを見るので、場面を増やしても
      ここに載らなければ dup は1ミリも下がらない）
    - `render`: 役割の型 → 書き手。乗れる関係はここの鍵で決まる
    - `requires` / `forbids`: G-SC3（骨格）が見る、この場面が必ず使う／使わない言い方
    """

    id: str
    vocab: tuple[VocabStep, ...]
    render: dict[tuple[str, ...], Callable[[Mapping[str, int], Mapping[str, str]], SceneText]]
    requires: tuple[tuple[str, ...], ...] = ()
    forbids: tuple[str, ...] = field(default_factory=tuple)
    # ★**場面ごとに数の相場が違う。** 場面を足して最初に出たのがこれだった:
    #   「植物園の入園料は、大人1人130円、子ども1人110円」← 入園料が安すぎる
    # 関係（式）は数の引き方を持つが、**どの範囲がありえるかは場面が知っている**。
    # だから場面が定義域を上書きできるようにする（役割名 → ドメイン記法）。
    # 空なら関係の既定（YAML の params）をそのまま使う。
    limits: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 場面（1つあたり × 個数 = 合計）
# ---------------------------------------------------------------------------
def _shopping_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    item_a, item_b, counter = v["item_a"], v["item_b"], v["counter_a"]
    return SceneText(
        scenario=(
            f"1{counter}{n['price_a']}円の{item_a}と1{counter}{n['price_b']}円の{item_b}を"
            f"合わせて{n['total']}{counter}買ったところ、代金の合計は{n['cost']}円だった。"
        ),
        quantities=f"{item_a}を買った{counter}数を x {counter}とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{item_a}を買った{counter}数を求めよ。",
        relation_label="代金の合計",
        answer_unit=counter,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter},
    )


def _shopping_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    item_a, counter_a = v["item_a"], v["counter_a"]
    item_b, counter_b = v["item_b"], v["counter_b"]
    return SceneText(
        scenario=(
            f"ある店で、1{counter_a}{n['price_a']}円の{item_a}と"
            f"1{counter_b}{n['price_b']}円の{item_b}を"
            f"買った。{item_b}は{item_a}より{n['diff']}{counter_b}多く買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{item_a}を買った{counter_a}数を求めよ。",
        relation_label="代金の合計",
        answer_unit=counter_a,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter_a},
    )


def _two_tier(n: Mapping[str, int]) -> tuple[str, str, str]:
    """2段の料金を「高いほう・安いほう」に振り分け、**x が指す側の名前**を返す。

    ★式は `price_a·x + price_b·(…)` なので **x は必ず price_a の側**である。
    どちらを「大人」と呼ぶかを固定すると、price_a < price_b の回に
    「大人90円・子ども120円」（子どものほうが高い）が出る——場面として成り立たない。
    高いほうを大人と呼び、**問う相手を price_a の側に合わせる**。
    """
    if n["price_a"] >= n["price_b"]:
        return "大人", "子ども", "大人"
    return "子ども", "大人", "子ども"


def _shopping_gap(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    item_a, item_b, counter = v["item_a"], v["item_b"], v["counter_a"]
    return SceneText(
        scenario=(
            f"1{counter}{n['price_a']}円の{item_a}と1{counter}{n['price_b']}円の{item_b}を"
            f"合わせて{n['total']}{counter}買ったところ、"
            f"{item_a}の代金は{item_b}の代金より{n['gap']}円多かった。"
        ),
        quantities=f"{item_a}を買った{counter}数を x {counter}とする。",
        ask_formulation="代金の差の関係を、x を使った方程式で表せ。",
        ask_value=f"{item_a}を買った{counter}数を求めよ。",
        relation_label="2つの代金の差",
        answer_unit=counter,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter},
    )


def _shopping_less(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    item_a, counter_a = v["item_a"], v["counter_a"]
    item_b, counter_b = v["item_b"], v["counter_b"]
    return SceneText(
        scenario=(
            f"ある店で、1{counter_a}{n['price_a']}円の{item_a}と"
            f"1{counter_b}{n['price_b']}円の{item_b}を"
            f"買った。{item_b}は{item_a}より{n['diff']}{counter_b}少なく買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{item_a}を買った{counter_a}数を求めよ。",
        relation_label="代金の合計",
        answer_unit=counter_a,
        slots={"item_a": item_a, "item_b": item_b, "counter": counter_a},
    )


def _stamp_gap(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    return SceneText(
        scenario=(
            f"{n['price_a']}円切手と{n['price_b']}円切手を"
            f"合わせて{n['total']}枚買ったところ、"
            f"{n['price_a']}円切手の代金は{n['price_b']}円切手の代金より{n['gap']}円多かった。"
        ),
        quantities=f"{n['price_a']}円切手を買った枚数を x 枚とする。",
        ask_formulation="代金の差の関係を、x を使った方程式で表せ。",
        ask_value=f"{n['price_a']}円切手を買った枚数を求めよ。",
        relation_label="2つの代金の差",
        answer_unit="枚",
        slots={"counter": "枚"},
    )


def _stamp_less(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    return SceneText(
        scenario=(
            f"{n['price_a']}円切手と{n['price_b']}円切手を買った。"
            f"{n['price_b']}円切手は{n['price_a']}円切手より{n['diff']}枚少なく、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{n['price_a']}円切手を買った枚数を求めよ。",
        relation_label="代金の合計",
        answer_unit="枚",
        slots={"counter": "枚"},
    )


def _admission_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    place, fee = v["place"], v["fee_name"]
    first, second, asked = _two_tier(n)
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    enter = "入園" if fee == "入園料" else "入館"
    return SceneText(
        scenario=(
            f"{place}の{fee}は、大人1人{high}円、子ども1人{low}円である。"
            f"大人と子どもが合わせて{n['total']}人で{enter}し、"
            f"{fee}の合計は{n['cost']}円だった。"
        ),
        quantities=f"{asked}の人数を x 人とする。",
        ask_formulation=f"{fee}の関係を、x を使った方程式で表せ。",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label=f"{fee}の合計",
        answer_unit="人",
        slots={"place": place, "counter": "人", "asked": asked, "fee_name": fee},
    )


def _admission_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    place, fee = v["place"], v["fee_name"]
    first, second, asked = _two_tier(n)
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    other = "子ども" if asked == "大人" else "大人"
    enter = "入園" if fee == "入園料" else "入館"
    return SceneText(
        scenario=(
            f"{place}の{fee}は、大人1人{high}円、子ども1人{low}円である。"
            f"ある団体が{enter}したところ、{other}は{asked}より{n['diff']}人多く、"
            f"{fee}の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label=f"{fee}の合計",
        answer_unit="人",
        slots={"place": place, "counter": "人", "asked": asked, "fee_name": fee},
    )


def _stamp_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    return SceneText(
        scenario=(
            f"{n['price_a']}円切手と{n['price_b']}円切手を"
            f"合わせて{n['total']}枚買ったところ、代金の合計は{n['cost']}円だった。"
        ),
        quantities=f"{n['price_a']}円切手を買った枚数を x 枚とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{n['price_a']}円切手を買った枚数を求めよ。",
        relation_label="代金の合計",
        answer_unit="枚",
        slots={"counter": "枚"},
    )


def _stamp_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    return SceneText(
        scenario=(
            f"{n['price_a']}円切手と{n['price_b']}円切手を買った。"
            f"{n['price_b']}円切手は{n['price_a']}円切手より{n['diff']}枚多く、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{n['price_a']}円切手を買った枚数を求めよ。",
        relation_label="代金の合計",
        answer_unit="枚",
        slots={"counter": "枚"},
    )


def _fee_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    group = v["group"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "大人" if n["price_a"] >= n["price_b"] else "中学生"
    return SceneText(
        scenario=(
            f"{group}の会費は、大人1人{high}円、中学生1人{low}円である。"
            f"大人と中学生が合わせて{n['total']}人集まり、"
            f"会費の合計は{n['cost']}円になった。"
        ),
        quantities=f"{asked}の人数を x 人とする。",
        ask_formulation="会費の関係を、x を使った方程式で表せ。",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label="会費の合計",
        answer_unit="人",
        slots={"group": group, "counter": "人", "asked": asked},
    )


def _fee_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    group = v["group"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "大人" if n["price_a"] >= n["price_b"] else "中学生"
    other = "中学生" if asked == "大人" else "大人"
    return SceneText(
        scenario=(
            f"{group}の会費は、大人1人{high}円、中学生1人{low}円である。"
            f"{other}は{asked}より{n['diff']}人多く集まり、"
            f"会費の合計は{n['cost']}円になった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label="会費の合計",
        answer_unit="人",
        slots={"group": group, "counter": "人", "asked": asked},
    )


def _material_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    work, mat_a, mat_b = v["work"], v["material_a"], v["material_b"]
    return SceneText(
        scenario=(
            f"{work}に、1本{n['price_a']}円の{mat_a}と1本{n['price_b']}円の{mat_b}を"
            f"合わせて{n['total']}本使ったところ、材料費の合計は{n['cost']}円だった。"
        ),
        quantities=f"{mat_a}を使った本数を x 本とする。",
        ask_formulation="材料費の関係を、x を使った方程式で表せ。",
        ask_value=f"{mat_a}を使った本数を求めよ。",
        relation_label="材料費の合計",
        answer_unit="本",
        slots={"work": work, "material_a": mat_a, "material_b": mat_b, "counter": "本"},
    )


def _material_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    work, mat_a, mat_b = v["work"], v["material_a"], v["material_b"]
    return SceneText(
        scenario=(
            f"{work}に、1本{n['price_a']}円の{mat_a}と1本{n['price_b']}円の{mat_b}を"
            f"使った。{mat_b}は{mat_a}より{n['diff']}本多く使い、"
            f"材料費の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{mat_a}を使った本数を求めよ。",
        relation_label="材料費の合計",
        answer_unit="本",
        slots={"work": work, "material_a": mat_a, "material_b": mat_b, "counter": "本"},
    )


def _ticket_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    line, ticket = v["line"], v["ticket_name"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "おとな" if n["price_a"] >= n["price_b"] else "こども"
    return SceneText(
        scenario=(
            f"{line}の{ticket}は、おとな1枚{high}円、こども1枚{low}円である。"
            f"おとなとこどもの{ticket}を合わせて{n['total']}枚買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities=f"{asked}の{ticket}の枚数を x 枚とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{asked}の{ticket}の枚数を求めよ。",
        relation_label=f"{ticket}の代金の合計",
        answer_unit="枚",
        slots={"line": line, "counter": "枚", "asked": asked, "ticket_name": ticket},
    )


def _ticket_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    line, ticket = v["line"], v["ticket_name"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "おとな" if n["price_a"] >= n["price_b"] else "こども"
    other = "こども" if asked == "おとな" else "おとな"
    return SceneText(
        scenario=(
            f"{line}の{ticket}は、おとな1枚{high}円、こども1枚{low}円である。"
            f"{other}の{ticket}を{asked}より{n['diff']}枚多く買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{asked}の{ticket}の枚数を求めよ。",
        relation_label=f"{ticket}の代金の合計",
        answer_unit="枚",
        slots={"line": line, "counter": "枚", "asked": asked, "ticket_name": ticket},
    )


# カタログはこの file が持つ（YAML に足さなくても場面が増える）。
# ★**施設と料金名は対で決まる。** 施設名だけを差し替えていたので
# 「美術館の入園料」「水族館の入園料」「科学館の入園料」が出ていた（園ではないので
# 実物は「入館料」）。G-BT の読み手が4件挙げた。品名と助数詞と同じ扱いにする。
_PLACES = ("動物園|入園料", "植物園|入園料", "遊園地|入園料",
           "水族館|入館料", "科学館|入館料", "美術館|入館料")
_GROUPS = ("地域のクラブ", "スポーツクラブ", "合唱団", "ボランティア団体", "同好会")
_WORKS = ("かざりつけ", "工作", "看板づくり", "模型づくり", "花だんの手入れ")
# ★船は「乗船券」（同じ穴）。
_LINES = ("市内バス|乗車券", "路線バス|乗車券", "観光電車|乗車券",
          "ロープウェイ|乗車券", "遊覧船|乗船券")
_MATERIALS = ("リボン|ひも", "赤いテープ|青いテープ", "太い針金|細い針金",
              "緑のモール|黄色のモール", "麻ひも|ビニールひも")

SCENES: tuple[SceneSpec, ...] = (
    SceneSpec(
        id="shopping",
        vocab=(("distinct2", "item_candidates",
                ("item_a", "counter_a", "item_b", "counter_b")),),
        render={ROLES_TOTAL: _shopping_total, ROLES_DIFF: _shopping_diff,
                ROLES_GAP: _shopping_gap, ROLES_LESS: _shopping_less},
    ),
    SceneSpec(
        id="admission",
        vocab=(("one", _PLACES, ("place", "fee_name")),),
        render={ROLES_TOTAL: _admission_total, ROLES_DIFF: _admission_diff},
        # 料金名は施設で変わる（園なら入園料・館なら入館料）。
        requires=(("入園料", "入館料"), ("大人",), ("子ども",)),
        # 入園料は数百円〜千円台（実物の相場）。買い物の 40〜160円では成り立たない。
        # ★**(大人, 子ども) を対で引く。** 別々に引くと「大人2500円・中学生2000円」の
        # ように差が小さく、区分を分ける意味が無い場面が出る（読み手が指摘）。
        # (品物,値段) を平らにして1回で引くのと同じ手。
        limits={"rate_pairs": ("1500|700", "1200|600", "1000|500",
                               "900|450", "800|400", "600|300")},
    ),
    SceneSpec(
        id="stamp",
        vocab=(),
        render={ROLES_TOTAL: _stamp_total, ROLES_DIFF: _stamp_diff,
                ROLES_GAP: _stamp_gap, ROLES_LESS: _stamp_less},
        requires=(("切手",),),
        # 切手は実在する額面だけ（1円・63円・84円・94円・110円・180円…）。
        # ★実在する額面だけ（180円・290円は実在しない＝読み手が指摘）。
        limits={"rate": {"int_set": [50, 63, 84, 94, 110, 140, 210, 320],
                         "distinct": ["value"]}},
    ),
    SceneSpec(
        id="fee",
        vocab=(("one", _GROUPS, ("group",)),),
        render={ROLES_TOTAL: _fee_total, ROLES_DIFF: _fee_diff},
        requires=(("会費",), ("大人",), ("中学生",)),
        # 会費は数百円〜数千円。大人と中学生の差は2倍前後（対で引く）。
        limits={"rate_pairs": ("3000|1500", "2500|1200", "2000|1000",
                               "1500|800", "1200|600", "1000|500")},
    ),
    SceneSpec(
        id="ticket",
        vocab=(("one", _LINES, ("line", "ticket_name")),),
        render={ROLES_TOTAL: _ticket_total, ROLES_DIFF: _ticket_diff},
        # 券名は乗り物で変わる（船は乗船券）。
        requires=(("乗車券", "乗船券"), ("おとな",), ("こども",)),
        # 乗車券は数百円台。おとなとこどもは2倍（実物の運賃の決まり）。
        limits={"rate_pairs": ("560|280", "480|240", "400|200",
                               "350|180", "300|150", "250|130")},
    ),
    SceneSpec(
        id="material",
        vocab=(("one", _WORKS, ("work",)),
               ("one", _MATERIALS, ("material_a", "material_b"))),
        render={ROLES_TOTAL: _material_total, ROLES_DIFF: _material_diff},
        requires=(("材料費",),),
    ),
)


def scenes_for(roles: tuple[str, ...]) -> tuple[SceneSpec, ...]:
    """その役割の型に乗れる場面（宣言順）。"""
    return tuple(s for s in SCENES if roles in s.render)


def draw_scene_spec(
    roles: tuple[str, ...], rng: Rng, allow: Sequence[str] = ()
) -> SceneSpec:
    """場面を1つ引く（`draw` を1回だけ消費する＝順番の勘定が読める）。

    `allow` は設計書（family YAML の `scenes`）が選んだ名前。空なら棚の全部から引く
    ＝これまでの動き。**絞っても `draw` の回数は変わらない**ので、
    絞っていないセルの生成物は1文字も動かない。
    """
    pool = scenes_for(roles)
    if allow:
        pool = tuple(s for s in pool if s.id in allow)
    if not pool:
        raise ValueError(
            f"その役割の型に乗る場面が無い: {roles}"
            + (f"（設計書が選んだ場面={list(allow)}）" if allow else "")
        )
    return pool[int(draw({"int_range": [0, len(pool) - 1]}, rng))]
