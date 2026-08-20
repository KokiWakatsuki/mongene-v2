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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from engine.core.rng import Rng, draw
from engine.packs.math.recipes.scene_vocab import VocabStep

# 役割の型。`total` は「合わせて N」、`diff` は「B は A より d 多い」。
ROLES_TOTAL = ("rate", "rate", "total", "amount")
ROLES_DIFF = ("rate", "rate", "diff", "amount")


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


def _admission_total(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    place = v["place"]
    first, second, asked = _two_tier(n)
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    return SceneText(
        scenario=(
            f"{place}の入園料は、大人1人{high}円、子ども1人{low}円である。"
            f"大人と子どもが合わせて{n['total']}人で入園し、"
            f"入園料の合計は{n['cost']}円だった。"
        ),
        quantities=f"{asked}の人数を x 人とする。",
        ask_formulation="入園料の関係を、x を使った方程式で表せ。",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label="入園料の合計",
        answer_unit="人",
        slots={"place": place, "counter": "人", "asked": asked},
    )


def _admission_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    place = v["place"]
    first, second, asked = _two_tier(n)
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    other = "子ども" if asked == "大人" else "大人"
    return SceneText(
        scenario=(
            f"{place}の入園料は、大人1人{high}円、子ども1人{low}円である。"
            f"ある団体が入園したところ、{other}は{asked}より{n['diff']}人多く、"
            f"入園料の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{asked}の人数を求めよ。",
        relation_label="入園料の合計",
        answer_unit="人",
        slots={"place": place, "counter": "人", "asked": asked},
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
    line = v["line"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "おとな" if n["price_a"] >= n["price_b"] else "こども"
    return SceneText(
        scenario=(
            f"{line}の乗車券は、おとな1枚{high}円、こども1枚{low}円である。"
            f"おとなとこどもの乗車券を合わせて{n['total']}枚買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities=f"{asked}の乗車券の枚数を x 枚とする。",
        ask_formulation="代金の関係を、x を使った方程式で表せ。",
        ask_value=f"{asked}の乗車券の枚数を求めよ。",
        relation_label="乗車券の代金の合計",
        answer_unit="枚",
        slots={"line": line, "counter": "枚", "asked": asked},
    )


def _ticket_diff(n: Mapping[str, int], v: Mapping[str, str]) -> SceneText:
    line = v["line"]
    high, low = max(n["price_a"], n["price_b"]), min(n["price_a"], n["price_b"])
    asked = "おとな" if n["price_a"] >= n["price_b"] else "こども"
    other = "こども" if asked == "おとな" else "おとな"
    return SceneText(
        scenario=(
            f"{line}の乗車券は、おとな1枚{high}円、こども1枚{low}円である。"
            f"{other}の乗車券を{asked}より{n['diff']}枚多く買い、"
            f"代金の合計は{n['cost']}円だった。"
        ),
        quantities="",
        ask_formulation="",
        ask_value=f"{asked}の乗車券の枚数を求めよ。",
        relation_label="乗車券の代金の合計",
        answer_unit="枚",
        slots={"line": line, "counter": "枚", "asked": asked},
    )


# カタログはこの file が持つ（YAML に足さなくても場面が増える）。
_PLACES = ("動物園", "植物園", "水族館", "遊園地", "科学館", "美術館")
_GROUPS = ("地域のクラブ", "スポーツクラブ", "合唱団", "ボランティア団体", "同好会")
_WORKS = ("かざりつけ", "工作", "看板づくり", "模型づくり", "花だんの手入れ")
_LINES = ("市内バス", "路線バス", "遊覧船", "ロープウェイ", "観光電車")
_MATERIALS = ("リボン|ひも", "赤いテープ|青いテープ", "太い針金|細い針金",
              "緑のモール|黄色のモール", "麻ひも|ビニールひも")

SCENES: tuple[SceneSpec, ...] = (
    SceneSpec(
        id="shopping",
        vocab=(("distinct2", "item_candidates",
                ("item_a", "counter_a", "item_b", "counter_b")),),
        render={ROLES_TOTAL: _shopping_total, ROLES_DIFF: _shopping_diff},
    ),
    SceneSpec(
        id="admission",
        vocab=(("one", _PLACES, ("place",)),),
        render={ROLES_TOTAL: _admission_total, ROLES_DIFF: _admission_diff},
        requires=(("入園料",), ("大人",), ("子ども",)),
        # 入園料は数百円〜千円台（実物の相場）。買い物の 40〜160円では成り立たない。
        limits={"rate": {"int_set": [300, 400, 500, 600, 700, 800, 900, 1000,
                                     1200, 1500], "distinct": ["value"]}},
    ),
    SceneSpec(
        id="stamp",
        vocab=(),
        render={ROLES_TOTAL: _stamp_total, ROLES_DIFF: _stamp_diff},
        requires=(("切手",),),
        # 切手は実在する額面だけ（1円・63円・84円・94円・110円・180円…）。
        limits={"rate": {"int_set": [50, 63, 84, 94, 110, 140, 180, 210, 290],
                         "distinct": ["value"]}},
    ),
    SceneSpec(
        id="fee",
        vocab=(("one", _GROUPS, ("group",)),),
        render={ROLES_TOTAL: _fee_total, ROLES_DIFF: _fee_diff},
        requires=(("会費",), ("大人",), ("中学生",)),
        # 会費は数百円〜数千円。
        limits={"rate": {"int_set": [500, 600, 800, 1000, 1200, 1500, 2000, 2500,
                                     3000], "distinct": ["value"]}},
    ),
    SceneSpec(
        id="ticket",
        vocab=(("one", _LINES, ("line",)),),
        render={ROLES_TOTAL: _ticket_total, ROLES_DIFF: _ticket_diff},
        requires=(("乗車券",), ("おとな",), ("こども",)),
        # 乗車券は数百円台。
        limits={"rate": {"int_set": [140, 180, 210, 250, 300, 350, 400, 480, 560],
                         "distinct": ["value"]}},
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


def draw_scene_spec(roles: tuple[str, ...], rng: Rng) -> SceneSpec:
    """場面を1つ引く（`draw` を1回だけ消費する＝順番の勘定が読める）。"""
    pool = scenes_for(roles)
    if not pool:
        raise ValueError(f"その役割の型に乗る場面が無い: {roles}")
    return pool[int(draw({"int_range": [0, len(pool) - 1]}, rng))]
