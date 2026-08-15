# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13b・P1 の C2 完成セッション）

本書は **ゴール仕様 v1.0 の Phase P1 で C2（g2 数と式）を T1 で 100%（32/32）に到達させたセッション**を
別アカウントへ引き継ぐためのもの。前回引き継ぎ書 `docs/HANDOFF_engine_2026-07-13.md`（#26〜#38・
C2 17/32）の続きにあたる。**本書＝最新**。ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
   全実装は「どの C グループ・どの Phase か」を宣言して行う。進捗実測は `python -m engine.tools.goal_progress`。
2. **本書（最新）**：§1 現状・§2 新しい学び・§3 残タスク・§5 別アカウント指示文。
3. `docs/HANDOFF_engine_2026-07-13.md`（1つ前・#26〜#38・§2 学び）／`docs/HANDOFF_engine_2026-07-12.md`
   （§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）。プレイブックと落とし穴はこの2冊が正。
4. P1 残の設計 `docs/design_C2_polynomial_2026-07-13.md`（C2 計算群の設計。**本セッションで実装完了**）。

---

## 0.5 ★環境の高速化（再開の最初に実施＝大幅な時短・別アカウントで導入する）

現状フルスイートは **シングルコアで約45分**（テスト 11,422 件中 96%＝10,986 件が recipe の property。
マシンは 8 コアだが 1 コアしか使っていない）。**これが本プロジェクト最大の時間ボトルネック**。
`pytest-xdist` を導入して全コア並列化する（前セッションはこれを未導入のまま直列で回していたため遅かった）:

```bash
.venv/bin/pip install pytest-xdist       # dev依存の追加（venv のみ）
# 以後フルスイートは -n auto で（約45分 → 見込み 8〜10 分）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q
```
- テストは決定論・seed 独立なので並列で安全な見込み。**初回だけ `-n auto` と直列（`-n0`）の
  結果を突き合わせ、passed 数一致・失敗ゼロを確認**してから常用する。
- xdist 導入後は「pytest は1本ずつ（CPU飽和回避）」の制約は不要（1 プロセスが全コアを使う）。

**あわせて効く時短運用**:
- フルスイートは **セッション終了時に1回**だけ（各セルは eval＋property＋spec check で個別担保）。
- 各セルの check（generate／120seed 拒否／dup 100seed）は **1スクリプト（bootstrap 1回）に統合**して回す
  （bootstrap 起動の重複を避ける。ただし1コマンド2分制限に注意し、重いものは run_in_background）。
- 開発中の property は seed を絞り（例 `range(30)`）、最終スイートのみ 100〜200 で回す。

---

## 1. 現状サマリ（2026-07-13b・本セッション終了時）

**進捗: capabilities 66/630（10.5%）**（`python -m engine.tools.goal_progress` 実測）。
- **C2 g2 数と式（式の計算・連立）: 32/32（100%）** ← 本セッション +10セル。**C2 は T1 完成**。
- **C5 g2 一次関数: 34/36（94%）** ← 変化なし。残2は保留（§3.2・word_problem/幾何＝M1）。
- 他グループ（C1/C3/C4/C6〜C16）は未着手（0）。学年別: g2 66/197・g1/g3/exam は 0。

**本セッションでコミットした7コミット（#39〜#45）**。すべて **1セル（or 連結ファミリ）ごとに DoD 緑**
（generate 目視／spec lint0 smoke0／120-seed 拒否0／dup_rate ≤0.20 @100seed 実測／level_sep 相異／
golden 承認／property 100+seed／eval exit0／mypy strict／ruff clean）を満たしてコミット。

| # | セル | 内容 | 新規部品・要点 |
|---|---|---|---|
| #39 | g2_l4 calc Lv1/2/3 | 単項式乗除（×÷・累乗・分数係数） | solver `compute_monomial_expression`・factor-first で整数係数保証・上付き汎用フォーマッタ `_fmt_monomial_display` |
| #40 | g2_l6 calc Lv2/3 | 通分（分数式の加減） | solver `combine_fractional_expressions`（together＋分子expand・分母は最小公倍数） |
| #41 | g2_l1 calc Lv1 | 次数（単項式・多項式） | solver `degree_of_expression`（sympy.degree）・**単一小問に集約**・asked_vocab に `degree` 追加 |
| #42 | g2_l9 calc Lv1/2/3 | 等式変形（指定文字で解く） | solver `solve_for_variable`（sympy.solve）・given `target_variable`／asked `expression` 追加 |
| #43 | g2_l7 calc Lv1 | 数の性質の式（連続数の和） | solver `express_number_property`・given `expressions` 追加・文字×性質×個数で dup 分散 |
| #44 | g2_l8 calc Lv1 | 2けたの自然数（10a+b） | solver `combine_digit_number`・文字ペア×和差で dup 分散 |
| #45 | g2_l1/l2/l10 knowledge | 用語想起・判別（C2 完成） | ChoiceAnswer 4セル（#16 knowledge capability 再利用）・G-Q5t 素通り |

