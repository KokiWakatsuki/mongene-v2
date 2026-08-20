# 式と場面の切り分け 設計（2026-08-17）

> ★**この文書のコマンドは `engine_core/` 時代のもの**（2026-08-20 にエンジンは
> `mongene-engine` へ移り、`engine_core/` は無くなった）。記録として残すため
> 本文は直していない。**現在の走らせ方は `records/README.md` を見ること。**
> `PYTHONPATH=engine_core` は存在しないパスなので Python が黙って無視する
> ＝古い書き方でも動いてしまう。動くことは正しさの証拠にならない。

**目的**: いまは式1つに場面1つが貼りついている（8組）。切って `関係 × 場面` の掛け算に
すれば、場面を1つ書くだけで全部の式に乗る。量産の下ごしらえ。

対象: `engine_core/engine/packs/math/recipes/word_problem_linear.py`（913行）。
同じ構造が `word_problem.py`（連立）・`word_problem_pythagorean.py` 等にもある。

---

## 1. いまの構造（読んで確かめた実物）

`params["scenario_kind"]` が**2つの辞書を同時に引く**。

```
scenario_kind = "price_count"
   ├→ _SCENE_DRAWERS["price_count"]        場面の数値を引き、日本語を書く
   └→ FORMULATION_BUILDERS["price_count"]  その数値から方程式を組む
```

`_scene_price_count` は1つの関数で**3つの仕事**をしている:

```python
def _scene_price_count(p, rng) -> LinearScene:
    total = draw(...); count_a = draw(...); price_a, price_b = draw_many(...)  # ① 数を引く
    cost = price_a * count_a + price_b * (total - count_a)                     # ② answer-first の逆算
    return LinearScene(
        numbers={"price_a": ..., "price_b": ..., "total": ..., "cost": ...},   # ③ 立式への受け渡し
        scenario=f"1{counter}{price_a}円の{item_a}と…買ったところ、代金の合計は{cost}円だった。",
        quantities=..., ask_formulation=..., ask_value=..., relation_label=..., ...)
```

**貼りついている理由は `numbers` のキー**。これは `FORMULATION_BUILDERS[kind]` の
キーワード引数そのもので、場面と式が同じ名前空間を共有している。

現在の8組:

| scenario_kind | 式 | 場面 |
|---|---|---|
| price_count | `a₁x + a₂(N−x) = T` | 2種類の品を合わせて N 個買う |
| price_count_diff | `a₁x + a₂(x+d) = T` | B は A より d 個多く買う |
| surplus_shortage | `ax + s = bx − t` | a 個ずつで s 余り、b 個ずつで t 足りない |
| seat_shortage | `ax + r = b(x−1) + q` | 最後の1脚だけ q 人 |
| round_trip | `x/a + x/b = t` | 往復の時間の和 |
| catch_up | `v₁(x+d) = v₂x` | 追いつく |
| proportion_pair | `ax = pb`（比例式） | 対応する量の比 |
| continued_ratio | `Rx = r₂N`（比例式） | 連比 |

---

## 2. 切り方 —— 2層でなく**3層**にする

「式」と「場面」を直接つなぐと切れない。間に**関係の型**を置く。

```
① 式 Formulation   … 代数だけ。役割名 → 方程式と mode
② 関係 Relation    … 役割が何を意味するか。answer-first の引き方と非退化条件を持つ
③ 場面 Scene       … ②の役割に日本語の衣を着せる。語彙と文型だけ
```

**なぜ3層か**: 場面文「1個140円のりんごと1個90円のレモンを合わせて12個買った」は、
すでに「2種類・単価・合計個数」という**関係を語っている**。関係を飛ばして式に
場面を直結すると、場面テンプレが式の形を丸ごと抱え込む＝いまと同じになる。

### 掛け算になる単位

- **関係**は式とほぼ1対1（`price_count` と `price_count_diff` は別の関係）
- **場面**は1つの関係に何個でも付く ← ここが増える

```
関係 two_kinds_total  ×  場面 {買い物, 入園料, 切手, 材料, 会費}   = 5
関係 two_kinds_diff   ×  場面 {買い物, 切手, 材料}                = 3
関係 distribute       ×  場面 {配る, 座る, 詰める, 分ける}         = 4
…
```

場面を1つ足すと、その場面が着られる**すべての関係**に乗る。

---

## 3. 型の定義（そのまま実装できる形）

### 3.1 Formulation（いまの `FORMULATION_BUILDERS` をほぼそのまま残す）

変えるのは**引数名を役割名に統一**すること。いまは `price_a`・`per_a`・`speed_go` と
場面の語で名づけられており、これが場面と式を縛っている。

```python
@dataclass(frozen=True)
class Formulation:
    name: str
    roles: tuple[str, ...]          # 例 ("rate_a", "rate_b", "count_total", "amount_total")
    build: Callable[..., LinearFormulation]   # roles をキーワードで受ける
```

