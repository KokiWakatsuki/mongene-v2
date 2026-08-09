# 引き継ぎ（2026-08-09・残り proof 8セル / 中断時点）

ユーザーの指示で**実行中のタスクを全部止めた**時点の記録。止めたのは
`engine.eval` 全走・`check_cell`（g2_l41 Lv4）・`fit_domain`・サブエージェント2本。

---

## 1. 到達点

**台帳 630 / 実装 622（98.7%）**。`scratchpad/audit_progress.py` = 監査 OK。
このセッションの前半で、前セッションの未コミット分（作図9セル＋文字式の説明6セル）を
実測で検証して commit した（`896b8db`）。**残り8はすべて proof**。

| セル | 状態 |
|---|---|
| g2_l40 proof Lv4 | **✅ 完成・check_cell ALL_OK**（rejects=0/120・dup 0.01）※未コミット |
| g2_l42 proof Lv3 | **✅ 完成・check_cell ALL_OK**（rejects=0/120・dup 0.00）※未コミット |
| g2_l41 proof Lv4 | 🟡 実装済み・**check_cell が途中で止まった**（再実行するだけ） |
| g2_l38 proof Lv2/Lv3 | 🟡 サブエージェントが実装済み・**生成は通る**が check_cell 未実行 |
| g3_l51 Lv3/Lv4・g3_l52 Lv3 | 🔴 solver だけ（814行）・recipe/checker/template/family がまだ無い |

---

## 2. コミットされているもの（`896b8db`）

作図9セル（g1_l41〜l44・`recipes/construction.py`・答えは `GraphAnswer`）と、
文字式による数の性質の説明6セル（g2_l7/l8/g3_l13・`solvers/number_proof.py`）。
15セルすべて rejects=0/120・dup 0.00〜0.10、フルスイート 472 passed で確認済み。

---

## 3. 未コミットの変更（この時点の作業ツリー）

### 3.1 私（本体）が書いたもの — **g2_l40 Lv4 と g2_l42 Lv3 は検証済み**

```
M engine/packs/math/geometry/constructions_congruence.py    kite_diagonals / isosceles_equal_segments
M engine/packs/math/geometry/constructions_right_triangle.py equal_altitudes
M engine/packs/math/geometry/deduce.py                       _MAX_ROUNDS 12 -> 24
M engine/packs/math/geometry/render_text.py                  合同2回の証明で見出しを立て直す
M engine/curriculum/math/families/g2_l40.proof.yaml           Lv4 追加
M engine/curriculum/math/families/g2_l41.proof.yaml           Lv4 追加
M engine/curriculum/math/families/g2_l42.proof.yaml           Lv3 追加
M docs/proof_engine_design_2026-08-08.md                      進捗を 43/51・9/9 に更新
```

**新しい構成3つ（`geometry/constructions_*.py`）**

| 構成 | セル | 導出 |
|---|---|---|
| `kite_diagonals` | g2_l40 Lv4 | たこ形に対角線2本＋交点P。SSS（深さ1）→ 対応する角（2）→ **2つ目の合同** SAS（3）→ BP＝DP（4） |
| `isosceles_equal_segments` | g2_l41 Lv4 | 二等辺の辺上に BD＝CE。底角（1）→ SAS（2）→ DC＝EB（3） |
| `equal_altitudes` | g2_l42 Lv3 | 2頂点から対辺への垂線が等しい。RHS（1）→ ∠ABC＝∠ACB（2）→ AB＝AC（3） |

**機構の修正2件（どちらもこのセッションで見つけた本物の不具合）**

1. **`deduce._MAX_ROUNDS` が 12 で足りていなかった。**
   5点の図（`isosceles_equal_segments`）が**事実143個・最大深さ15・0.4秒**で
   「飽和しなかった」と落ちていた。等式が鎖でつながる図は、事実が増えなくても
   深さだけ伸びる。**本当の歯止めは深さではなく事実の数**なので 24 に上げた。
   既に飽和する図は `added=False` で抜けるので遅くならない。
   → メモリの「点を6つにすると飽和しない」は、この訂正とセットで読むこと。

2. **合同を2回使う証明で、冒頭の見出しのまま2組目の条件を並べていた。**
   「（証明）△ABC と △ADC において … AP は共通 …」＝ △ABC の辺でないものが
   見出しの下に載っていた。`render_text.build_proof_lines` を**比べる三角形が
   変わるところで段に分ける**ように直し、仮定の行も「最初に使う段」に置いた
   （番号も上から順に並ぶ）。`render_proof` が段の頭に
   「次に、△ABP と △ADP において」を出す。**合同1回の証明の出力は変わらない**
   （g2_l40 Lv2/Lv3・g2_l49 Lv2 で確認済み）。

出来上がりの例（g2_l40 Lv4・seed 3）:

```
右の図で、AB ＝ AD、CB ＝ CD である四角形ABCDに対角線AC、BDを引き、その交点をPとした。
このとき、BP ＝ DP であることを証明せよ。

（証明）△ABC と △ADC において
　　仮定より　　AB ＝ AD　…①
　　仮定より　　BC ＝ CD　…②
　　AC は共通　…③
　　①、②、③より、3組の辺がそれぞれ等しいので
　　　△ABC ≡ △ADC　…④
　　④より、合同な図形では対応する辺（角）はそれぞれ等しいので
　　　∠BAP ＝ ∠DAP　…⑤
　　次に、△ABP と △ADP において
　　AP は共通　…⑥
　　①、⑥、⑤より、2組の辺とその間の角がそれぞれ等しいので
　　　△ABP ≡ △ADP　…⑦
　　⑦より、合同な図形では対応する辺（角）はそれぞれ等しいので
　　　BP ＝ DP
```

### 3.2 サブエージェントが書いたもの（**未検証**）

```
?? engine/curriculum/math/families/g2_l38.proof.yaml   （85行・Lv2/Lv3）
?? engine/packs/math/solvers/conditional_proof.py      （853行）
?? engine/packs/math/recipes/conditional_proof.py      （164行）
?? engine/packs/math/checkers/conditional_proof.py     （23行）
?? engine/packs/math/templates/conditional_proof.py    （30行）
M  engine/packs/math/{solvers,recipes,checkers,templates}/__init__.py  （import 追加）
M  engine/curriculum/math/concepts.yaml                （概念2件 proof_logic.*）
?? engine/packs/math/solvers/pythagoras_proof.py       （814行・**単体では未配線**）
```

**g2_l38（仮定と結論・反例）は生成まで通ることを確認した**（import OK・Lv2/Lv3 とも
`generate` が例外なく通る）。実際に出た問題文:

- Lv2: 「r が10の倍数ならば、3r + 7 は奇数である」ことを、r = 10w（w は整数）とおいて証明せよ。
- Lv3: 「h が5の倍数、k が奇数ならば、h - k は3の倍数である」という命題が正しいかどうかを判断し、正しければ証明を、正しくなければ反例を示せ。

台帳の desc/example と型が合っている。**ただし check_cell（rejects/dup の実測）も
pytest も回していない。** 中身のレビューもしていない。

**三平方（g3_l51/l52）は solver 1本だけで、recipe も family も無い＝台帳には載らない。**
`REGISTRY._solvers` に `pythagoras_proof` 系は1つも登録されていない（`register_solver`
まで到達していないか、`__init__.py` に import が無い）。

---

## 4. 次にやること（この順で）

1. **`PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py g2_l41 proof 4`**
   （実装は入っている。定義域は粗格子 309/648＝48% を実測済みなので、
   24回の引き直しで rejects は出ないはず。落ちたら `scratchpad/fit_domain.py` で測り直す）
2. **`check_cell g2_l38 proof 2,3`** ＋ `conditional_proof.py` 4本のレビュー
   （サブエージェントの報告を受け取れていないので、**中身は自分で読むこと**）
3. **三平方3セル**を仕上げる。`solvers/pythagoras_proof.py` が使えるかを最初に判断する
   （使えないなら捨てて書き直すほうが早い）。recipe / checker / template / family と
   `__init__.py` の import・`concepts.yaml`・recipe の `provides_concepts` が要る。
4. 8セルそろったら **`audit_progress.py` → `pytest -q` → `engine.eval`**（約20分・exit 0 が DoD）。
   **eval はテスト緑とは別に必ず回す**（fp = op 列なので、Lv 間で op 列が同じだと
   level_sep が黙って壊れる）。
5. `test_unsupported_codes.py` の `not_implemented` 座標（現在 exam_l6.proof Lv3）は
   実装済みになったら差し替える。

## 5. 別件（作業チップに切り出し済み）

結論が四角形の種類になる証明セルで、問題文が
「四角形ABCD は長方形である **であることを証明せよ**」と二重になっている
（再現: `scratchpad/peek.py g2_l49 proof 2 3`）。原因は
`templates/plane_geometry.py` の `{{ given.conclusion }} であることを証明せよ` と
`facts.fact_text` が四角形の述語を**文の形**で返すことの噛み合わせ。

## 6. 実測コマンド

```bash
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py           # 進捗更新前に必ず
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> proof <lv,lv>
PYTHONPATH=. .venv/bin/python scratchpad/peek.py <unit> proof <lv> <seed>
PYTHONPATH=. .venv/bin/python scratchpad/fit_domain.py <構成名> <depth> --prefer seg_eq --topic <topic_set>
PYTHONPATH=. .venv/bin/python scratchpad/draw_l40_l42.py             # 図をPNGに起こして目視
PYTHONPATH=. .venv/bin/python -m pytest -q                           # 472 passed
PYTHONPATH=. .venv/bin/python -m engine.eval                         # 約20分・exit 0 が DoD
```

**シェルは zsh。`python` は無い（`.venv/bin/python`）。`timeout` コマンドも無い。**
