# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13e・P2 の C1 一次方程式 分母払い＋比例式セッション）

本書は **Phase P2 を継続し、C1（g1 数と式・一次方程式の残）の「分母を払う（l23 Lv3）」と「比例式
（l24 Lv1/Lv2）」の calculation セルを既存パック `equation` に mode 追加で網羅させたセッション**の
引き継ぎ。前回 `docs/HANDOFF_engine_2026-07-13d.md`（C1 文字式＋一次方程式・96/630）の続き。**本書＝最新**。
ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§4 資産・§5 指示文。
3. `docs/HANDOFF_engine_2026-07-13d.md`（C1 文字式 letter_expr・一次方程式 equation パック／§0.5 lru_cache 高速化）／
   `docs/HANDOFF_engine_2026-07-13c.md`（C1 正負の数 calc・arithmetic.py 資産）／
   `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。

---

## 0.5 実行の勘所（13d §0.5 が正・要点のみ再掲）
- **property は lru_cache 化で数秒**（`f38aece`）。セル毎の property DoD は
  `pytest engine_tests/unit/test_recipes.py -k "<関数名/セル名断片>"` でフォアグラウンド可（本セッションは
  `-k "equation or proportion or clear_denom or l23 or l24"` で 1612 passed / 5.8s）。
- **フルスイートは `-n auto` で約3分**（本セッション実測 14552 passed / 3:18）:
  ```bash
  .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
  ```
  ⚠️ pytest 自身の exit code は **pipestatus** で見る（fish は `$pipestatus[2]`）。
- **spec check（lint+smoke20+dup100）は `generate()` を都度呼び curriculum を毎回ロードするので遅い**
  （1 family 1〜2分）。**背景実行＋通知待ち**が安定（フォアグラウンドは2分制限で 143）。check_cell（120gate+dup100）は
  共有 env なので数秒〜数十秒。
- **★check_cell.py は scratchpad に無ければ再作成**（本セッションで再作成した版が
  `scratchpad/check_cell.py`。フル gate 拒否＋dup を一発測定。無ければ本書 §4 のスニペットで再作成）。

---

## 1. 現状サマリ（2026-07-13e・本セッション終了時）

**進捗: capabilities 99/630（15.7%）**（`python -m engine.tools.goal_progress` 実測・exit 0）。最新コミット `b2f8fb8`（#56）。
- **C1 g1 数と式: 33/69** ← 本セッション +3セル（一次方程式 l23 Lv3 + l24 Lv1/Lv2）。
- C2 32/32（完成）・C5 34/36（変化なし）。他グループ未着手。

**本セッションの1コミット（#56 = `b2f8fb8`）**。1セル群を DoD 全緑でコミット
（generate 目視／spec lint0 smoke0／120-seed 拒否0／dup ≤0.20@100 実測／level_sep 相異(fp)／
golden 承認（golden slice 30緑）／property 1612緑／eval exit0／mypy strict／ruff clean／フルスイート 14552 passed）。

| # | セル | mode / signature | 要点 |
|---|---|---|---|
| #56 | g1_l23 分母払い Lv3 | clear_denominators_two | (x+p)/d1 ±(m·x+s)/d2 = c。**equation.py に mode 追加のみ**（capability 償却）。分子定数を「割り切れる小候補」から引き小さく保つ。op列[clear_denominators, expand_and_transpose, solve] |
| #56 | g1_l24 比例式 Lv1/Lv2 | cross_multiply / cross_multiply_expand | **新 family g1_l24.calculation**。表示（比例式 a:b=c:x）≠solver式（クロス乗算 a·x=b·c）。新 template lf_solve_proportion_v1。op列相異＝level_sep |

### 再開時の最初のコマンド
```bash
cd /Users/koki/workspace/mongene-v2
git log --oneline -6                                        # 最新 b2f8fb8(#56)
git status --porcelain                                      # 空(clean)。scratchpad/ は未追跡で無視
.venv/bin/python -m engine.tools.goal_progress             # 99/630・C1 33/69・exit0
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0（約1分）
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
```
> 本セッション終了時のフルスイートは緑（**14552 passed / EXIT=0**）を確認済み（約3分）。
> **本変更は共有 RNG ヘルパ（arithmetic・polynomial 整形）を一切変更していない**（equation.py への mode 追加と
> 新 family/template のみ）ため、既存 golden の陳腐化はゼロ。実測でも **l23 Lv2 golden は byte 不変**
> （approve 再生成後 git diff なし＝新 mode 分岐は既存 mode より後で early-return するので RNG 消費が不変）。

---

## 2. このセッションで得た「新しい学び」

1. **★比例式は「表示」と「solver 用の式」が構造的に別物**（13d §3.1 の予告どおり）。表示は比例式
   `a : b = c : x`（`given["equation"]` に格納・calc frame の given_vocab の "equation" キーで OK・frame 変更不要）。
   solver へは**クロス乗算した線形式**（Lv1 `a·x = b·c` / Lv2 `d·(x+p) = b·c`）を渡す。recipe で eq_str（線形）と
   eq_disp（比例式）を別々に組み `_build_eq(eq_str, eq_disp, mode, ctx)` を使う（term-list の `_build` は使わない）。
   solver（`solve_linear_equation`）は eq_str の線形式を素直に sympy.solve するだけで、mode は steps の op 列
   （たすきがけの narration）だけを差し替える。
2. **★answer-first の「逆算で分子定数が肥大化する」罠と回避**。素朴に「解 x0 を先に決め、分子を
   `d·kp - x0` で逆算」すると分子定数が |24| 等に膨れて教材として不自然（初版で実際に (x+63):20 が出た）。
   → **分子定数を先に小さな候補域から引き、割り切れ条件（`(x0+v)%d==0`）を満たすものだけ許す**方が faithful。
   l24 Lv2 は「N=x0+p（小さな p）と左辺分母 b の**既約比** c:d = reduce(N:b)」で右比を後から決めると
   例（(x+1):6=5:3）を自然に再現でき、分子も小さく保てる。**answer-first でも「答え側」でなく「見た目の小ささ」を
   固定して逆算する方が良い場面がある**。
3. **★定数答えでも「答え x0 が given 数値と一致」は gate をすり抜ける実害**。given 数値は両符号 whitelist
   されるため（13d §2-#3）、**x0 が表示中の整数（比の各項・分母・分子定数）と偶然一致しても G-Q5t は素通り**する。
   これは gate 上は緑だが教材的には答えバレ。→ **recipe 構成側で `abs(x0) in shown_integers` を弾く有界リトライ**を
   入れる（whitelist に頼らず自衛）。定数答えセルを増やすときの新しい定石。
4. **★spec check は遅い・check_cell は速い（env 共有の差）**。`spec_cli check` は `generate()` を seed ごとに
   呼び毎回 curriculum/families をロードするため 1 family で1〜2分（背景実行推奨）。一方 check_cell は
   `make_env()` で1回だけ bootstrap した共有 env を使い回すので 120gate+dup100 が数十秒。**日常の DoD 確認は
   check_cell、最終署名としての lint/smoke は spec check** と使い分ける。
5. **★新 mode は既存 mode 分岐の「後ろ」に足すと既存 golden が byte 不変**。recipe の `if mode == ...: return`
   連鎖で、既存 mode は自分の分岐で early-return するため、後ろに新分岐を足しても RNG 消費順が変わらない。
   approve 再生成 → git diff が既存 level に出ない＝chronology 破壊なしを実測で確認できる（13c §2-#7 の一般化）。

（C1 までの学び＝HANDOFF 13d §2 / 13c §2 / 13b / 13 も引き続き有効。narration 数字禁止・定数答え whitelist・
式答えは display 全体一致で漏洩検査＋bare monomial 退化ガード 等。）

---

## 3. 残タスク（優先順）

### 3.1 C1 の残（36/69）
- **文字式 calc の残**: 記法 **l13/l14**（積・商の表し方＝`3×a×a→3a²`・`a÷b→a/b` の簡約表示 solver。answer は式）。
  ※「きまりに従って簡潔に表す」＝簡約表示。式答えなので display 全体一致の漏洩検査＋非退化ガード（letter_expr 系の定石）。
- **knowledge 多数**（#16/#45 の **ChoiceAnswer パターン**を流用。polynomial.py の `poly_term_recall` /
  `classify_monomial_or_polynomial` / `judge_like_terms` が雛形）:
  - **l17 knowledge**（項・係数・次数・同類項の用語判別）・**l21 knowledge**（方程式・解の用語＋Lv2 解の判別 verify）・
    **l22 knowledge**（移項とは何か）・**l2 knowledge**（絶対値の用語＋大小判別 verify）・**l19 knowledge**（等式・左辺右辺）・
    **l20 knowledge**（不等号 以上/以下/未満/超）・**l1/l3〜l15 各種**。答えテキストは G-Q5t 素通り＝本文に選択肢並記 OK。
- **l11 素因数分解**（答え `2³×3²` 形＝因数分解 solver+累乗表示・bespoke）・**l60 科学的記数法**
  （`a×10ⁿ`・四捨五入・有効数字＝新 solver・bespoke）。

### 3.2 その先
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
word_problem 系（l19/l24/l25/l26/l27 の word_problem）は **C14（T3・M1 本体）**。

---

## 4. アーキ／プレイブック／資産
`docs/HANDOFF_engine_2026-07-12.md` §2/§3/§5（アーキ・11手順・落とし穴9件）と 13d §4 / 13c §4 が正。本書 §2 は追記。

**本セッションで拡張した資産（C1 で流用）**:
- **`equation` パック**（`math.solve_linear_equation` / `math.compute_linear_equation`）に mode 追加:
  - `clear_denominators_two`（l23 Lv3・分母払い）／`cross_multiply`（l24 Lv1・比例式たすきがけ）／
    `cross_multiply_expand`（l24 Lv2・文字項を含む比例式）。**mode 名は solver `_EQUATION_STEPS` と recipe の
    `if mode==...` と yaml の `mode:` で完全一致・signature は大域一意**。
  - recipe の比例式 mode は **eq_str（クロス乗算した線形式）と eq_disp（比例式表示）を別々に組み `_build_eq` を使う**。
  - 新 template `lf_solve_proportion_v1`（"次の比例式を解け。\n{{ given.equation }}"）。
  - concepts 3件追加（`equation.solve_by_clear_denominators` / `solve_proportion` / `solve_proportion_linear`）。
- **既存資産**：arithmetic.py（正負の数 calc・`fmt_number`）／polynomial.py（式の計算・整形ヘルパ
  `_fmt_poly_x_terms`・`_sympy_poly_x`・`_domain_candidates` 等）／letter_expr.py（文字式）／linear.py（一次関数）。

**検証スニペット**: `scratchpad/check_cell.py`（本セッションで再作成）＝1セルの 120-seed フル gate 拒否＋
`cell_dup_rate`@100 を一発測定。`PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>`。
（scratchpad は git 未追跡なので次セッションで消えていたら本書 §4 / 13d §4 のスニペットで再作成。）

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P2 継続）を続けてください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む**: ①`docs/goal_spec_2026-07-12.md` ②`docs/HANDOFF_engine_2026-07-13e.md`（**最新・本書**）
> ③`docs/HANDOFF_engine_2026-07-13d.md`（C1 文字式 letter_expr・一次方程式 equation パック）
> ④`docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件）。
>
> **再開の最初**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -6                                        # 最新 b2f8fb8(#56)
> git status --porcelain                                      # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress             # 99/630・C1 33/69・exit0
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
> ```
>
> フルスイートが緑なら **C1 の残（§3.1）** を同じプレイブックで1セルずつ DoD 緑にしてコミット。優先＝
> ①文字式 記法 l13/l14 calc（簡約表示・式答え）②knowledge 多数（polynomial の poly_term_recall / classify /
> judge_like_terms を雛形に ChoiceAnswer 流用）③l11 素因数分解・l60 科学的記数法（bespoke）。C1 完成後 C3 g3 数と式。
>
> **鉄則**: ①level 間は steps の op 列を変える ②narration に数字を書かない ③式答えは display 全体一致漏洩検査＋
> 非退化ガード（13d §2-#2）④定数答えは given whitelist で安全だが **答え x0 が given 数値と一致するのは gate 素通りの
> 実害なので recipe 側で弾く**（本書 §2-#3）⑤dup は check_cell の 100seed 実測 ≤0.20 ⑥mode 名は solver/recipe/yaml で
> 完全一致・signature は大域一意 ⑦frame 語彙を足したら test_frames.py 同時更新（比例式は "equation" キー流用で不要だった）
> ⑧**property は lru_cache 化で数秒**（`-k` でフォアグラウンド可）。**spec check は遅い（背景実行）・check_cell は速い**
> ⑨1セル群ずつ DoD 緑にしてコミット。

---

*引き継ぎ書（2026-07-13e・P2 の C1 一次方程式 分母払い＋比例式セッション）。次アカウントは §5 の指示文から入ること。*