### 再開時の最初のコマンド（実状態の確認）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework
git log --oneline -8                 # 最新 8de78e8（#45 C2 knowledge 完成）
git status --porcelain               # 空（clean）
.venv/bin/python -m engine.tools.goal_progress          # 66/630・C2 32/32
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0（約1分）
# ★まず §0.5 の pytest-xdist を導入 → 再開直後にフルスイートを1本走らせ緑を最終確認（-n auto で約8〜10分）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q
```
> ⚠️ **本セッションの #39〜#45 は各セルを個別 DoD 緑（property 100+seed／eval 一式 exit0／golden／
> mypy strict／ruff engine/ clean／spec check／dup_rate 100seed／120seed 拒否0／level_sep）で検証してコミット
> 済みだが、最終フルスイート（全 property を一括・約45分）は別アカウント引き継ぎのため中断（未走）**。
> セッション開始時（#39 の前）にフルスイートを1本走らせ 9942 passed / exit0 を確認済み。**再開時の最初に
> §0.5 の `pytest-xdist` を導入してからフルスイートを1本走らせ緑を最終確認すること**
> （`-n auto` で約8〜10分）。前回引き継ぎ（#20〜#25）と同じ「FS中断→再開時確認」運用。

---

## 2. このセッションで得た「新しい学び」

1. **★G-Q5t は「答えが自由変数を含む symbolic」なら display 全体一致のみ検査**（`quality_gates.py:363-367`）。
   多項式・単項式・分数式・「y = …」形など、答えに文字が残るセルは**個々の係数は検査されず**、答えの
   display 文字列が丸ごと本文/ヒントに現れる場合だけ漏洩判定。→ 与式と構造の異なる答え（積・通分結果・
   解の式）は相対的に安全。ただし答えが与式の一部と一致する退化（#26 の l3 で実測した bare 単項）は要注意。
   本セッションの計算セル（l4/l6/l9/l7/l8）はすべてこの「free-symbol は display のみ」に該当し漏洩ゼロ。
2. **★次数（l1）の G-Q5t は given whitelist が救う**：答えの次数（小整数）が given の係数と一致しても、
   `_build_given_whitelist` が given の数値を両符号で許可するため素通り。given に無ければ本文に現れず漏洩なし。
   **上付き指数（³ 等・U+00B3）は `extract_numbers` に拾われない**ので、次数が given の指数由来でも漏洩しない。
3. **★分数フォーマッタの曖昧さ回避**：分数係数の単項式は「-3/2 xy」のように**係数と文字の間にスペース**を
   入れる（source example に一致・"-3/2xy" は 5/(2xy) と誤読されうる）。除数・負・分数の因子はかっこで囲む。
4. **★level_sep は mode ごとの steps op 列で作る**（数値域だけの差は不可）。多レベル計算セル（l4/l6/l9）は
   recipe が level ごとに mode を持ち、solver がその mode で op 列を変える。単一レベルのセル（l1/l7/l8・
   knowledge Lv 単独）は signature 相異のみで通る（fp 衝突は起きない）。
5. **★dup_rate が構造的に低いセル（数の性質・用語想起）**は「答えに無関係な surface」を広くとる（§7.7 F-3）。
   l7＝変数文字(18)×性質(5)×個数(2〜5)で 0.10／l8＝文字ペア(順序つき18)×演算(和/差)で 0.08／knowledge の
   用語想起＝concept×**具体例（surface）** で分散（l1kn Lv1 0.08・l10kn Lv1 0.0）。dup_key は params ベース
   なので、**具体例の文字列を params に残せば答えが少数でも dup は下がる**。必ず eval/100seed で実測。
6. **★knowledge（ChoiceAnswer）はテキスト答え＝G-Q5t 完全素通り**（`_answer_values(choice)=[correct]`→数字なし）。
   選択肢文言は本文に固定併記してよい。用語想起は「concept で correct が変わる」型（#21）にして answer に
   変化を持たせ、具体例で dup を分散する。判別（単項式/多項式・同類項か）は式で答えが変わる verify 型（強い）。
7. **★spec 追加は実行中フルスイートに干渉する**（`test_eval_suite` が `capability_cells` を走査）が、
   **solver/recipe/checker/template の Python 追記は非干渉**（`test_recipes` は関数を名指しでテストする）。
   → 長いフルスイート実行中は Python を先行実装し、spec/concept は完走後に追加すると待ち時間を活かせる。
   recipe ロジックは **scratchpad の一時 spec を `load_family_dir` で読んで直接叩けば**、実 families を汚さず
   （＝実行中フルスイート非干渉で）検証できる（本セッションで knowledge 4セルをこの方法で先行検証）。
8. **★フルスイートは1本ずつ**（約45分・CPU飽和回避）。各セル検証（spec check＋120seed＋property＋eval）は
   複数を1コマンドに詰めると2分制限を超えてバックグラウンド化される。**spec check は1 family ずつ**が安全。

---

## 3. 残タスク（優先順）

### 3.1 P1 の T1 到達状況（本セッションで C2 完成）
- **C2: 32/32（100%・T1 完成）**。**C5: 34/36**（残2＝§3.2 の保留・T3/M1）。
  → **P1 の T1 実装可能ぶんは実質完了**（C5 の残2は word_problem/専用幾何設計で T1 では作らない）。

### 3.2 保留セル（T1 では忠実に量産しない・M1 で再検討）
- **g2_l30 find_value Lv3**（速さの変化・複数区間の交点）＝word_problem（piecewise 立式）。
- **g2_l29 graph_table Lv3**（動点面積の折れ線）＝faithful かつ dup 緑にする配置設計が別途必要。
  いずれも `source_desc` に「未実装・M1」と明記済み。M1 の word_problem 基盤と合わせて再検討。

### 3.3 次フェーズ P2（goal_spec §3.6・最安・最大volume）
**P2 = C1（g1 数と式・69セル）＋ C3（g3 数と式・68セル）＝ SymPy 直・visual 不要・160セル規模**。
- C1 g1 数と式: 正負の数・文字式・一次方程式。**本セッションの polynomial.py 資産（同類項・分配・等式変形・
  次数・用語 knowledge）と linear.py の一次方程式資産が大きく流用できる見込み**。g1 は次数が低く SymPy 直で最安。
- C3 g3 数と式: 多項式（展開・因数分解）・平方根・二次方程式。**展開/因数分解は sympy.expand/factor、平方根は
  sympy.sqrt/simplify、二次は sympy.solve** で solver を素直に書ける。C2 の calc パターン（answer/factor-first・
  mode で level_sep・分数/上付きフォーマッタ）をほぼそのまま横展開できる。
- 進め方: C1→C3 の順に、各 unit の `units.generated.yaml` の desc/example を正として転記し、C2 と同じ
  プレイブック（solver→recipe→checker→template→(frame)→concept→spec→DoD→property→commit）で1セルずつ。
  **frame 語彙が足りなければ `frames.py`＋`test_frames.py` を同時更新**（本セッションで degree/target_variable/
  expression/expressions を追加した実績あり）。

### 3.4 その先（P3 以降）
P3（関数）→ P4（幾何 visual 基盤＝1本で C7〜C10 の140セル解放）→ … → P7（T3 翻訳基盤＝word_problem/
proof 151セル・M1本体）。goal_spec §3.6 の Phase 順に従う。

---

## 4. アーキ／プレイブック／落とし穴

**`docs/HANDOFF_engine_2026-07-12.md` の §2/§3/§5**（アーキ・横展開プレイブック11手順・既知の落とし穴9件）と
**`docs/HANDOFF_engine_2026-07-13.md` §2**（G-Q5t 表示文字列検査・上付き指数・graph.py 土台・dup 定石・
level_sep）が正。本書 §2 はそれへの追記。新セルはプレイブックどおり。

**検証コマンド（要点）**:
```bash
find engine -name __pycache__ -type d -exec rm -rf {} +
.venv/bin/python -m engine.tools.generate <unit> <form> <lv> --seed 4         # 目視
.venv/bin/python -m engine.tools.spec_cli check math.<unit>.<form>            # lint0/smoke0（1familyずつ）
# 120seed 拒否0（G-Q5t 広域）＋ dup_rate 100seed 実測（eval方式・spec_cli の dup は当てにならない）
.venv/bin/python -m engine.tools.spec_cli approve math.<unit>.<form>          # golden 固定
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100                     # 自動被覆・exit0
.venv/bin/python -m pytest engine_tests/unit/test_recipes.py -k <name> ...    # property（frame追加時は test_frames を別途単独実行）
.venv/bin/python -m mypy --strict engine/packs/ engine/core/ engine/eval/
.venv/bin/ruff check engine/    # engine/ のみ clean を保つ（engine_tests は既存 nit 数件あり・対象外）
```

**C2 の実装物（P2 で流用する資産）**:
- `engine/packs/math/{solvers,recipes,checkers,templates}/polynomial.py`：式の計算 solver 群
  （simplify/add_sub/distribute/monomial/fraction/degree/solve_for_variable/number_property/digit_number）
  ＋ knowledge（poly_term/classify/like_terms/system_term）。フォーマッタ `_fmt_poly_display`/
  `_fmt_monomial_display`（上付き汎用）/`_fmt_monomial_factor`/`_fmt_monomial_chain`/`_fmt_fraction_display`。
- frame: calculation に degree/target_variable/expression/expressions を追加済み（`frames.py`・`test_frames.py`）。

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P1→P2）を継続してください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む（順に）**:
> 1. `docs/goal_spec_2026-07-12.md`（ゴール仕様＝完成の定義。全実装は「どのCグループ・どのPhaseか」を宣言）
> 2. `docs/HANDOFF_engine_2026-07-13b.md`（**最新**・本書。§1 現状・§2 新しい学び・§3 残タスク）
> 3. `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）と
>    `docs/HANDOFF_engine_2026-07-13.md`（§2 学び）
>
> **★再開の最初にやること**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -9
> git status --porcelain                                        # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress               # 66/630・C2 32/32
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100     # 一式OK・exit0
> # ★まず高速化: pytest-xdist を導入（フルスイート 45分 → 約8〜10分）
> .venv/bin/pip install pytest-xdist
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -n auto -q   # フルスイート緑確認(★#39〜#45はFS未走なので必ず実行)
> ```
>
> フルスイートが緑なら、**P2（C1 g1数と式 → C3 g3数と式）**へ。C2 で作った polynomial.py の calc/knowledge
> 資産と linear.py の一次方程式資産を流用し、C2 と同じプレイブックで1セルずつ DoD 緑にしてコミット。
> C1 が最安（g1・次数低・SymPy 直）、C3 は expand/factor/sqrt/solve で素直に書ける。
>
> **鉄則**: ①level 間は steps の op 列を変える（数値域だけの偽レベルは level_sep が落とす）②narration/ヒントに
> 数字を書かない ③**G-Q5t は答えが自由変数を含む symbolic なら display 全体一致のみ検査**（bare 単項への退化に
> 注意）／定数答えは given whitelist と助数詞除外で守る ④dup_rate は eval/100seed 実測で ≤0.20（答えに効かない
> surface param＝変数文字・具体例・演算種別を広くとる）⑤frame 語彙を足したら `test_frames.py` 同時更新（-k で
> deselect される罠に注意し別途単独実行）⑥★フルスイートは pytest-xdist で -n auto 並列（約8〜10分・§0.5）＝「1本ずつ」制約は xdist 導入後は不要。spec check は1 family ずつ（2分制限）。フルスイートはセッション終了時に1回・開発中の property は seed を絞る
> ⑦サブエージェント並行（worktree）は不安定なので当面直列。長いフルスイート中は Python を先行実装し spec は
> 完走後（spec は test_eval_suite に干渉／Python 追記は test_recipes 非干渉）⑧1セルずつ DoD 緑にしてコミット。
>
> **保留**: g2_l30 fv Lv3・g2_l29 graph Lv3 は word_problem/幾何寄りで T1 では忠実に量産できない（§3.2）。
> M1 の word_problem 基盤と合わせて再検討。無理に量産しない。

---

*引き継ぎ書（2026-07-13b・P1 の C2 完成セッション）。次アカウントは本書 §5 の指示文から入ること。*
