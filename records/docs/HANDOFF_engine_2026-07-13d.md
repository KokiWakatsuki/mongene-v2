# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13d・P2 の C1 文字式＋一次方程式セッション）

本書は **Phase P2 を継続し、C1（g1 数と式）の「文字式の計算」と「一次方程式の解法」の calculation
セルを新パック `letter_expr` / `equation` で網羅させたセッション**の引き継ぎ。前回
`docs/HANDOFF_engine_2026-07-13c.md`（C1 正負の数 calc・82/630）の続き。**本書＝最新**。
ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§4 資産・§5 指示文。
3. `docs/HANDOFF_engine_2026-07-13c.md`（C1 正負の数 calc・arithmetic.py 資産／§2 定石）／
   `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。

---

## 0.5 環境（pytest-xdist 導入済み・実行の勘所）
- **★本セッションで property テストを 60 倍高速化**（コミット末尾）。`test_recipes.py` の `_make_ctx` が
  テスト1件ごとに 58 family の YAML と curriculum を再パースしていた（1回≈313ms・property 1200件で約376秒＝97%が
  再パース浪費・family 増で悪化）。`lru_cache` で1回に集約。実測 **`-k letter` 128s→2.1s／test_recipes.py 全体
  単一コア 13613 passed in 35s**。→ **セル毎の property DoD は `-k "letter"` 等で数秒**（背景実行不要）。
  **フルスイート全体も -n auto で 25:54 → 3:04（8.4倍・14127 passed 同数・緑維持）**。
- フルスイートは **`-n auto` で約3分**（lru_cache 修正後・本マシン実測。修正前は約20〜26分）:
  ```bash
  .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
  ```
  ⚠️ `| tail` の exit code は tail のもの。**pytest 自身の exit code は pipestatus で見る**（fish は `$pipestatus[2]`、bash/zsh は `${PIPESTATUS[1]}`）。
- **★セル毎の property DoD / golden slice / check_cell / spec check は Bash の2分制限を超えるので背景実行が安定**
  （`run_in_background: true` + 完了通知を待つ、または Monitor で `grep -q passed` を待つ）。フォアグラウンドで回すと
  収集12000件のため2分制限で `Exit code 143` になる（テスト自体は無事）。
- **★property の `-k` は当該関数名で絞るが、部分一致で他セルも巻き込む**（例 `-k "equation"` は g2_l26
  solve_equation_for_y も拾い 1208 件、`-k "substitution"` は g2 連立代入法も拾い 806 件）。全部緑なら問題ないが
  収集は毎回全12000件で重い（2〜6分）。新セルだけ厳密に見たいなら固有の関数名断片で絞る（`-k "letter"`＝404件）。

---

## 1. 現状サマリ（2026-07-13d・本セッション終了時）

**進捗: capabilities 96/630（15.2%）**（`python -m engine.tools.goal_progress` 実測・exit 0）。最新コミット `da6671e`（#55）。
- **C1 g1 数と式: 30/69** ← 本セッション +14セル（文字式 calc 6 + 一次方程式 calc 8）。
- C2 32/32（完成）・C5 34/36（変化なし）。他グループ未着手。
- ★**property テストを lru_cache で 60 倍高速化**（`f38aece`・§0.5）＝毎セル検証が数分→数秒・FS 26分→3分。

**本セッションの3コミット（#52〜#54）**。すべて1セル群ごとに DoD 緑
（generate 目視／spec lint0 smoke0／120-seed 拒否0／dup_rate ≤0.20 @100seed 実測／level_sep 相異(fps)／
golden 承認（golden slice 緑）／property 全緑／eval exit0／mypy strict／ruff clean）でコミット。

| # | セル | mode / signature | 要点 |
|---|---|---|---|
| #52 | g1_l17 一次式加減 Lv1/2・g1_l18 一次式乗除 Lv1/2 | combine_linear / expand_paren_linear / distribute_linear / distribute_divide_linear | **letter_expr パック新設**。単一文字の一次式。答えは式（free_symbol）。漏洩ガード付き |
| #53 | g1_l16 代入と式の値 Lv1/2 | substitute_positive / substitute_signed | letter_expr に**代入 solver 追加**（sympy.subs）。答えは数値（定数） |
| #54 | g1_l21 等式の性質 Lv1/2・g1_l22 移項 Lv1/2 | equality_add / equality_multi / transpose_constant / transpose_both | **equation パック新設**（sympy.solve）。答えは解 x=定数。answer-first で逆算 |
| #55 | g1_l23 かっこ展開 Lv2・g1_l25 代金・g1_l26 過不足・g1_l27 速さ | expand_parens / word_price_equation / shortage_equation / speed_fraction_equation | equation.py に **mode 追加のみ**（capability 償却）。l26 は transpose_both を signature 別で流用＝コード変更なし |

### 再開時の最初のコマンド
```bash
cd /Users/koki/workspace/mongene-v2
git log --oneline -6                                        # 最新 da6671e(#55)
git status --porcelain                                      # 空(clean)
.venv/bin/python -m engine.tools.goal_progress             # 96/630・C1 30/69・exit0
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0（約1分）
# フルスイート（pipestatus で exit code 確認）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
```
> 本セッション終了時のフルスイートは緑（**14127 passed / EXIT=0**）を確認済み（lru_cache 修正後は約3分・§0.5）。
> **本変更は共有 RNG ヘルパ（arithmetic の `_DECIMALS`・`draw` 経路・共有フォーマッタ）を一切変更していない**
> （新モジュール追加と polynomial 整形ヘルパの参照のみ）ため、既存 golden の陳腐化はゼロ（§13c-2-#7 の教訓）。

---

## 2. このセッションで得た「新しい学び」

1. **★単一文字の一次式は g2 の二変数多項式と構造が違う**。g2 の polynomial recipe（combine_like_terms 等は
   x,y／a,b の二変数を answer-first で構成）を**直接は流用できない**（一次式は ax+b の単一文字＋定数）。
   → **arithmetic.py と同型の「1 solver（mode→op列）＋ 1 recipe dispatch」を新設**するのが最も faithful かつ clean。
   ただし polynomial の**整形ヘルパは流用可**：`_fmt_poly_display`（solver）／`_fmt_poly_x_terms`・`_sympy_poly_x`・
   `_fmt_expr_from_terms`・`_sympy_str_from_terms`・`_domain_candidates`（recipe）を import して使った。
2. **★式答え（free_symbol 含む SymbolicAnswer）の G-Q5t は display 全体一致のみ検査**（§13c-2-#1）だが、
   **答えが bare monomial に退化すると与式の部分文字列と衝突して漏洩誤検出になる**。実バグ：l18 Lv2 で
   答え `12x`（定数項0）が被除数 `(12x - 9)` の "12x" と一致（seed13）。また combine で答え `3x` が与式 `-3x` と一致しうる。
   → recipe に**「答えの表示が与式に部分文字列として現れない」有界リトライガード**を入れる（`_leaks`＝空白除去で
   保守的に substring 照合）。加えて **x 係数を構成で必ず非零に**して定数退化を防ぐ（free_symbols を loop で確認）。
3. **★定数答えセル（代入 l16・方程式 l21/l22）は arithmetic 系と同じく G-Q5t 安全**。答えは数値で、given の
   数値（式・方程式の係数・代入値）が**すべて whitelist（両符号）**される。本文の数値は全て given 由来なので、
   答え（given に無い新しい数）は本文に現れず漏洩しない。`contains_number` は**トークン単位**照合なので、
   多桁答え（例 243）が単桁トークンの並びと偶然一致することもない。narration に数字を書かないことだけ守る。
4. **★一次方程式は answer-first（解 x0 を先に選び係数を逆算）**。`solve_linear_equation` は sympy.solve で
   1変数方程式を厳密に解く（double-solve）。両辺に文字がある型は **d=(a-c)·x0+b** で右辺定数を逆算（a≠c）。
   **RHS=0 退化（"x - 4 = 0" のような解きかけに見える形）は c≠0 を構成保証して回避**（b≠-x0 等）。
5. **★2自由度しかない mode は dup が上がる**。`x+b=c`（x0 と b の2自由度）は域 [-9,9] だと dup 0.16。
   → **域を [-12,12] に広げて 0.10 に低下**。低 variety セルは域拡大が第一手（累乗/絶対値は kind 重み付けだった＝§13c-2-#2）。
6. **★背景実行＋通知待ちが安定**（§0.5）。spec check / check_cell / property / golden slice はどれも2分を超えるので
   `run_in_background` にして完了通知（または Monitor の `grep -q "ALL_OK|passed"`）を待つ。フォアグラウンドは 143 で切れる。

（C1 正負の数までの学び＝HANDOFF 13c §2 / 13b / 13 も引き続き有効。定数答え G-Q5t 安全・narration 数字禁止等。）

---

## 3. 残タスク（優先順）

### 3.1 C1 の残（39/69）
- **一次方程式 calc の残（equation.py に mode 追加で入る・sympy.solve は分数/かっこ/比例式も解ける）**:
  - **l23 Lv3**（分母を払う `(x-1)/2 - (2x-3)/5 = 1`＝分数係数の式。answer-first で分母倍数を選び整数解を保証。
    `clear_denominators_simple`（x/p+x/q=r）とは別に、`(x+p)/d1 ±(m·x+s)/d2 = c` 型の新 mode が要る。
    整数中間値を出すため p≡-x0 mod d1・s≡-m·x0 mod d2 で構成）。op 列例＝`[clear_denominators, expand_and_transpose, solve]`。
  - **l24 Lv1**（比例式 `3:4=9:x`＝たすきがけ `ad=bc`。構成: a,b,t で c=a·t, x0=b·t）・**Lv2**（`(x+1):6=5:3`）。
    ★**表示（比例式）と solver 用の式（クロス乗算した線形式）が別**なので、params に equation_str（線形）と
    display（比例式）を両方持たせ、`_build_eq` を使う（term-list の `_build` は使わない）。新 given=proportion 想定
    だが calc frame の given_vocab に proportion が無ければ frames.py + test_frames.py 追加（§5-⑦）。
- **文字式 calc の残**: 記法 **l13/l14**（積・商の表し方＝`3×a×a→3a²`・`a÷b→a/b` の簡約表示 solver。answer は式）。
  ※ l13/l14 は「きまりに従って簡潔に表す」＝簡約表示。knowledge 寄り（用語想起）の level もある。
- **knowledge 多数**（#16/#45 の **ChoiceAnswer パターン**を流用。polynomial.py の `poly_term_recall` /
  `classify_monomial_or_polynomial` / `judge_like_terms` が雛形）:
  - **l17 knowledge**（項・係数・次数・同類項の用語判別）・**l21 knowledge**（方程式・解の用語＋Lv2 解の判別 verify
    ＝x=3 は解か代入判定）・**l22 knowledge**（移項とは何か）・**l2 knowledge**（絶対値の用語＋大小判別 verify）・
    **l19 knowledge**（等式・左辺右辺の用語）・**l20 knowledge**（不等号 以上/以下/未満/超 の意味）・**l1/l3〜l15 各種**。
- **l11 素因数分解**（答え `2³×3²` 形＝因数分解solver+累乗表示・bespoke）・**l60 科学的記数法**
  （`a×10ⁿ`・四捨五入・有効数字＝新solver・bespoke）。

### 3.2 その先
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
C2 の calc パターン（factor-first・mode で level_sep・分数/上付きフォーマッタ）と本セッションの letter_expr /
equation を横展開。word_problem 系（l19/l24/l25/l26/l27 の word_problem）は **C14（T3・M1 本体）**。

---

## 4. アーキ／プレイブック／資産
`docs/HANDOFF_engine_2026-07-12.md` §2/§3/§5（アーキ・11手順・落とし穴9件）と 13c §4 が正。本書 §2 は追記。

**本セッションで新設した資産（C1 で流用）**:
- **`letter_expr` パック**（`engine/packs/math/{solvers,recipes,checkers,templates}/letter_expr.py`・各 `__init__` に登録済み）:
  - solver `math.evaluate_letter_expression(expr_str, mode)`：一次式を sympy.expand で整理（答えは式）。
    mode＝combine_linear / expand_paren_linear / distribute_linear / distribute_divide_linear。
  - solver `math.evaluate_substitution(expr_str, subs_str, mode)`：代入して式の値（定数）。subs_str="x=-3" 形。
    mode＝substitute_positive / substitute_signed。
  - recipe `math.compute_letter_expression`（漏洩ガード付き）／`math.compute_substitution`。
  - template `lf_calc_evaluate_v1`（arithmetic と共有・l17/l18）／`lf_substitute_value_v1`（l16）。
- **`equation` パック**（同 4 種）:
  - solver `math.solve_linear_equation(equation_str, mode)`：sympy.solve で1変数方程式。答えは解 x=定数（display "x = ..."）。
    mode＝equality_add / equality_multi / transpose_constant / transpose_both（**今後 l23〜l27 の mode をここに足す**）。
  - recipe `math.compute_linear_equation`（answer-first）。
  - template `lf_solve_equation_property_v1`（等式の性質）／`lf_solve_equation_transpose_v1`（移項）／`lf_solve_equation_v1`（一般）。
- **既存資産**：arithmetic.py（正負の数 calc・`fmt_number`）／polynomial.py（式の計算・整形ヘルパ群）／linear.py（一次関数）。

**検証スニペット**: `scratchpad/check_cell.py`＝1セルの 120-seed 拒否（フル gate）+ `cell_dup_rate`@100 を一発測定。
`PYTHONPATH=. .venv/bin/python <path>/check_cell.py <unit> <form> <lv,lv>`。
（別セッションの scratchpad から本セッション scratchpad にコピー済み。無ければ 13c §4 / 12 §5-#8 のスニペットで再作成。）

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P2 継続）を続けてください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む**: ①`docs/goal_spec_2026-07-12.md` ②`docs/HANDOFF_engine_2026-07-13d.md`（**最新・本書**）
> ③`docs/HANDOFF_engine_2026-07-13c.md`（C1 正負の数 calc・arithmetic 資産）
> ④`docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件）。
>
> **再開の最初**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -6                                        # 最新 da6671e(#55)
> git status --porcelain                                      # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress             # 96/630・C1 30/69・exit0
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
> ```
>
> フルスイートが緑なら **C1 の残（§3.1）** を同じプレイブックで1セルずつ DoD 緑にしてコミット。優先＝
> ①一次方程式の残 **l23 Lv3（分母払い）・l24（比例式）** calc（`equation.py` に mode 追加。l24 は表示≠solver式に注意）
> ②文字式 記法 l13/l14 calc ③knowledge 多数（polynomial の poly_term_recall / classify / judge_like_terms を
> 雛形に ChoiceAnswer 流用）④l11 素因数分解・l60 科学的記数法（bespoke）。C1 完成後 C3 g3 数と式（sympy.expand/factor/sqrt/solve）。
>
> **鉄則**: ①level 間は steps の op 列を変える（数値域だけの偽レベルは level_sep が落とす）②narration/ヒントに
> 数字を書かない（定数答えの唯一の漏洩経路）③式答えは「答え表示が与式に部分文字列で現れない」有界リトライで
> 漏洩を防ぐ＋x係数非零を構成保証（§2-#2）④定数答えは given whitelist で安全（§2-#3）⑤dup は check_cell の
> 100seed 実測 ≤0.20（低 variety セルは域拡大＝§2-#5）⑥mode 名は solver と recipe/yaml で一致・signature は
> 大域一意 ⑦frame 語彙を足したら test_frames.py 同時更新 ⑧**property は lru_cache 化で数秒**（`-k "<関数名断片>"` で
> フォアグラウンド可・§0.5）。check_cell（120seed）/golden slice/spec check は数十秒〜2分なので**背景実行＋通知待ち**が安定
> ⑨1セル群ずつ DoD 緑にしてコミット。

---

*引き継ぎ書（2026-07-13d・P2 の C1 文字式＋一次方程式セッション）。次アカウントは §5 の指示文から入ること。*
