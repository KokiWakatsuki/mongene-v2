# 引き継ぎ書 engine 2026-07-14b（P2/C3残21+C5残2の並列8クラスタ化・前セッションはプロセス強制終了で中断）

本書は `docs/HANDOFF_engine_2026-07-14.md`（★★運用モデル★★＝統括はSonnet5・高）の**直後のセッション**の記録。
**実装の進捗はほぼゼロ**（後述）。今回の価値は「C3残21＋C5残2の正確な座標・設計・8クラスタ分割」がリサーチ済みであること。

## 0. まず読む順
1. `docs/goal_spec_2026-07-12.md`（ゴール仕様v1.0）
2. `docs/HANDOFF_engine_2026-07-14.md`（**★★運用モデル★★＝統括=Sonnet5・高、難所のみOpus検証ゲート／§7鉄則9項目**は今回も完全に有効）
3. 本書

venv `.venv/bin/python`。ブランチ `engine-m0-rework`。

## 1. 現状（このセッション終了時点）
- **最新コミットは `4941388`（#80: g3_l22.calculation Lv2/Lv3）のまま不変**。goal_progress **182/630（28.9%）**・C3 47/68・C5 34/36・作業ツリーclean（`scratchpad/`のみ untracked）。
- 前セッション（本セッション）は「C3残21＋C5残2の計23セルを8クラスタに分割し、独立git worktreeで並列実装」を試みたが、**8体のバックグラウンドエージェントが作業中にホストプロセスごと強制終了**（`<task-notification status="failed">`×8、"previous Claude Code process exited"）。**mainブランチ(engine-m0-rework)には一切変更が入っていない**（既に確認済み・golden/commit実行前に切れたため無傷）。

### 1.1 8クラスタの結果（worktree実地確認済み）
| クラスタ | worktree/branch | 結果 |
|---|---|---|
| POLY (g3_l12/l13) | `agent-a1387736a6ba8663f` / `engine-m0-rework-c3-l12l13` | **部分的に有用**。solver/recipe/checkerのコードが存在→WIPコミット済み(`06db224`)。**template/family yaml/concepts.yaml/test_recipes.py登録は未着手・完全未検証**。 |
| RADICAL (g3_l15/l23) | `agent-a371d5344fb241b38` | 成果なし（`.venv`の残骸のみ）。ゼロから。 |
| DECIMAL (g3_l16) | `agent-a87278350faa1ff15` | **部分的に有用**。solver完成（Lv1/Lv2両方・厳密整数演算）→WIPコミット済み(`3f50a94`)。**循環小数の表記規約を新設決定済み**（§3参照・再利用推奨）。recipe以降は未着手。 |
| HUB (knowledge 6セル) | `agent-a0f40be7b391747f2` | 成果なし。ゼロから。 |
| QUADRATIC (g3_l29/l30) | `agent-a3bc2b616e7672d40` | 成果なし（`.venv`の残骸のみ）。ゼロから。 |
| MOTION (g3_l31 find_value) | `agent-a3dda886559b3804d` | 成果なし。ゼロから。 |
| C5-LINEAR (g2_l30) | `agent-ac334747e3d58813b` | 成果なし。ゼロから。 |
| VISUAL (graph_table×2) | (worktree自体が存在せず) | 成果なし（変更なしで自動削除された模様）。ゼロから。 |

**worktreeは全て `.claude/worktrees/agent-*` 配下に現存**（削除していない）。新アカウントは `git worktree list` で確認し、POLY/DECIMALの2つは**中身を読んでレビューしてから使うか判断**、他5つ+VISUALは**不要なら `git worktree remove <path>` で構わない**（未commit分は既にWIP化済みで損失なし。ただし削除は破壊的操作なので、判断は新アカウント・ユーザーに委ねる）。

## 2. 教訓（次回への申し送り）
- **8並列は前セッションでは大きすぎた可能性**（プロセスごと落ちた＝リソース枯渇か、単なるアプリ再起動か原因不明）。新アカウントで再挑戦する場合、**2〜4クラスタ程度に絞る／各クラスタのDoDを細切れにしてこまめにcommitさせる**（1クラスタ=1コミットではなく、solver完成時点で一旦WIPコミットさせる等）と、途中終了時の損失が小さくなる。
- 並列自体の設計（ファイル単位でクラスタを割り、独立worktreeで作業→conductorが順次マージ）は妥当なので、**設計自体は使い回してよい**（下記§3にそのまま再掲）。

## 3. C3残21＋C5残2の正確な座標・設計（再利用可・リサーチ済み）

`engine/core/curriculum.load_curriculum()` + `engine/core/pipeline.capabilities()`（要 `engine.bootstrap.bootstrap()` 呼び出し）を突合して機械抽出済み。以下がC3の missing 21件・C5の missing 2件の**全件**（unit, form, level, ledger desc）。

