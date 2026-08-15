# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13c・P2 の C1 正負の数 calc セッション）

本書は **Phase P2 に着手し、C1（g1 数と式）の「正の数・負の数」の calculation セルを新パック
`arithmetic.py` で網羅（16/69）させたセッション**の引き継ぎ。前回 `docs/HANDOFF_engine_2026-07-13b.md`
（C2 完成・66/630）の続き。**本書＝最新**。ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§5 指示文。
3. `docs/HANDOFF_engine_2026-07-13b.md`（C2完成・§2 G-Q5t/dup 定石）／`docs/HANDOFF_engine_2026-07-12.md`
   （§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。プレイブックはこの2冊が正。

---

## 0.5 環境（pytest-xdist 導入済み）
`pytest-xdist` は導入済み。フルスイートは **`-n auto` で約20分**（本マシン実測・6.4コア相当）:
```bash
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q
```
> 直列(`-n0`)との passed 数突き合わせ（初回パリティ確認）は未実施＝**低リスクとして次セッションに委ねた**
> （テストは決定論・seed独立の純関数で xdist の分散に無関係。個別に全て緑を確認済み）。気になれば1回だけ直列実行。

---

## 1. 現状サマリ（2026-07-13c・本セッション終了時）

**進捗: capabilities 82/630（13.0%）**（`python -m engine.tools.goal_progress` 実測）。最新コミット `f68911a`
（実装6コミット #46〜#51 + golden 修正 `f68911a` + 本書 `c6b9b6c`）。
- **C1 g1 数と式: 16/69** ← 本セッション +16セル（正の数・負の数の calculation を網羅）。
- C2 32/32（完成）・C5 34/36（変化なし）。他グループ未着手。

**本セッションの6コミット（#46〜#51）**。すべて1セル（or 同一unitの複数level）ごとに DoD 緑
（generate 目視／spec lint0 smoke0／120-seed 拒否0／dup_rate ≤0.20 @100seed 実測／level_sep 相異／
golden 承認／property 100+seed／eval exit0／mypy strict／ruff clean）でコミット。

| # | セル | mode | 要点 |
|---|---|---|---|
| #46 | g1_l3 加法 Lv1/2 | addition_pair / addition_terms | 汎用solver新設・2数(符号決定)/3項(項の和・分数小数) |
| #47 | g1_l4減法・l6乗法・l8除法 Lv1/2 | subtraction/multiplication/divide _pair/_terms/_chain | divide_pairはanswer-firstで割り切れる整数 |
| #48 | g1_l5 加減混合 Lv1/2 | add_sub_terms / add_sub_terms_rational | 各項に+/-演算子・+と-を必ず両方含める |
| #49 | g1_l7 累乗 Lv1/2 | power_single / power_sign_contrast | -a^n と(-a)^nの区別・底を int/frac/dec で dup分散 |
| #50 | g1_l9 四則混合 Lv2/3 | four_operations / distributive_trick | 骨格A-(B)²×C+D÷E / 分配法則の工夫 |
| #51 | g1_l2 絶対値・大小 Lv1/2 | absolute_value / order_numbers | absはevaluate solver再利用・orderは専用solver(Tuple答え) |

### 再開時の最初のコマンド
```bash
cd /Users/koki/workspace/mongene-v2
git log --oneline -8            # 最新 f68911a（golden修正）
git status --porcelain          # 空（clean）
.venv/bin/python -m engine.tools.goal_progress          # 82/630・C1 16/69
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0（約1分）
# フルスイート（pytest の exit code を必ず pipestatus で確認・§2-#8）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=${pipestatus[1]}"
```
> ⚠️ 本セッション終了時のフルスイートで **golden 陳腐化 11 件を検出→再 approve で修正済み（`f68911a`）**。
> 修正後 `test_golden_slice` は 246 passed。**修正後のフルスイート緑を再確認するのが再開時の最初のタスク**
> （§2-#7 の教訓：共有 RNG ヘルパ変更後は golden slice を回す）。

---

## 2. このセッションで得た「新しい学び」（arithmetic 系の勘所）

