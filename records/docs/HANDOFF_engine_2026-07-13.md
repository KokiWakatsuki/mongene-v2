# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-13・P1 継続セッション）

本書は **ゴール仕様 v1.0 の Phase P1（C5 一次関数 → C2 数と式）を大きく前進させたセッション**を
別アカウントへ引き継ぐためのもの。前回引き継ぎ書 `docs/HANDOFF_engine_2026-07-12.md`（M0＋#1〜#25）の
続きにあたる。**本書＝最新**。ブランチ `engine-m0-rework`（master 未マージ）。venv `.venv/bin/python`。

---

## 0. まず読む（順に）
1. **ゴール仕様: `docs/goal_spec_2026-07-12.md`**（v1.0・完成=green 630/630・台帳 C1〜C16・Phase P1〜P8）。
   全実装は「どの C グループ・どの Phase か」を宣言して行う。進捗実測は `python -m engine.tools.goal_progress`。
2. 前回引き継ぎ書 `docs/HANDOFF_engine_2026-07-12.md`（§2 アーキ・§3 プレイブック11手順・§5 落とし穴・§7.7 knowledge）。
   **プレイブックと落とし穴は前回書が正**。本書はその差分（本セッションの前進・新しい学び）を足す。
3. P1 残セルの実装設計 `docs/design_C5_graph_2026-07-13.md` / `docs/design_C2_polynomial_2026-07-13.md`。
4. 本書（最新の進捗・新しい落とし穴・別アカウント指示）。

---

## 1. 現状サマリ（2026-07-13・本セッション終了時）

**進捗: capabilities 51/630（8.1%）**（`python -m engine.tools.goal_progress` 実測）。
- **C5 g2 一次関数: 34/36（94%）** ← 本セッション +9セル。残2は保留（§3）。
- **C2 g2 数と式（式の計算・連立）: 17/32（53%）** ← 本セッション +6セル（l16/l10/l3×2/l5×2）。
- 他グループ（C1/C3/C4/C6〜C16）は未着手（0）。

**本セッションでコミットした13セル（#26〜#36 ＋ l3/l5）**。すべて**1セル（or連立/連結する2セル）ごとに
DoD 緑（property 200seed／spec lint0 smoke0／120-200seed 拒否0／dup_rate≤0.20 @100seed／level_sep 相異／
golden 承認／eval exit0／mypy strict／ruff clean）**を満たしてコミット。**バッチのフルスイートを3回緑
確認済み**（最新 9118 passed／41分）。

| # | セル | 内容 | 償却・新規部品 |
|---|---|---|---|
| #26 | g2_l30 graph Lv2 | ダイヤ交点読み | intersection_of_two_lines 再利用（新solverゼロ） |
| #27 | g2_l26 graph Lv2 | 特殊直線 x=k/y=k（切片法） | graph.py に vline_x/hline_y 後方互換追加・新visual |
| #28 | g2_l28 graph Lv2 | 対応表からグラフをかく | draw_linear_features 再利用 |
| #29 | g2_l22 graph Lv3 | 分数傾き・格子点 | 新solver draw_linear_features_fraction |
| #30 | g2_l23 graph Lv2 | 端点開閉の線分 | 新solver draw_segment_features・新visual・**graph.py 土台refactor** |
| #31 | g2_l28 calc Lv1 | 分数係数の代入 | evaluate_linear_at_x 再利用 |
| #32 | g2_l21 knowledge Lv2 | 傾き/切片の符号で4分類判別 | 新solver classify_line_by_signs |
| #33 | g2_l30 fv Lv2 | ダイヤ交点を連立で求める | intersection recipe 完全再利用 |
| #34 | g2_l29 fv Lv3 | 面積の式から時刻を逆算 | 新solver solve_time_from_area |
| #35 | g2_l16 calc Lv1 | 連立（足して消去） | intersection_of_two_lines 再利用 |
| #36 | g2_l10 calc Lv1 | 代入して左辺の値 | 新solver evaluate_two_var_lhs・frame語彙 candidate 追加 |
| l3 | g2_l3 calc Lv1/Lv2 | 多項式の加減 | 新solver add_or_subtract_polynomials（polynomial.py） |
| l5 | g2_l5 calc Lv1/Lv2 | 分配・除法 | 新solver distribute_or_divide（polynomial.py） |