```python
def formulate_two_kinds_total(*, rate_a, rate_b, count_total, amount_total):
    return _formulate(
        f"{rate_a}*x + {rate_b}*({count_total} - x)", f"{amount_total}",
        f"{rate_a}x + {rate_b}({count_total} - x) = {amount_total}", "word_linear")
```

役割名は**意味の型**で決める（`rate`＝1つあたり、`count`＝個数、`amount`＝合計量、
`speed`・`time`・`ratio`）。場面はこの型を見て、どの語で言うかを決める。

### 3.2 Relation（新設。数の引き方と非退化条件をここに集める）

```python
@dataclass(frozen=True)
class Relation:
    name: str
    formulation: Formulation
    # answer-first に数を引く。**日本語を1文字も書かない。**
    draw_numbers: Callable[[Mapping[str, Any], Rng], dict[str, int]]
    # 求める量 = m·x + n（過不足の応用のように x と問われる量が違う場合）
    answer_coeff: tuple[int, int] = (1, 0)
    # この関係が場面に要求する語彙の型（Scene 側が満たす契約）
    slot_types: tuple[tuple[str, str], ...] = ()
        # 例 (("rate_a", "unit_price"), ("rate_b", "unit_price"),
        #     ("count_total", "count"), ("amount_total", "amount"))
    # 立式の前に1手要る関係だけ（連比の和など）
    prelude: tuple[str, str, str] | None = None
```

いまの `_scene_*` から**日本語を抜いた残り**がそのまま `draw_numbers` になる。
非退化条件（`price_a != price_b`・`per_a < per_b`）もここに来る。

### 3.3 Scene（新設。日本語だけ）

```python
@dataclass(frozen=True)
class Scene:
    name: str
    fits: frozenset[str]            # 着られる関係の名前
    vocabulary: Callable[[Rng], dict[str, str]]   # 品名・助数詞・人名などを引く
    # 役割の値と語彙から文を組む。**数の抽選はしない**（もう引かれている）。
    render: Callable[[dict[str, int], dict[str, str]], SceneText]

@dataclass(frozen=True)
class SceneText:
    scenario: str          # 場面文
    quantities: str        # 「〜を x とする。」
    ask_formulation: str
    ask_value: str
    relation_label: str    # 立式の着眼点（解説の1手目に出る）
    answer_unit: str
    slots: dict[str, str]  # dup_key に載せる表層（品名など）
```

**場面は関係の役割名しか知らない。** 式の形は見ない。だから同じ場面が
`two_kinds_total` にも `two_kinds_diff` にも着られる。

### 3.4 recipe の変更

```python
kind = str(p["relation"])                    # 旧 scenario_kind
scene_name = str(draw(p["scene_candidates"], rng))   # ★ 場面を抽選する
relation = RELATIONS[kind]
scene = SCENES[scene_name]
assert kind in scene.fits                    # 契約違反は構成時に落とす

numbers = relation.draw_numbers(p, rng)
vocab = scene.vocabulary(rng)
text = scene.render(numbers, vocab)
formulation, sol, answer_value = solve_scene(kind, numbers, relation.answer_coeff)
```

---

## 4. ★守らなければいけない4つ（過去に踏んだ）

### 4-1. 増やした軸は `params` に載せる

`dup_key` は `params` だけから作られる。**`scene` を params に入れないと、
場面を5倍にしても dup_rate は1ミリも下がらない。**

```python
params = {..., "relation": kind, "scene": scene_name, "numbers": numbers, "slots": text.slots}
```

### 4-2. `params` の数値は全部問題文に出ていること（テストが強制）

`test_recipes.py` が `params["numbers"]` の各値が本文にあることを確かめている。
場面を変えても `numbers` は同じなので、**新しい場面文がすべての数を書いているか**を
必ず確かめる（1つでも落とすとテストが落ちる＝ここは自動で守られる）。

### 4-3. ★ゲートは「日本語と数式が合っているか」を見ていない

checker は `FORMULATION_BUILDERS` を**もう一度通す**（`solve_scene` を共有）。
つまり日本語がどうであれ double-solve は必ず一致する。

**場面を増やすと、ここが唯一の穴になる。** 新しい場面テンプレが
「合わせて12個」を「12個ずつ」と書き違えても、どのゲートも落ちない。

→ **G-BT（逆翻訳）を、(関係 × 場面) の組ごとに、複数 seed で回す。**
　 文型を数え上げて代表1件では足りない（引き継ぎ書 §2）。

### 4-4. 定義域は狭めない

場面が増えても数の引き方（`draw_numbers`）は触らない。dup が下がるのは
**場面という軸が増えるから**であって、数を絞るからではない。

---

## 5. 検査の作り方（新設ぶん）