1. **★定数答えの G-Q5t は原理上安全**。問題文の数値はすべて given（式）由来で `_build_given_whitelist` に
   両符号で載る。答えは問題文に書かれない（hints は各 step の **narration のみ**＝最後の step を除く・
   `result_display` は非表示・`t1_template.py:174`）。→ **narration に数字を書かなければ漏洩しない**。
   実際 seed43 で narration「2数の符号…」の '2' が答え 2 と衝突（"数" は `_COUNTER_EXPR_RE` 非該当で
   除去されない）→「たがいの数」に修正で解消。narration の数字は徹底排除する。
2. **★累乗・絶対値は組合せが少なく dup が跳ねる**（power 単独で 0.76）。対策＝底/値を **{int, frac, dec}
   の複数 kind** にし、**base_kinds リスト内で反復して重み付け**（例 `[int, frac, frac, frac, dec]`）+ 範囲拡大。
   小プール（int≈14・dec≈28）が均等比重だと衝突源になる（`draw(list)` は kind を一様選択＝プール сие無視）。
   → 高variety の frac に重みを寄せると 0.11 まで下がる。dup は必ず `eval/cell_dup_rate` の 100seed で実測。
3. **★小数入力は evaluate solver の `fmt_number` で分数化**する（|1.9| → 19/10）。絶対値は int+frac に限定して
   回避。並べ替え（order）は **元の提示トークンを保持**（solver が token を sort して token を表示）＝小数OK。
4. **★mode 名は solver `_MODE_STEPS` と recipe/yaml で完全一致**させる（divide_pair vs division_pair の
   ズレで実行時 KeyError）。**signature は大域一意**にする（G-FP が signature→fp をプロセス内で大域キャッシュ
   `quality_gates.py:149`）＝各セルで一意な **mode 名を signature に流用**した。
5. **checker は mode 分岐可**（`compute_signed_arithmetic.double_solve` は order_numbers のみ別 solver を呼ぶ）。
6. **★pytest 実行の絞り込み**: `-k "signed"` は全 property（≈1600件）にマッチし約4分。**構文/構成テストだけ**は
   `-k "特定の関数名断片"`（例 `-k "power_single"`）で 1.4 秒。**セル毎の property DoD** は `-k "g1_lN"`
   で当該 200 件（2level×100seed）だけ走らせる（全収集は12000件で重いが実行は200件）。
7. **★共有 RNG ヘルパの変更は既承認 golden を陳腐化させる**（本セッションで実バグ）。#49 で共有の `_DECIMALS`
   に小数候補を追加したところ、**先に承認済みだった dec 種を使うセル（l3/l4/l5/l6 の Lv2＝分数小数混在）の
   抽選列が変わり golden が不一致**になった（フルスイートの `test_golden_slice` で 11 件 failed・fix `f68911a`）。
   セル自体は正常（dup/拒否/property 全緑）でスナップショットのみ古い→再 approve で解消。
   **教訓: 乱数に効く共有ヘルパ（`_DECIMALS`・`draw` 経路・フォーマッタ）を変えたら、影響する全既承認 family を
   再 approve するか `pytest engine_tests/golden/test_golden_slice.py`（約75秒）を回してから次へ進む**。
8. **★`pytest ... | tail` の exit code は tail のもの**（pytest の失敗が隠れる）。フルスイートは
   `2>&1 | tail -3; echo "EXIT=${pipestatus[1]}"`（fish は `$pipestatus[2]`）で **pytest 自身の exit code** を見る。

（C2 までの学び＝HANDOFF 13b §2 / 13 §2 も引き続き有効。上付き指数は extract_numbers 非抽出で漏洩なし等。）

---

## 3. 残タスク（優先順）

### 3.1 C1 の残（53/69）
- **正の数・負の数 calc の残2**: **l11 素因数分解**（答え `2³×3²` 形＝因数分解solver+累乗表示・新template）・
  **l60 科学的記数法**（`a×10ⁿ`・四捨五入・有効数字＝新solver）。各 bespoke だが arithmetic.py に mode 追加で入る。
- **文字式 l12〜l20 calc**（代入l16・記法l13/l14・一次式加減l17・一次式乗除l18）＝**polynomial.py の
  combine_like_terms/add_or_subtract/distribute_or_divide 資産を新family+conceptで流用**（R6: recipe の
  provides_concepts に新concept追加が必要）。代入(l16)は新solver（sympy.subs）。
