# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13f・P2 の C1 記法＋knowledge セッション）

本書は **Phase P2 を継続し、C1（g1 数と式）の残を「文字式の記法（l13/l14）」と「数と式の
knowledge（用語想起 l17/l19/l21・解の判別 l21Lv2）」まで進めたセッション**の引き継ぎ。
前回 `docs/HANDOFF_engine_2026-07-13e.md`（一次方程式 分母払い＋比例式・99/630）の続き。**本書＝最新**。
ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§4 資産・§5 指示文。
3. `docs/HANDOFF_engine_2026-07-13e.md`（一次方程式 分母払い/比例式・§2 比例式の表示≠solver式）／
   `docs/HANDOFF_engine_2026-07-13d.md`（letter_expr/equation パック・lru_cache 高速化）／
   `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。

---

## 0.5 実行の勘所（13d/13e §0.5 が正・要点のみ）
- **property は lru_cache で数秒**（`pytest engine_tests/unit/test_recipes.py -k "<断片>"` フォアグラウンド可）。
- **フルスイートは `-n auto` で約3.5分**（本セッション 15686 passed / 3:34）。exit code は **pipestatus** で見る。
- **spec check は遅い（1 family 1〜2分・背景実行）／check_cell は速い（共有 env・数十秒）**。日常 DoD は check_cell、
  最終署名は spec check。★check_cell.py は ChoiceAnswer 対応済（`getattr(ans,"display",None) or getattr(ans,"correct",ans)`）。

---

## 1. 現状サマリ（2026-07-13f・本セッション終了時）

**進捗: capabilities 109/630（17.3%）**（`python -m engine.tools.goal_progress`・exit 0）。最新コミット `3fefbab`（#59）。
- **C1 g1 数と式: 43/69** ← 本セッション +13セル（#56 分母払い/比例式3 + #57 記法4 + #58 knowledge4 + #59 l2 knowledge2）。
- C2 32/32（完成）・C5 34/36。他グループ未着手。

**本セッションの4コミット（#56〜#59）**。各1セル群を DoD 全緑でコミット。

| # | セル | solver / signature | 要点 |
|---|---|---|---|
| #56 | g1_l23 Lv3 分母払い・g1_l24 比例式 Lv1/2 | clear_denominators_two / cross_multiply(_expand) | equation.py に mode 追加。比例式は表示≠solver式（13e §2） |
| #57 | g1_l13 乗法 Lv1/2・g1_l14 除法 Lv1/2 | **math.simplify_notation** | letter_expr に新 solver。与式(× ÷ 明示)を sympy 正準化し `_fmt_monomial_display` で教材表記。式答え |
| #58 | g1_l17/l19/l21 用語想起・g1_l21Lv2 解の判別 | **math.term_recall_definition** / **math.verify_equation_solution** | ChoiceAnswer。汎用 term_recall を domain で切替し3セル共有。verify は代入判定 |
| #59 | g1_l2 絶対値用語 Lv1・大小判別 Lv2 | term_recall(domain=number) / **math.compare_signed_numbers** | 用語想起は term_recall に domain=number 追加。Lv2 は2数の大小 verify（答え=大きいほうの数） |

### 再開時の最初のコマンド
```bash
cd /Users/koki/workspace/mongene-v2
git log --oneline -6                                        # 最新 3fefbab(#59)
git status --porcelain                                      # 空(clean)。scratchpad/ は未追跡で無視
.venv/bin/python -m engine.tools.goal_progress             # 109/630・C1 43/69・exit0
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
```
> 本セッション終了時のフルスイートは緑（**15894 passed / EXIT=0**）を確認済み（約3.5分）。
> 既存 golden の陳腐化ゼロ（共有 RNG ヘルパ未変更・新 solver/family 追加のみ）。

---

## 2. このセッションで得た「新しい学び」

1. **★記法（積・商の簡約表示）は「与式を simplify して正準表示」型**。与式（`y×x×(-4)` を `*`/`/` にした
   未簡約文字列）を `sympy.sympify` すると正準単項式が得られ、`_fmt_monomial_display`
   （solvers/polynomial.py・数を前・アルファベット順・`**n`→上付き・`*`除去）で教材表記になる。答えは式。
   除法は分母を**文字**にすれば分数退化（`6x÷2→3x`）を防げる。level_sep は op 列（Lv1=1手 vs Lv2=2手）。
   **単一小文字は sympy で全て安全に Symbol**（`e`→E 等の罠は無し・確認済）。
2. **★ChoiceAnswer 用語想起 recipe は params に surface（statement/example）を含めないと dup が壊滅**。dup_key は
   `signature + 正規化 params`。当初 params を `{concept, domain}` だけにしたら 2〜4 concept しか無く dup 0.96。
   → **具体例（statement 文字列）を params に含める**と dup_key が分散し 0.09/0.01/0.0 に（poly_term_recall の
   `params={concept, example}` と同じ定石＝13b §2-#3 の再確認）。**新 knowledge セルは必ず surface を params に入れる**。
3. **★汎用 term-recall ソルバ 1 本で複数ユニットを償却**。`term_recall_definition(concept, domain)` に
   domain 別の用語辞書（letter/equality/equation）を持たせ、distractors は同 domain の他用語。l17/l19/l21Lv1 を
   1 solver + 1 recipe で作れた（family/concept/domain param だけで増やせる）。knowledge の横展開が安い。
4. **★前セッションの property カバレッジ漏れを検出・補完**。#56 の l23Lv3/l24 は `test_recipes.py` の
   ハードコード family リスト（`_EQUATION_WORD_CELLS`）に**未追加**だった（property は既存セル名一致で緑に見えたが
   新セルは seed100 property 未被覆）。#57 で construct テスト＋リスト追加で補完。**新 family/level を作ったら
   `test_recipes.py` の該当 `_*_CELLS` リストに必ず追加**（capabilities に出ても property は自動では増えない）。
5. **★verify 型（解の判別）は answer-first で真偽ビットを制御**。真の解 x0 から方程式 a·x+b=c を組み、
   is_solution=偽なら候補を x0±delta（delta≠0）にずらす。judge_like_terms(#45)/verify_system_solution(#18) と同思想。
6. **★ruff は tests に既存 E702 債務あり（348-951 行の `a=..;b=..` 形）が、engine/ には無い**。新規追加分だけ
   clean にすればよい（既存債務の修正はスコープ外＝churn 回避）。mypy strict は engine 全 solver/recipe で緑。

（C1 までの学び＝13e/13d/13c §2 も有効。narration 数字禁止・定数答え whitelist・式答え display 全体一致漏洩検査・
答え x0 が given 数値と一致は gate 素通りの実害→構成でガード 等。）

---

## 3. 残タスク（優先順）

### 3.1 C1 の残（26/69）
- **knowledge の残**（#58/#59 の term_recall / verify を横展開・**surface を params に必ず入れる**＝§2-#2）:
  - **l22 knowledge**（移項とは・なぜ符号が変わるか＝説明選択。単一概念なので選択肢設計に一工夫要）・
    **l20 knowledge**（不等号 以上/以下/未満/超 の意味＝phrase→記号 mapping・term_recall domain 追加で入る）・
    **l1 knowledge**（正負・符号・0 の用語）・**l3/l4/l5 knowledge**（加法規則/減法規則/項）・
    **l10 knowledge**（自然数・整数の集合）・**l11 knowledge**（素数/合成数の判別）・**l12 knowledge**（文字式の意味）・
    **l15 knowledge**（速さ=距離/時間）。term_recall_definition の `_TERM_MAPS` に domain を足すか verify を新設。
- **l11 素因数分解 calc**（答え `2³×3²` 形＝因数分解 solver+累乗表示・bespoke）・**l60 科学的記数法 calc**
  （`a×10ⁿ`・四捨五入・有効数字＝新 solver・bespoke）。
  - ★**l11 knowledge（素数/合成数の判別）は保留**：答えが素数/合成数/どちらでもないの3値で、素数プールが小さく
    （≤100 で25個）「基礎らしい小さい数」だと dup≤0.20 を満たせない（#59 で検討・見送り）。素因数分解 calc と
    セットで「大きめの数」を扱うか、term-recall（素数/素因数/合成数の意味・例の数を surface に）に realize すれば入る。

### 3.2 その先
C1 完成 → **C3 g3 数と式**（展開/因数分解=sympy.expand/factor・平方根=sqrt/simplify・二次=solve）。
word_problem 系（利用）は **C14（T3・M1 本体）**。

---

## 4. アーキ／プレイブック／資産
`docs/HANDOFF_engine_2026-07-12.md` §2/§3/§5 と 13e/13d §4 が正。本書 §2 は追記。

**本セッションで拡張した資産（letter_expr パック）**:
- solver **`math.simplify_notation(expr_str, mode)`**（l13/l14・記法の簡約表示・式答え）。
  mode＝product_basic/product_powers/quotient_basic/quotient_mixed。`_fmt_monomial_display` を import 流用。
- solver **`math.term_recall_definition(concept, domain)`**（用語想起・ChoiceAnswer）。`_TERM_MAPS` に domain 辞書。
- solver **`math.verify_equation_solution(equation_str, value)`**（解の判別・ChoiceAnswer verify）。
- recipe `compute_notation`（記法・撹拌は draw ベース `_shuffle_pairs`）／`term_recall`（**statement を params に含める**）／
  `verify_equation_solution`（answer-first で真偽ビット制御）。checker 3件・template 4件・concepts 6件追加。
- **既存**：arithmetic.py／polynomial.py（`_fmt_monomial_display`・`_fmt_monomial_factor`・`poly_term_definition` 雛形）／
  equation.py（一次方程式）／linear.py。

**検証スニペット**: `scratchpad/check_cell.py`（ChoiceAnswer 対応済）。`PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>`。
scratchpad は git 未追跡なので消えていたら本書 §4 / 13e §4 のスニペットで再作成。

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P2 継続）を続けてください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む**: ①`docs/goal_spec_2026-07-12.md` ②`docs/HANDOFF_engine_2026-07-13f.md`（**最新・本書**）
> ③`docs/HANDOFF_engine_2026-07-13e.md`（分母払い/比例式）④`docs/HANDOFF_engine_2026-07-12.md`（プレイブック）。
>
> **再開の最初**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -6                                        # 最新 3fefbab(#59)
> git status --porcelain                                      # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress             # 109/630・C1 43/69・exit0
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q 2>&1 | tail -3; echo "EXIT=$pipestatus[2]"
> ```
>
> フルスイートが緑なら **C1 の残（§3.1）** を同じプレイブックで1セルずつ DoD 緑にしてコミット。優先＝
> ①knowledge の残（l22/l2/l20/l1/l3-5/l10-12/l15＝term_recall_definition の `_TERM_MAPS` に domain 追加 or verify 新設・
> **surface を params に必ず入れて dup 分散**）②l11 素因数分解・l60 科学的記数法（bespoke）。C1 完成後 C3 g3 数と式。
>
> **鉄則**: ①level 間は steps op 列を変える ②narration に数字を書かない ③式答えは display 全体一致漏洩検査＋非退化ガード
> ④定数答えは given whitelist で安全だが答え=given値は gate 素通りの実害→構成でガード ⑤**knowledge の dup は surface を
> params に含めて分散**（含め忘れると dup 0.96＝§2-#2）⑥mode/signature/concept は solver・recipe・yaml・concepts.yaml で
> 整合 ⑦**新 family/level を作ったら test_recipes.py の `_*_CELLS` リストに必ず追加**（property は自動では増えない＝§2-#4）
> ⑧property は lru_cache で数秒（`-k` フォアグラウンド）・spec check は遅い（背景）・check_cell は速い ⑨1セル群ずつ DoD 緑でコミット。

---

*引き継ぎ書（2026-07-13f・P2 の C1 記法＋knowledge セッション）。次アカウントは §5 の指示文から入ること。*