### 5-1. 契約の検査（構成時・自動）

| 検査 | 内容 |
|---|---|
| `scene.fits` に無い関係を着せたら例外 | recipe の assert |
| `relation.slot_types` の役割を場面が全部埋めているか | `Scene.render` の戻りを検査 |
| 場面文に `numbers` の値が全部出ているか | 既存テストが見る（4-2） |
| 同じ関係の場面どうしで、`ask_value` の助数詞が答えの単位と合っているか | 新規 |

### 5-2. 逆翻訳（G-BT・人／サブエージェントが読む）

**手順**（`records/work/bt_patterns.py` の文型数え上げを土台にする）:

1. (関係 × 場面) の組ごとに seed を 5 本引き、**問題文だけ**を書き出す
   （答え・解説・params を渡さない。渡すと読み手が引きずられる）
2. 読み手に「この文から方程式を立てよ」と頼む
3. engine の `formulation.display` と突き合わせる
4. 食い違ったら、**場面文のほうを直す**（式は関係が持っている正）

**★1文型1件では足りない。** 同じ文型でも seed によって
「帰りだけ時速15km」のような**場面としてありえない値**が出る（引き継ぎ書 §5）。
だから seed を複数引き、値の妥当性も一緒に見る。

### 5-3. 走査（機械・全数）

新しい場面が増えるたび、既存の走査をそのまま当てる:

```bash
PYTHONPATH=engine_core .venv/bin/python records/work/build_corpus.py
PYTHONPATH=engine_core:records/work .venv/bin/python records/work/scan_explanations.py
PYTHONPATH=engine_core:records/work .venv/bin/python records/work/scan_surface.py
```

---

## 6. 実装の順序（この順でやれば途中で壊れない）

| # | やること | 確かめ方 |
|---|---|---|
| 1 | `Formulation` の引数名を役割名に統一（`price_a`→`rate_a` 等）。**振る舞いは変えない** | `check_cell` で8セルの出力が1文字も変わらないこと |
| 2 | `_scene_*` から数の抽選だけを抜いて `Relation.draw_numbers` に移す。日本語はまだ元のまま | 同上（出力不変） |
| 3 | 残った日本語を `Scene`（既存の場面＝各関係に1つ）にする。`SCENES` に登録 | 同上（出力不変） |
| 4 | ここまでで**構造だけが変わり、生成物は同一**。golden が全部通ることを確認 | `approve_all.py`（差分ゼロ） |
| 5 | 場面を1つ足す（例: `two_kinds_total` に「入園料」） | `check_cell` で dup_rate が下がることを実測 |
| 6 | G-BT を (関係 × 新場面) で5 seed 回す | 日本語だけを読ませて式を突き合わせ |
| 7 | 場面を残りぶん足す | 5〜6 を繰り返す |

**4 の「生成物が同一」を必ず通す。** ここを飛ばすと、構造を変えたのか中身を
変えたのかが分からなくなる（golden の差分がそれを教えてくれる）。

---

## 7. 最初に足す場面の候補（実物の問題集にある形）

| 関係 | いまの場面 | 足せる場面 |
|---|---|---|
| two_kinds_total | 2種類の品を買う | 入園料（大人・子ども）／切手（2種の額面）／会費（一般・学生） |
| two_kinds_diff | B は A より d 個多い | 切手／プリント（クラス別）／ジュースとお茶 |
| distribute（過不足） | 画用紙を配る | 折り紙を配る／みかんを分ける／ロープを切り分ける |
| seat（座席） | 長いすに座る | テントに分かれる／車に分乗する |
| round_trip | 往復の道のり | 上りと下り（川）／行きと帰りで手段が違う通学 |
| catch_up | 追いつく | 兄が忘れ物を届ける／自転車が徒歩を追う／バスと自転車 |
| ratio | 代金の比 | 材料の比（小麦粉と砂糖）／人数の比／縮尺 |

**★場面を書くときの落とし穴**（読んで見つけた実物）:
- 「帰りだけ時速15km」のように、**同じ道を非現実的な速さで戻る**設定にしない
- 助数詞と品物を必ず対で引く（`"ノート|冊"` の記法。既存）
- 値段は品物の相場に収める（`(品物, 値段)` を**平らにして1回で引く**。2段だと dup が跳ねる）
- 人・動物には「いる」、物には「ある」

---

## 8. この設計で解けないこと（正直に）

- **関係そのものは増えない。** 場面を掛けても式の型は8のまま。式を増やすには
  `Relation` を書き足す（それは別の作業）
- **関係と場面の相性は人が決める**（`fits` を手で書く）。機械には
  「入園料に往復の時間は着られない」が分からない
- **G-BT は自動化できない**。日本語と数式の対応を機械が確かめられるなら、
  そもそも checker がそれをやれている