### 再開時の最初のコマンド（実状態の確認）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework
git log --oneline -5                 # 最新は l3/l5 のコミット
git status --porcelain               # 空（clean）
.venv/bin/python -m engine.tools.goal_progress          # 49/630・グループ別被覆
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit0（約1分）
# ★再開直後にフルスイートを1本走らせ緑を最終確認（約40分・他pytestと競合させない）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -q
```

---

## 2. このセッションで得た「新しい学び」（前回落とし穴への追記）

1. **★G-Q5t は答えの「表示文字列」も検査する**（数値トークンだけではない）。多項式セルで
   答えが bare な単項（例 `y`・`3x`）になると、それが与式中に部分文字列として現れて漏洩判定される
   （l3 seed78 で `解答の式 'y' が problem_text/hints に漏洩` を実測）。→ **答えが単項に退化しないよう
   構成で防ぐ**（l3 は「各変数の係数を相殺しない候補から引き、両変数を必ず残す」＝retry 不使用の候補制限）。
   `_draw_term_group`（polynomial l2）と同じ思想。
2. **★上付き指数は extract_numbers に拾われない**（`x³` の ³ は U+00B3 で数字トークンでない）。次数系
   （l1）を作るとき、答えの次数（小整数）が given の指数由来だと whitelist に入らないが、**本文にも
   plain digit として現れないため漏洩もしない**（両建て）。ただし係数と偶然一致する経路は要 100+seed 実測。
3. **★graph.py の土台 refactor（#30）**: `render_grid_svg` から `_grid_scaffold`（open+rect+grid+軸）と
   `_grid_ticks`（目盛）を抽出した。**120 golden がバイト不変**であることを確認済み。以後の作図系
   （線分・折れ線）はこの土台を共有して足す（`render_segment_solution_svg` が実例）。
4. **★dup_rate は「答えが符号/少数種で決まる」型で跳ねる**（#19 の再確認）。#32（4分類・符号のみ依存）は
   域 [-9,9] で 0.26 → **答えに無関係な係数域を [-40,40] に広げて 0.0**。#34（面積逆算）も 160通り→648通りで
   0.28→0.14。**「答えに効かない surface param は広くとる」が定石**。必ず eval/100seed で実測（spec_cli の
   dup_rate は常に0で当てにならない）。
5. **★sonnet サブエージェント並行（worktree）はこの環境で不安定**。試行で (a) worktree が古い merge-base を
   割り当て、(b) SendMessage 再開で isolation が外れメインツリーを編集する事故が起きた（git status で即検知・
   完全復旧済み）。**当面 C2 も親が直列で実装**。どうしても並行するなら**手動 `git worktree add` で正しい base を
   用意し cd 運用**する（isolation:worktree ＋ SendMessage 再開は使わない）。鉄則「サブagent報告は git 実体で検証」
   が今回も機能した。
6. **多レベル polynomial セルの level_sep**: recipe が level ごとに `steps_ops` を持ち **steps を自前で組む**
   （solver は答えの double-solve 用）。fp（op列）が相異すれば level_sep 通過。l2/l3/l5 が実例。
7. **G-Q1 は `sub_questions[0]` のみ double-solve 検査**（quality_gates.py:206）。→ **2小問に分けず単一小問に
   集約**する（#27 は「主直線＋特殊直線」を1つの GraphAnswer にまとめた・l1 も単一小問化を推奨）。

---

## 3. 残タスク（優先順）

### 3.1 C2 polynomial 群の残（最優先・純SymPy直・T1明快）
`docs/design_C2_polynomial_2026-07-13.md` を正として、`polynomial.py`（solvers/recipes/checkers/templates）に
追記する（linear.py は触らない）。実装順の残: **l4 → l6 → l1 → l9 → l7 → l8**。
- **l4 単項式乗除**（Lv1/2/3・**最難**）: ×/÷・累乗・分数係数。`_fmt_monomial_chain` 新フォーマッタ（÷/上付き）が要る。
- **l6 通分**（Lv2/3）: `together`+分子 expand。分数フォーマッタ新設。
- **l1 次数**（Lv1）: `Poly.total_degree`。次数域1-3。asked_vocab に `degree` 追加（frame+test_frames 同時更新）。
  **単一小問に集約**（monomial/polynomial を mode で切替）。上付き指数の扱いに注意（学び#2）。
- **l9 等式変形**（Lv1/2/3）: `sympy.solve(eq, target)` で一般化。given=equation+target_variable、
  asked に `expression`（解の式）追加。Lv 差＝移項のみ/係数で割る/積・分母の文字（op列を変える）。
- **l7 偶数奇数の式**（Lv1）: `expand`。dup_rate 高リスク（property_type 数種）→個数/演算を surface で広げる。
- **l8 十進 10a+b**（Lv1）: **dup_rate 構造的困難**（数値パラメータなし＝毎回同型）。文字ペア (a,b)/(m,n) を
  ランダムにして見かけ差を出すか、source_desc 明記＋preview 検収に委ねる。和のみ（source_desc 忠実）。
- frame 追加が要るセル（l1 degree・l9 target_variable/expression）は `frames.py`＋`test_frames.py` を**同時更新**。

### 3.2 保留セル（word_problem/幾何寄り・T1 では忠実に量産できない）
- **g2_l30 fv Lv3**（速さの変化・複数区間の交点）: 場面から piecewise を立式して交点を求める＝**word_problem**
  （C14/M1 の T3 翻訳基盤の領域）。g2_l30.find_value.yaml の source_desc に「未実装・M1」と明記済み。
- **g2_l29 graph Lv3**（動点面積の折れ線・最重量）: (a) 正方形＋三角形APD 等の配置から幾何計算する版＝変種が
  少なく dup_rate 不達、(b) 頂点を固定 param で与える版＝答え≈与件で核心技能（折れ線を導く）が消える。
  `render_polyline_svg`＋GraphAnswer（頂点特徴）は設計済みだが、**faithful かつ dup_rate 緑にする配置
  バリエーション設計が別途必要**。M1 の word_problem 基盤と合わせて再検討。
→ この2セルにより **C5 の T1-clean 到達は 34/36**。残2は本質的に T3（word_problem）または要専用設計。

### 3.3 P1 完了後（goal_spec §3.6 の Phase 順）
P2（C1 g1数と式・C3 g3数と式＝SymPy直・visual不要・最安160セル）→ P3（関数）→
P4（幾何 visual 基盤＝1本で C7〜C10 の140セルを解放）… → P7（T3翻訳基盤＝word_problem/proof 151セル・M1本体）。

---

## 4. アーキ／プレイブック／落とし穴

**前回引き継ぎ書 `docs/HANDOFF_engine_2026-07-12.md` の §2/§3/§5 が正**（アーキ要点・横展開プレイブック11手順・
既知の落とし穴9件）。本書 §2 はそれへの**追記**。新セルは前回 §3 の手順どおり
（solver→recipe→checker→template→(frame)→concept→spec→DoD→property→検証してコミット）。

**検証コマンド（前回 §4 と同じ）**:
```bash
find engine -name __pycache__ -type d -exec rm -rf {} +
.venv/bin/python -m engine.tools.generate <unit> <form> <lv> --seed 4     # 目視
.venv/bin/python -m engine.tools.spec_cli check math.<unit>.<form>         # lint0/smoke0
# 100-200seed 拒否0（G-Q5t 偽陽性の広域確認）＋ dup_rate 100seed 実測（前回 §5-#8 スニペット・eval方式）
.venv/bin/python -m engine.tools.spec_cli approve math.<unit>.<form>       # golden 固定
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100                  # 自動被覆・exit0
.venv/bin/python -m pytest engine_tests/unit/test_recipes.py -k <name> ... # property（-k で test_frames が
                                                                            #   deselect される罠に注意＝別途単独実行）
