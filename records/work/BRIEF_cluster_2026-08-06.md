# セル横展開 共通ブリーフ（2026-08-06 / find_value・knowledge・calculation 形式）

リポジトリ: `/Users/koki/workspace/mongene-v2`
ベース: ブランチ `engine-m0-rework` の `7545348`（429/630）。
**あなたのワークツリーの HEAD が `7545348` であることを最初に `git log --oneline -1` で確認せよ。**
違っていたら作業せず即報告（過去に旧 master 基点でワークツリーが作られ成果が全滅した事故がある）。

## ゴール

割り当てられたセル（プロンプトに列挙）を開通させる。
**新 solver をできるだけ作らない**。既存 solver の合成・mode 追加で済むならそうする。
数学的に新しい計算が要るときだけ新 solver を足し、理由を報告する。

## 台帳が正

`engine/curriculum/math/units.generated.yaml` の当該セルの `desc` / `example` が題材の正。
確認コマンド:

```bash
PYTHONPATH=. uv run python scratchpad/show_cells.py g1_l51 g1_l52   # 引数はunit id
```

family yaml の `source_desc` に desc/example を**転記**し、そのうえで
「この form の型」「level_sep（Lv 間で何が構造的に違うか）」「検証（どの2経路で答えを突き合わせるか）」
を日本語で書く。手本 = `engine/curriculum/math/families/g2_l51.word_problem.yaml`。
台帳の題材から一部を落とす判断をしたら**理由を source_desc に明記**する。

## 作るもの（クラスタ1つあたり）

1. `engine/packs/math/recipes/<cluster>.py` — recipe（1本で担当セル全部を賄えるのが理想）
2. `engine/packs/math/checkers/<cluster>.py` — `{RECIPE_NAME}.double_solve`
3. `engine/packs/math/solvers/<cluster>.py` — 新 solver が要る場合のみ
4. `engine/curriculum/math/families/<lesson>.<form>.yaml` — レッスン×形式ごと
5. `engine_tests/golden/math.<lesson>.<form>/` — `spec_cli approve` で生成
6. 登録: `recipes/__init__.py` / `checkers/__init__.py` / `solvers/__init__.py` に import 追加、
   `engine/curriculum/math/concepts.yaml` に concept_tags 追加
7. **`engine_tests/unit/test_recipes.py` の `_*_CELLS` リストに担当セルを必ず追加**（末尾に自分用の
   `_XXX_CELLS` と `@pytest.mark.parametrize` ブロックを新設するのが衝突しない）
   （capabilities に出ても property は自動では増えない。過去4体とも忘れた最頻の抜け）
8. テンプレは既存を再利用できないか先に探す。要るなら `engine/packs/math/templates/` に追記。

**ファイル衝突回避**: recipe/checker/solver は**自分のクラスタ専用の新規ファイル**に書く。
`__init__.py` / `concepts.yaml` / `test_recipes.py` / `templates/*` は他エージェントと共有なので
**末尾追記のみ**（既存行を書き換えない）。

## 必ず守る契約（過去に踏んだ罠）

1. **params には「問題文に出ている数値」だけを置く。導出値・答えを置かない。**
   checker は params の数値だけから solver を呼び直して独立に再計算する。
   導出値を params に置くと「本文の数値を書き間違えても検証が気づかない」経路ができる。
2. **draw した点ラベル・図に出る記号は params に必ず含める。**（dup_rate 対策にも効く）
3. **G-Q5t（答え漏洩ゲート）の whitelist は `mr.given` の値だけ**
   （実装 `engine/core/verify/quality_gates.py` の `_build_given_whitelist`・両符号）。
   スキャン対象は `context_slots` を含む問題文全体。
   → **設問文にだけ出る数値は whitelist されず、答えと一致すると偽陽性で拒否される。**
   → **narration（steps）に数字を書かない。値は `result_display` にのみ置く。**
   → 助数詞衝突は `_COUNTER_EXPR_RE` で除去済み（次・元 等）。新しい衝突語に当たったら報告（core は触るな）。
4. **`sympy.nsimplify(文字列)` は偽の閉形式を返す**。solver に文字列係数を渡さない。必ず `sympify` を通す。
5. **level_sep は「何を問うか・手数・概念」を動かす。数値の大小だけでは分離しない。**
   fingerprint =（given の型, asked, **steps の op 列**, 小問数）なので、
   **Lv 間で steps の op 列を必ず変える**（同じだと eval の level_sep が落ちる）。
6. **`form=knowledge` は `asked=choice` のみ**（ChoiceAnswer 必須。数値答えでも choice 化する）。
   答えテキストに ASCII 数字を書かない（`2数`→`両方の数`）。
7. **ゲートは答えが 0 や 1 に潰れる退化を素通りする**。degenerate な構成は property で明示的に禁止する。
8. **`spec_cli check` の dup_rate は常に 0.0 で当てにならない。**
   本物は `PYTHONPATH=. uv run python scratchpad/check_cell.py <unit> <form> <lv,lv>`（実測100seed）。
   **全担当セルで実測し、0.20 以下であることを報告に書く。**
   超過時の既知の直し方: ①draw した記号名を params に入れる ②候補域・題材リストを広げる
   ③答えに無関係な surface（品名・点名・単位）を足す ④場面の枠組みそのものを2通り引く。

## コマンド

すべて `uv run` 経由（素の `python` は PATH に無い）。スクリプト直実行は `PYTHONPATH=.` が要る。
**pytest は必ず `--no-cov`**（付けないと apps/ のカバレッジで重くなり必ず exit 1）。

```bash
uv run python -m engine.tools.spec_cli check   math.<lesson>.<form>
uv run python -m engine.tools.spec_cli preview math.<lesson>.<form>   # HTML 目視
uv run python -m engine.tools.spec_cli approve math.<lesson>.<form>   # check ok 後
PYTHONPATH=. uv run python scratchpad/check_cell.py <unit> <form> <lv,lv>

uv run python -m pytest engine_tests -q --no-cov -k "<lesson>"        # セル単位 property
uv run python -m pytest engine_tests/contract engine_tests/unit -q --no-cov
uv run ruff check engine && uv run mypy engine
```

## DoD

- 担当全セルで `spec_cli check` が `ok: true`、golden 承認済み
- `check_cell.py` 実測 dup_rate ≤ 0.20（**数値を報告に書く**）・120seed 全ゲート拒否 0
- `test_recipes.py` に property を追加済み（construct / double_solve / 非退化）
- `uv run python -m pytest engine_tests -q --no-cov` が通る
- `ruff check engine` / `mypy engine` クリーン（engine_tests の ruff 既存15件は増やさない）
- **生成物を実際に目視し、手計算で答えを照合した結果**を報告に含める
  （例:「l51 Lv2 seed1: 母線9・半径3 → 中心角 360·3/9=120°、表面積 27π+9π=36π ✓」）

## 報告

差分は**コミットせず未コミットのまま**ワークツリーに残す（親がマージする）。
報告に ①担当セルと最終状態 ②手計算照合の実例 ③実測 dup_rate 一覧 ④踏んだ罠・設計判断 ⑤残課題。