- **一次方程式 l21〜l27 calc**（移項・かっこ小数分数・比例式）＝**新solver（sympy.solve で1変数方程式）**。
  linear.py は一次「関数」で方程式求解は無いので新規。answer は解 x（定数）。
- **knowledge 多数**（l1/l3/l4/l5/l6/l7/l8/l9/l10/l11/l12/l13/l14/l15/l17/l19/l20/l60）＝用語想起/判別。
  **#16/#45 の ChoiceAnswer パターン**（concept で答えが変わる用語想起・式で変わる判別）を流用。
  「説明せよ」型の source example も **単一選択に realize**（design note を source_desc に明記＝C2 と同方針）。

### 3.2 その先
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
C2 の calc パターン（factor-first・mode で level_sep・分数/上付きフォーマッタ）を横展開。

---

## 4. アーキ／プレイブック／落とし穴
`docs/HANDOFF_engine_2026-07-12.md` §2/§3/§5（アーキ・11手順・落とし穴9件）と 13/13b §2 が正。本書 §2 は追記。

**arithmetic.py の実装物（C1 で流用する資産）**:
- `engine/packs/math/{solvers,recipes,checkers,templates}/arithmetic.py` を各 `__init__.py` に登録済み。
- solver `math.evaluate_numeric_expression(expr_str, mode)`：数値式を sympy で厳密評価。`_MODE_STEPS` に
  mode→op列（addition_pair/addition_terms/subtraction_*/add_sub_terms*/multiplication_*/power_*/divide_*/
  four_operations/distributive_trick/absolute_value）。`fmt_number`（整数/既約分数）。
- solver `math.order_signed_numbers(numbers_str, ascending)`：複数数を整列（元トークン保持・答え=Tuple）。
- recipe `math.compute_signed_arithmetic`：全 mode を1関数で dispatch。`_draw_operand`（int/frac/dec）・
  `_fmt_signed`/`_paren_if_neg`/`_fmt_power_base`/`_superscript`/`_DECIMALS`。order は `_build_order_numbers`。
- template：`lf_calc_evaluate_v1`（"次の計算をせよ"）を全 calc で共有＋abs/order/distributive 専用。

**検証スニペット（本セッションで整備）**: `scratchpad/check_cell.py`＝1セルの 120-seed 拒否（フル gate）+
`cell_dup_rate`@100 を一発測定。`PYTHONPATH=. .venv/bin/python <path>/check_cell.py <unit> <form> <lv,lv>`。
プレイブック検証コマンドは 13b §4 と同じ（generate/spec check 1familyずつ/approve/eval/mypy/ruff）。

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P2 継続）を続けてください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む**: ①`docs/goal_spec_2026-07-12.md` ②`docs/HANDOFF_engine_2026-07-13c.md`（**最新・本書**）
> ③`docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件）。
>
> **再開の最初**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -6                                         # 最新 7ba90c2(#51)
> git status --porcelain                                       # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress              # 82/630・C1 16/69
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100    # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q  # FS緑確認(約20分)
> ```
>
> フルスイートが緑なら **C1 の残（§3.1）** を同じプレイブックで1セルずつ DoD 緑にしてコミット。優先＝
> ①文字式 l12-20（polynomial資産流用・代入は新solver）②一次方程式 l21-27（sympy.solve 新solver）
> ③knowledge 多数（#16/#45 ChoiceAnswer流用）④l11素因数分解・l60科学的記数法（bespoke）。C1完成後 C3。
>
> **鉄則**: ①level間は steps の op列を変える ②narration/ヒントに数字を書かない（定数答えの唯一の漏洩経路）
> ③dup は `scratchpad/check_cell.py` の 100seed 実測 ≤0.20（累乗/絶対値等の低variety セルは底/値を int/frac/dec
> の複数kindにしリスト内反復で frac に重み付け）④mode名は solver と recipe/yaml で一致・signature は大域一意
> ⑤frame語彙を足したら `test_frames.py` 同時更新 ⑥FS は `-n auto`（セッション終了時1回）・spec check は
> 1familyずつ（2分制限）・セル毎 property は `-k "g1_lN"` で200件のみ ⑦1セルずつ DoD 緑にしてコミット。

---

*引き継ぎ書（2026-07-13c・P2 の C1 正負の数 calc セッション）。次アカウントは §5 の指示文から入ること。*