.venv/bin/python -m mypy --strict engine/packs/ engine/core/ engine/eval/
.venv/bin/ruff check engine/
```
**運用の注意**: 各セル検証（generate/check/dup/property）は bootstrap 多重＋200-400 property で 2分超になり
バックグラウンド化されやすい。**フルスイート（約40分）は1本ずつ・他 pytest と競合させない**。

---

## 5. 別アカウントへの指示文（そのまま渡す）

> engine M0再構築の横展開（Phase P1〜）を継続してください。ブランチ `engine-m0-rework`、venv `.venv/bin/python`。
>
> **まず読む（順に）**:
> 1. `docs/goal_spec_2026-07-12.md`（ゴール仕様＝完成の定義。全実装は「どのCグループ・どのPhaseか」を宣言）
> 2. `docs/HANDOFF_engine_2026-07-13.md`（**最新**・本セッションの前進と新しい学び・§2 と §3）
> 3. `docs/HANDOFF_engine_2026-07-12.md`（§3 プレイブック11手順・§5 落とし穴9件＝**手順の正**）
> 4. P1残の実装設計 `docs/design_C2_polynomial_2026-07-13.md`（C2 残の solver/level_sep/落とし穴）
>
> **★再開の最初にやること**:
> ```bash
> cd /Users/koki/workspace/mongene-v2
> git log --oneline -5
> git status --porcelain                                        # 空(clean)
> .venv/bin/python -m engine.tools.goal_progress               # 51/630
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100     # 一式OK・exit0
> .venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -q   # フルスイート緑確認(約40分・1本ずつ)
> ```
>
> フルスイートが緑なら、**C2 polynomial 群の残（l4→l6→l1→l9→l7→l8）**を実装順に進める
> （`polynomial.py` に追記・linear.py は触らない）。設計は `design_C2_polynomial` 参照。
> その後 P1 完了確認 → P2（C1 g1数と式・C3 g3数と式＝SymPy直・最安）へ。
>
> **鉄則**: ①level間は steps の op列を変える（数値域だけの偽レベルは level_sep が落とす）②narration/ヒントに
> 数字を書かない ③**G-Q5t は答えの表示文字列も検査する**＝答えが bare 単項に退化して与式に現れる漏洩に注意
> （構成で退化を防ぐ）④dup_rate は eval/100seed 実測で ≤0.20（答えに効かない surface param は広くとる）
> ⑤frame語彙を足したら test_frames.py 同時更新（-k フィルタで deselect される罠に注意し別途単独実行）
> ⑥フルスイートは1本ずつ（CPU飽和回避）⑦サブエージェント並行（worktree）は不安定なので当面直列
> ⑧1セルずつ DoD 緑にしてコミット。
>
> **保留**: g2_l29 graph Lv3・g2_l30 fv Lv3 は word_problem/幾何寄りで T1 では忠実に量産できない
> （§3.2 参照）。M1 の word_problem 基盤と合わせて再検討。無理に量産しない。

---

*引き継ぎ書（2026-07-13・P1 継続セッション）。次アカウントは本書 §5 の指示文から入ること。*
</content>
