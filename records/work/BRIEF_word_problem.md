# C14 word_problem 横展開 ブリーフ（共通）

リポジトリ: `/Users/koki/workspace/mongene-v2`（ベース: ブランチ `engine-m0-rework` の `23b82d1`）
現況: 410/630 セル。word_problem は 45/100。残り未実装 word_problem は 55 セル。

## ゴール

あなたに割り当てられたセル（別途指示）を `form=word_problem` として開通させる。
**新 solver をつくらない**のが原則。数学は既存 solver（`engine/packs/math/recipes/*.py`）に委ね、
文章題としての骨格（場面文＋小問）だけを新規に足す。

## 作るもの（クラスタ1つあたり）

1. `engine/packs/math/recipes/word_problem_<cluster>.py` — recipe 1本で担当セル全部を賄う
2. `engine/packs/math/checkers/word_problem_<cluster>.py` — `{RECIPE_NAME}.double_solve` を1本
3. `engine/curriculum/math/families/<lesson>.word_problem.yaml` — レッスンごと
4. `engine_tests/golden/math.<lesson>.word_problem/` — `spec_cli approve` で生成
5. 登録: `recipes/__init__.py` / `checkers/__init__.py` に import 追加、
   `engine/curriculum/math/concepts.yaml` に concept_tags を追加
6. テンプレが要るなら `engine/packs/math/templates/word_problem.py` に追記（既存テンプレで足りるなら足さない）

**ファイル衝突回避**: recipe/checker は必ず**自分のクラスタ専用の新規ファイル**に書く。
`__init__.py` / `concepts.yaml` / `templates/word_problem.py` は共有なので、末尾追記のみに留めること。

## 手本にするコード（必読）

- `engine/packs/math/recipes/word_problem_probability.py`（504行・6セルを1 recipe で賄う最新形）
- `engine/packs/math/checkers/word_problem_probability.py`（28行）
- `engine/curriculum/math/families/g2_l51.word_problem.yaml`（source_desc の書き方の手本）
- `engine/packs/math/templates/word_problem.py`
- 他の word_problem recipe: `word_problem_linear.py` / `word_problem_system.py` /
  `word_problem_quadratic.py` / `word_problem_linear_function.py` / `word_problem_expression.py` /
  `word_problem_relation.py` / `word_problem_sampling.py` / `word_problem_proportion.py`

## 台帳が正

`engine/curriculum/math/units.generated.yaml` の当該セルの `desc` / `example` が題材の正。
family yaml の `source_desc` に desc/example を**転記**し、そのうえで
「この form の型」「level_sep」「検証」を日本語で書く（g2_l51 の書式に倣う）。
台帳の題材から外す判断をした場合（例: グラフ作図の小問を落とす）は理由を `source_desc` に明記する。

## 必ず守る契約（過去に踏んだ罠）

1. **params には「本文に出ている数値」だけを置く。導出値・答えを置かない。**
   置くと `engine_tests/contract/test_word_problem_params_faithfulness.py` が落ちる（全 word_problem セル×8seed を機械検査）。
   checker は params の数値だけから solver を呼び直して独立に再計算する。
2. **`sympy.nsimplify(文字列)` は偽の閉形式を返す。** solver に文字列係数を渡さないこと。
3. **G-Q5t（答え漏洩ゲート）の whitelist は `mr.given` の値だけを走査する**
   （実装: `engine/core/verify/quality_gates.py` の `_build_given_whitelist`）。
   一方スキャン対象は `context_slots` を含む問題文全体。つまり **ask 文にだけ出る数値は
   whitelist されず、答えと一致すると偽陽性で拒否される**。ask 文に数値を置くなら
   given 側にも同じ値が出るようにするか、答えと衝突しない値域にする。
4. **draw した点ラベルは params に必ず含める。**
5. **word_problem の frame の `asked_vocab` は `{formulation, value}` のみ。**
   「グラフをかけ」等の作図小問は構造的に持てない（前例: g3_l31 / g2_l30 Lv3 は落として理由を明記）。
6. **level_sep は「何を文字に置くか」「手数と概念」を動かす。** 数値の大小だけ変えても分離しない。
7. 不等号は `SymbolicAnswer.srepr` の文字列比較でそのまま通る（`sympy.Le/Lt/Gt` 可・core 無改変）。
8. narration（steps）に数字を書かない。値は `result_display` にのみ置く。
   既存 solver の steps が題材語彙とズレる場合は合成後の意味に沿って組み直す。

## コマンド

すべて `uv run` 経由。スクリプトを直に走らせるときは `PYTHONPATH=/Users/koki/workspace/mongene-v2` を付ける。

```bash
# セル単位の検証（lint + smoke + dup_rate）
uv run python -m engine.tools.spec_cli check math.<lesson>.word_problem
# 目視プレビュー（HTML）
uv run python -m engine.tools.spec_cli preview math.<lesson>.word_problem
# golden 承認（seed1-3）※ check が ok になってから
uv run python -m engine.tools.spec_cli approve math.<lesson>.word_problem

# テスト（--no-cov 必須）
uv run python -m pytest engine_tests -q --no-cov -k "word_problem or recipes"
uv run python -m pytest engine_tests/contract engine_tests/unit -q --no-cov

# 静的検査（engine 配下は 0 エラーを維持。engine_tests には既存 15 件の債務あり＝増やさない）
uv run ruff check engine
uv run mypy engine
```

## DoD

- `spec_cli check` が担当全セルで `ok: true`（lint_errors / smoke_failures 空・dup_rate 警告なし）
- golden 承認済み
- `uv run python -m pytest engine_tests -q --no-cov` が通る
- `uv run ruff check engine` / `uv run mypy engine` がクリーン、engine_tests の ruff エラーが 15 件から増えていない
- 新 solver ゼロ（やむを得ず追加した場合は理由を報告）
- 生成物を実際に目視し、**手計算で答えを照合した結果**を報告に含める（例: 「Lv3 seed1: 57²−x²=3245 → x=2 ✓」）

## 報告

作業ツリーの差分はコミットせず**未コミットのまま残す**（親がマージする）。
報告には ①担当セルと最終状態 ②手計算照合の実例 ③踏んだ罠・設計判断 ④残課題 を簡潔に書く。
