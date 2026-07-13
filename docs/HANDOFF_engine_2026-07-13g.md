# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13g・P2 の C1 knowledge 総ざらいセッション）

本書は **Phase P2 を継続し、C1（g1 数と式）の残 knowledge を term_recall / recall_rule /
verify・classify の各インフラで一気に横展開したセッション**（#60〜#69・10コミット）の引き継ぎ。
前回 `docs/HANDOFF_engine_2026-07-13f.md`（記法＋knowledge・109/630）の続き。**本書＝最新**。
ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§4 資産・§5 指示文。
3. `docs/HANDOFF_engine_2026-07-13f.md`（記法／knowledge の定石・§2-#2 surface を params に）／
   `docs/HANDOFF_engine_2026-07-13e.md`（一次方程式 分母払い/比例式）／
   `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。

---

## 0.5 実行の勘所（13d/13e/13f §0.5 が正・要点のみ）
- **property は lru_cache で数秒**（`pytest engine_tests/unit/test_recipes.py -k "<断片>"` フォアグラウンド）。
- **フルスイートは `-n auto` で約4分**（本セッション 17150+ passed）。exit code は **pipestatus** で見る
  （fish は `$pipestatus[2]`）。★フルスイートを**背景実行しながら新 yaml を書くと**、`test_all_m0_families_
  lint_clean` が**書きかけの families を読んで一時的に落ちる**（concept 未追加の刹那）。落ちても
  ファイル群が整合すれば通る＝**偽陽性**。最終検証は編集完了後に単独で回すこと（§2-#5）。
- **spec check は遅い（1 family 30〜60秒・背景可）／check_cell は速い（共有 env・数十秒）**。日常 DoD は
  check_cell、最終署名は spec check→approve。check_cell.py は ChoiceAnswer 対応済。

---

## 1. 現状サマリ（2026-07-13g・本セッション終了時）

**進捗: capabilities 128/630（20.3%）**（`python -m engine.tools.goal_progress`・exit 0）。最新コミット `0f00e28`（#69）。
- **C1 g1 数と式: 62/69（90%）** ← 本セッション +19セル（#60〜#69・すべて knowledge）。
- C2 32/32（完成）・C5 34/36。他グループ未着手。

### 本セッションの10コミット（#60〜#69・各1〜4家系を DoD 全緑でコミット）

| # | セル | solver / signature | 要点 |
|---|---|---|---|
| #60 | g1_l20 不等号 Lv1 | term_recall(domain=inequality) | 以上/以下/未満/超→≧≦<>。記号答え用に step narration を domain 特化（既定不変＝既存 golden 維持）。専用 template |
| #61 | g1_l22 移項 Lv1 | **math.recall_rule_statement**（新設） | 規則の**正しい記述を選ぶ**型。用語想起と別の汎用ハブ。`_RULE_MAPS[topic][concept]=(正,誤リスト)` |
| #62 | g1_l3/l4/l5 Lv1 | recall_rule（addition_sign/subtraction/term_in_sum） | 加法符号規則・減法→加法・項の意味。★答えに ASCII 数字禁止（`2数`→`両方の数`・`1つ1つ`→`それぞれ`） |
| #63 | g1_l10 Lv1 | term_recall(domain=number_set) | 自然数/整数。2 concept で dup 0.24→**相異2値の例**で 0.0 |
| #64 | g1_l15/l12 Lv1 | recall_rule（speed_relation/letter_meaning） | 速さ=道のり÷時間 等・文字式の利点。求める量以外の場面を surface に（求める量の数値は出さない） |
| #65 | g1_l1 Lv1/Lv2 | **classify_number_sign** / **represent_opposite_quantity**（新設） | 正負分類・反対の性質の量を符号で。Lv2 も form=knowledge のため ChoiceAnswer（±m の2択）化 |
| #66 | g1_l10 Lv2 | **judge_set_closure**（新設） | 四則の閉性（真偽表）。閉じている/閉じていない。要素例のみ surface（誤解を招く演算例は出さない） |
| #67 | g1_l7/l9/l11 Lv1 | term_recall（power/laws/prime_concepts） | 累乗用語・法則名・素数用語。★**l11 は保留を解除**（判別でなく「意味想起」に軸足→dup 回避） |
| #68 | g1_l6/l8/l13/l14 Lv1 | recall_rule（product_sign/reciprocal/notation_product_rule/notation_quotient_rule） | 積の符号・逆数・乗除の記法規則。l13/l14 は数のみで dup>0.4→**例の文字も振って**分散 |
| #69 | g1_l60 Lv1 | term_recall(domain=approximation) | 近似値/誤差/有効数字の意味 |

### 再開時の最初のコマンド
```bash
cd /Users/koki/workspace/mongene-v2
git log --oneline -6                                        # 最新 0f00e28(#69)
git status --porcelain                                      # 空(clean)。scratchpad/ は未追跡で無視
.venv/bin/python -m engine.tools.goal_progress             # 128/630・C1 62/69・exit0
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
```
> 本セッション終了時のフルスイートは緑（EXIT=0）を確認済み。既存 golden の陳腐化ゼロ
> （term_recall の step narration は domain 別辞書化したが既定文は現行と完全一致＝既存 golden 不変）。

---

## 2. このセッションで得た「新しい学び」

1. **★knowledge は3つの汎用ソルバで大半を償却できる**。C1 の残 knowledge 19セルを
   （a）**term_recall_definition(concept, domain)** ＝説明→名称/記号を選ぶ（`_TERM_MAPS[domain]`）、
   （b）**recall_rule_statement(topic, concept)** ＝規則の正しい記述を選ぶ（`_RULE_MAPS[topic][concept]=
   (正記述, 誤記述リスト)`）、（c）小さな **classify/verify** ソルバ（classify_number_sign・
   judge_set_closure・represent_opposite_quantity）で実装できた。**新セルは domain/topic を1つ足すだけ**
   （solver・recipe surface・concepts.yaml・yaml・test の5点セット）。用語＝term_recall、規則/理由/やり方＝
   recall_rule、分類/判定＝小 verify、が振り分けの目安。
2. **★答えテキストに ASCII 数字を入れない（knowledge の鉄則）**。ChoiceAnswer の correct/distractor に
   `2数`・`1つ1つ`・`積が1`・`2乗` 等が混ざると property の no-digit 検査（＝G-Q5t 素通り条件）に落ちる。
   → `両方の数`・`それぞれ`・`逆数をかける`・`大きくして` 等に**言い換える**。**surface（given/statement）側は
   数字 OK**（漏洩検査は答え側のみ）。漢数字「一」は `isdigit()` False で安全だが読みが不自然なので避けた。
3. **★dup は「振れる自由度の個数」で決まる**。concept が2〜3個しか無いセルは surface の可変要素が少ないと
   dup>0.20 に落ちる（l7 底のみ 0.24／l10 数1個 0.24／l13-14 数のみ 0.47-0.65／l11 小プール 0.28）。
   **対策の定石**：①域を広げる（l7 底[2,50]）②**独立した2値を例に入れる**（l10 相異2整数・l11 相異2素数）
   ③**別種の自由度を足す**（l13/l14 は数だけでなく**文字も振る**）。100 seed の birthday 近似
   `dup≈N²/(2·組合せ数)` で 400+ 組合せあれば ≤0.20 に収まる。
4. **★form=knowledge は G-Q2 で `asked=choice` のみ許容**。数値答えにしたい apply 系（l1 Lv2 反対量）も
   **ChoiceAnswer 化**が必要（±m の2択＝符号判断が学習点に落ちる）。`asked=value`/`signed_value` は
   knowledge frame の asked_vocab 外で 120/120 拒否になる（G-Q2）。calc form なら value 可。
5. **★フルスイート背景実行と新 yaml 執筆を重ねると lint が偽陽性で落ちる**。`test_all_m0_families_
   lint_clean` はディスクの全 family を読むため、concept.yaml 追記前の刹那に family だけ在ると R6 で落ちる。
   **編集を全て終えてから単独で回して確認**すること（本セッションで一度観測・整合後は緑）。
6. **★答えが given 数値と一致する漏洩を構成で回避**（l1 Lv2）。反対の性質の量は**必ず反対向き（負）**を問い、
   答え -m を given の正数 m と一致させない（同じ向きを問うと答え +m が given m と一致し gate 素通りの実害）。
   §5-鉄則④の具体適用。judge_set_closure は要素**例**のみ surface に置き、誤解を招く特定の演算例を避けた。
7. **★保留セルは realize の軸をずらすと入る**（l11 knowledge）。「素数かどうかの判別」は素数プールが小さく
   dup 不可だったが、desc の「**意味**」を term_recall（素数/合成数/素因数の意味想起）に振り直すと surface
   （例の数）で分散でき dup 0.05 に収まった。**desc の別の側面を拾えば保留を解除できる**ことがある。

（C1 までの学び＝13f/13e/13d/13c §2 も有効。narration 数字禁止・式答え display 全体一致漏洩検査 等。）

---

## 3. 残タスク（優先順）

### 3.1 C1 の残（7/69）— ここからは bespoke（汎用ハブに乗らない）
knowledge の cheap 横展開は**出尽くした**。残りは計算・図・解釈で、いずれも新規ソルバの設計が要る:
- **l11 素因数分解 calc Lv1/Lv2**（答え `2³×3²` 形＝`sympy.factorint`＋累乗表示 bespoke）。
  表示は `_fmt_monomial_display` の `**n→上付き` 流用が効くはず。★G-Q5t 注意：答えは複数トークンの積
  （素因数の数字を含む）＝定数答えの whitelist 判定が単一数と異なる。gate 実装を要確認してから構成すること。
  Lv2 は素数判定・大きめの数。
- **l60 科学的記数法 calc Lv1/Lv2**（`a×10ⁿ`・四捨五入・有効数字＝bespoke）。指数表示・小数の丸め。
- **l60 knowledge Lv2**（有効数字がどこまでか判別・誤差の適用＝verify）。
- **l12 knowledge Lv2**（与式が表す数量の意味を解釈＝場面生成＋選択。scenario を作り「3x+5y は何を表すか」を
  ChoiceAnswer 化。答えに数字が入りやすい〈`3個`等〉ので言い換えと G-Q5t に注意）。
- **l2 graph_table Lv1**（数直線上の点↔数。graph_table form＝**図（visual）を伴う**初の C1 セル。
  既存の graph_table 系〔g2 の linear〕の visual_plan 機構を要調査。他 knowledge/calc と機構が違う）。

### 3.2 その先
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
word_problem 系（利用）は **C14（T3・M1 本体）**。幾何 C7-C10・proof C15 は独立ファイルで大量に増える群
＝サブエージェント並列が本領を発揮する候補。

---

## 4. アーキ／プレイブック／資産
`docs/HANDOFF_engine_2026-07-12.md` §2/§3/§5 と 13e/13d §4 が正。本書 §2 は追記。

**本セッションで拡張／新設した資産（すべて letter_expr パック内）**:
- solver **`math.term_recall_definition(concept, domain)`**（用語/記号想起）。`_TERM_MAPS` に domain 追加で増える。
  domain: letter/equality/equation/number/**inequality/number_set/power/laws/prime_concepts/approximation**。
  step narration は `_TERM_RECALL_STEP_TEXT_BY_DOMAIN`（既定＝現行文・inequality のみ特化）。
- solver **`math.recall_rule_statement(topic, concept)`**（規則想起・**#61 新設**）。`_RULE_MAPS[topic][concept]=
  (正記述, [誤記述])`。topic: transposition/addition_sign/subtraction/term_in_sum/speed_relation/
  letter_meaning/product_sign/reciprocal/notation_product_rule/notation_quotient_rule。
- solver **`math.classify_number_sign(value)`**（正負分類・#65）／**`math.represent_opposite_quantity(
  positive_label, asked_label, magnitude)`**（反対量の符号・#65・`_OPPOSITE_PAIRS`）／
  **`math.judge_set_closure(number_set, operation)`**（四則の閉性・#66・`_SET_CLOSURE` 真偽表）。
- recipe: `math.term_recall`（`_draw_term_statement` に domain 別 surface）／`math.recall_rule`
  （`_draw_rule_statement` に topic 別 surface）／`math.classify_number_sign`／
  `math.represent_opposite_quantity`／`math.judge_set_closure`。checker（double_solve）各1件。
- template: `lf_inequality_symbol_v1`／`lf_rule_recall_v1`／`lf_classify_sign_v1`／
  `lf_opposite_quantity_v1`／`lf_set_closure_v1`（+ 既存 `lf_term_recall_v1` を多 domain で流用）。
- **既存**：arithmetic.py／polynomial.py（`_fmt_monomial_display` 等）／equation.py／linear.py。

**検証スニペット**: `scratchpad/check_cell.py`（120seed フル gate ＋ dup@100・ChoiceAnswer 対応）。
`PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>`。git 未追跡（消えたら 13f §4）。

**DoD の順序（本セッションで確立した速い流れ）**:
1. solver+recipe+checker+template+concepts.yaml+yaml+test を書く →
2. `pytest -k` で construct/property（数秒）→ 3. `check_cell.py`（gate 0・dup≤0.20）→
4. `spec_cli check`（lint0/smoke0）→ 5. `spec_cli approve` →
6. golden slice（新規＋回帰）→ 7. mypy strict＋ruff（engine のみ・tests 既存債務は無視）→
8. `engine.eval` exit0＋goal_progress → 9. commit（家系ごと or 同機構グループごと）。
最後にフルスイート1回（編集完了後・単独）。

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P2 継続）を続けてください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む**: ①`docs/goal_spec_2026-07-12.md` ②`docs/HANDOFF_engine_2026-07-13g.md`（**最新・本書**）
> ③`docs/HANDOFF_engine_2026-07-13f.md`（knowledge の surface 定石）④`docs/HANDOFF_engine_2026-07-12.md`
> （プレイブック）。
>
> **再開の最初**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -6                                        # 最新 0f00e28(#69)
> git status --porcelain                                      # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress             # 128/630・C1 62/69・exit0
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
> ```
>
> フルスイートが緑なら **C1 の残（§3.1・7セル）** を進める。**ここからは bespoke**（term_recall/recall_rule に
> 乗らない）：優先＝①l11 素因数分解 calc（factorint＋累乗表示・**答えが積で複数数字→G-Q5t 判定を先に確認**）
> ②l60 科学的記数法 calc（a×10ⁿ・丸め）③l60 knowledge Lv2・l12 knowledge Lv2（解釈）④l2 graph_table
> （**図を伴う**初の C1・visual_plan 機構調査）。C1 完成後 C3 g3 数と式（展開/因数分解/平方根/二次）。
>
> **鉄則**: ①level 間は steps op 列を変える ②narration に数字を書かない ③式答えは display 全体一致漏洩検査＋
> 非退化ガード ④定数答えは given whitelist だが**答え=given値は構成でガード**（反対量は必ず負向きを問う＝§2-#6）
> ⑤**knowledge の答えテキストに ASCII 数字を入れない**（`2数`→`両方の数`等・§2-#2）⑥**dup は自由度の個数**＝
> concept 少なら**独立2値/別種の自由度**を surface に（§2-#3）⑦**form=knowledge は asked=choice のみ**（§2-#4）
> ⑧mode/signature/concept は solver・recipe・yaml・concepts.yaml で整合 ⑨**新 family/level は test_recipes.py の
> `_*_CELLS` リストに必ず追加** ⑩**フルスイート背景中に新 yaml を書くと lint 偽陽性**＝編集完了後に単独で回す（§2-#5）
> ⑪1家系（or 同機構グループ）ずつ DoD 緑でコミット。

---

*引き継ぎ書（2026-07-13g・P2 の C1 knowledge 総ざらいセッション）。次アカウントは §5 の指示文から入ること。*