### C3 missing (21)
```
g3_l12  calculation 2  因数分解や公式で工夫し数値計算・式の値を直接求める（例: 98²-2²）
g3_l12  calculation 3  対称式・条件式を変形してから代入する非自明な工夫（例: x+y=5,xy=3→x²+y²）
g3_l13  calculation 2  証明で用いる展開・因数分解の式変形処理（例: (2n+1)²-(2n-1)²展開）
g3_l14  knowledge   2  √a²=|a|等の意味理解・具体例への適用と判別
g3_l15  calculation 1  2乗して比較し根号数の大小を判定（例: √5と√8）
g3_l15  calculation 2  係数付き√や整数と√の混在で変形してから比較（例: 3,√7,2√2を順に）
g3_l16  calculation 1  分数を小数に直す/循環小数を循環節の表記で書く処理（例: 5/11）
g3_l16  calculation 2  循環小数を分数に直す変形処理（例: 0.27循環）
g3_l16  knowledge   2  与えられた数を有理数/無理数に分類・判別し具体例に適用
g3_l23  calculation 2  立式後の根号の四則・簡約処理（例: √2×√18+√50）
g3_l23  find_value  2  面積等の条件から一辺の長さ等を√で1〜2手順で求める（例: 面積45cm²→1辺）
g3_l24  knowledge   2  与えられた値が解かを判定し解の個数の意味を理解
g3_l26  knowledge   1  与式とa,b,cの対応を識別
g3_l28  knowledge   2  式の形からどの解法が有効かを判断
g3_l29  calculation 2  立式した2次方程式の求解処理（例: x(x+1)=56）
g3_l3   knowledge   1  与式がどの乗法公式の形かを識別
g3_l30  calculation 2  立式した方程式の求解処理（例: x(x+3)=40）
g3_l30  find_value  2  図形条件から面積・長さの関係を立式して求める（例: 縦x横x+3面積40）
g3_l31  find_value  2  指定時刻での動点の位置から長さ・面積を立式して求める（visual不要）
g3_l31  find_value  3  場合分けを要する区間での面積を図から構成して求める（visual不要）
g3_l31  graph_table 2  時間と面積の対応を表・グラフに整理して読む（★visual要）
```

### C5 missing (2)
```
g2_l29  graph_table 3  区間ごとに折れ線となる面積グラフをかく（★visual要）
g2_l30  find_value  3  速さの変化・複数区間を含む交点を求める
```

抽出コマンド（再現用）:
```bash
.venv/bin/python -c "
from engine.bootstrap import bootstrap
bootstrap()
from engine.core.pipeline import capabilities
from engine.tools.goal_progress import classify
from engine.core.curriculum import load_curriculum
have = {(c.unit, c.form, c.level) for c in capabilities()}
cur = load_curriculum()
for unit_id, unit in cur.units.items():
    section = str(unit.get('section',''))
    for form, fd in (unit.get('forms', {}) or {}).items():
        for level_key, ld in ((fd or {}).get('levels', {}) or {}).items():
            level = int(level_key)
            gid = classify(unit_id, section, form)
            if gid in ('C3','C5') and (unit_id, form, level) not in have:
                print(gid, unit_id, form, level, ld.get('desc',''))
"
```

### 3.1 8クラスタ分割（ファイル衝突回避の設計・そのまま再利用可）
| クラスタ | 対象セル | 触るファイル | 難度 |
|---|---|---|---|
| POLY | g3_l12(Lv2/Lv3)・g3_l13(Lv2) | `polynomial.py`拡張 | 低。l12 Lv3は**x,y実数解不要・s=x+y,p=xyの恒等式のみで解ける**（大幅減）。l13は既存`expand_expression`のn文字版でほぼ流用。 |
| RADICAL | g3_l15(Lv1/Lv2)・g3_l23(Lv2/find_value Lv2) | `radical.py`拡張 | 中。l15は新規「比較/順序」型answer設計が必要（下記§3.2）。l23は既存`simplify_radical`の流用が濃厚。 |
| DECIMAL | g3_l16(Lv1/Lv2) | 新規`rational_form.py` | 中。**solverは完成済み**（§4参照・そのまま使える可能性大、要レビュー）。 |
| HUB | l3.k1/l14.k2/l16.k2/l24.k2/l26.k1/l28.k2 | `letter_expr.py`既存3ハブ拡張 | 低〜中。既存の`_TERM_MAPS`/`_RULE_MAPS`拡張パターンの踏襲（#79実績あり）。knowledge答えは digit-free 必須（鉄則①）。 |
| QUADRATIC | g3_l29(Lv2)・g3_l30(Lv2/find_value Lv2) | `quadratic.py`拡張 | 低。x(x+c)=k型の展開→既存`solve_quadratic`流用。find_valueは正根のみ採用（負根は構造的に除外）。 |
| MOTION | g3_l31(find_value Lv2/Lv3) | 新規ファイル | 中〜高。座標幾何（動点）だが**visual不要**（純代数）。shoelace公式での対称検証推奨。 |
| C5-LINEAR | g2_l30(find_value Lv3) | `linear.py`拡張（既存g2_l29.find_value Lv1/Lv2に倣う） | 中。区分関数の「どの区間か」判定を構成時に保証（実行時retry不要）。 |
| VISUAL | g3_l31(graph_table Lv2)・g2_l29(graph_table Lv3) | `visuals/graph.py`拡張＋新family | **要注意＝運用モデルの「難所」に該当**。既存`render_segment_solution_svg`（単一線分）の複数線分（折れ線）拡張が必要。**g3_l31.graph_table Lv2は実は単一直線で足りる可能性が高い**（P=(vx,0)、面積y=(sv/2)xは単一線形・既存`render_segment_solution_svg`で対応可）ので、新規visual投資が必要なのは実質**g2_l29.graph_table Lv3のみ**（既存g2_l29.find_value Lv1/Lv2の場面設定を先に読むこと）。 |

### 3.2 一部セルの設計メモ（前セッションで詰めた考察）
- **g3_l15（根号の大小比較）**: bare√同士はradicand比較で十分（2乗の説明は方法論の語り）。3値混在（Lv2）は各値の2乗（有理数）を比較して順序付け——evalf厳禁、sympyの厳密比較で十分。answer表現はSymbolicAnswerのdisplayに不等号チェーン文字列、srepr に順序付きTupleを機械比較用に。
- **g3_l23.find_value（面積→1辺）**: `simplify_radical`の平方因数抽出流用でほぼ新規コード不要。FIND_VALUE_FRAMEの既存vocab（`condition`/`figure_spec`, asked=`value`）で足り、frame変更は不要。
- **g3_l29/l30（x(x+c)=k型）**: 既存`solve_quadratic`への展開後の受け渡しのみ。l29/l30で共通のmode（c違い）で1実装を両family流用可。
- **g3_l31 find_value（動点）**: 正方形をA=(0,0),B=(s,0),C=(s,s),D=(0,s)に固定し、Pの位置をtの区分関数で構成。面積はshoelace公式で独立検証（`.equals(0)`）。Lv3は「A→B→C」の2区間目に確実に入るt/s/vを構成時に保証（実行時場合分け判定は不要、境界値は排除）。
- **g3_l31.graph_table（Lv2）**: 上記の通り単一直線で済む可能性が高く、visual新規投資は不要（既存`render_segment_solution_svg`直用の可能性）。
- **フレーム語彙**: どのクラスタも既存の`CALCULATION_FRAME`/`FIND_VALUE_FRAME`/`KNOWLEDGE_FRAME`のvocabで足りる設計にできている（`frames.py`は触らない）。l12 Lv3は「入力を1つの既存キーに複数値をまとめる」手法（g3_l22 Lv3と同型）で解決可能。

## 4. DECIMAL solverの再利用可能な設計（WIPコミット`3f50a94`より）
循環小数の教科書表記規約を新設（コードベースに既存規約なし）:
- **display**: 循環節の最初と最後の数字の直後に結合文字 U+0307 (COMBINING DOT ABOVE) を付与。例: 5/11=0.454545...→循環節"45"→ `"0.4̇5̇"`。1桁循環（例1/3=0.333...）は点1つ: `"0.3̇"`。
- **srepr（機械比較用）**: ASCII専用の正準形 `"0.<非循環部>(<循環節>)"`（例 `"0.(45)"`）。
- 変換アルゴリズムは整数の余り追跡（長除法）と代数的閉じた式（Fraction自動既約化）、フロート不使用（鉄則⑥）。
- 実装は `.claude/worktrees/agent-a87278350faa1ff15/engine/packs/math/solvers/rational_form.py`（199行・commit `3f50a94`）。**そのまま使うかは新アカウントの判断（未検証）**。

## 5. 鉄則・DoD（変更なし・引き継ぎ書14参照）
`docs/HANDOFF_engine_2026-07-14.md` の §7（鉄則9項目）・DoD順（solver等5点セット→pytest -k→dup実測(build_mr)→spec_cli approve→golden→mypy strict/ruff→engine.eval→フルスイート単独→commit）がそのまま適用される。**★★運用モデル★★（統括=Sonnet5・高、難所=VISUAL クラスタのみOpus検証ゲート）も継続**。

## 6. 次アカウントへの推奨アプローチ
1. まず `git worktree list` と本書§1.1の表で現状把握。POLY/DECIMALのWIPは中身を読んで「使う/捨てて再実装」を判断（推奨: 一度レビューしてから活かす方が速い）。
2. 8クラスタ丸ごと並列よりも、**まず2〜3クラスタ（例: POLY, DECIMAL, QUADRATIC — 低リスクかつ既存パターン流用度が高いもの）から着手**し、動作確認できたら残りを追加投入する方が前回のような全損リスクを避けられる。
3. VISUALクラスタは最後（かつOpus検証ゲート必須）。g3_l31.graph_table Lv2は実は新規visual不要の可能性が高いので、まず数式的に確認してから着手判断。
4. 各クラスタは前回のプロンプト設計（本書§3の表・§3.2の設計メモ）をそのまま使い回せる。
