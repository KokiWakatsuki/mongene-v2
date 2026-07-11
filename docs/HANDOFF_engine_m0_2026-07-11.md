# 引き継ぎ書: Education OS 問題供給エンジン M0 再構築（2026-07-11）

本書は `docs/requirements_2026-07-11.html`(v2.1) と `docs/implementation_design_2026-07-11.md`(v1.1)
に基づく **M0 金の縦串** 実装の途中状態を、別セッション（別アカウント）へ引き継ぐためのもの。
アカウント切替（レート制限）のため作成。**バックグラウンドの sonnet サブエージェントはセッション終了で失われる**が、
作業ツリーのファイルはディスク上に残る。

## 0. まず読む
- 要件: `docs/requirements_2026-07-11.html`（F/Q/N/D 番号体系）
- 実装設計: `docs/implementation_design_2026-07-11.md`（H1〜H8 の穴・§4契約・§5 pipeline・§6 pack・§7 T1・§8 gates・§11 タスク表）
- ブランチ: **`engine-m0-rework`**（master から分岐）
- venv: `.venv/bin/python`（Python 3.13・pydantic 2.13・sympy・jinja2 導入済）
- **鉄則（過去の失敗対策・memory参照）**: サブエージェントの完了報告は鵜呑みにせず **git 実体 + テスト実走** で検証してから完了マークする。

## 1. 進め方の中央設計判断（確定済み）
- 新トップレベル `engine/` を並行構築（旧 `apps/api` は触らない・D-6）。旧 pytest 465本は維持（guardrail）。
- **依存規律**: `engine/core` は `engine/packs`・`engine/curriculum`・`apps` を **import しない**（curriculum はファイル読みのみ）。`packs/math` → core のみ。
- **M0 縦串 = `g2_l25` + `g2_l24`**（find_value 中心）。**g1_l36 は word_problem/場面グラフ＝T3依存のため M1 送り**（設計「word_problem を含まない構成を優先」に従う判断）。
- **N-6 正の分界**: `units.generated.yaml`（自動生成・手編集禁止）／概念・誤答要因・DAG・fact は手書き YAML。
- テスト実行: `.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -q`（`-o addopts=""` で旧cov設定を無効化）。
- mypy: `.venv/bin/python -m mypy --strict engine/core/` 等。

## 2. 完了済み（コミット済み・全 green）
| Task | 内容 | コミット |
|---|---|---|
| 1 | core骨格: `contracts.py`(全pydantic契約)・`rng.py`(derive_rng/draw/ドメイン記法v1)・`registry.py`(recipe/solver/template/checker/frame/gate/hint登録)・`signature.py`(fingerprint/dup_key) | `2ea42c3` |
| 2 | spec基盤: `core/spec/loader.py`・`core/spec/lint.py`(R1-R8) | `b26bb10` |
| 3 | curriculum: `tools/convert_input_spec.py`→`curriculum/math/units.generated.yaml`(184単元)・手書き`concepts.yaml`/`error_causes.yaml`/`prerequisites.yaml`/`facts.yaml`・`core/curriculum.py`(loader + `lint_curriculum` C1-C6) | `6c61271` |
| 5a | 数学 `packs/math/frames.py`(7型FrameProtocol実装)・`packs/math/solvers/linear.py`(縦串4ソルバ・op列でLv分離) | `6c61271` |
| 4 | `core/pipeline.py`(generate/resolve/capabilities/Supplier)・`core/render/t1_template.py`(TemplateContext/TextResult/T1レンダラ/フィルタ)・`core/verify/gates.py`(枠組み+G-SCHEMA) | `5e47852` |
| — | core配線: 段バンドル `TextStageInput`/`VisualStageInput`・`register_template` shortcut・remedial時 `curriculum_view["remedial_target_concepts"]`(G-Q7r用) | `7835cd0` |

**コミット済み時点で core 系 82 tests + 全体は Task4 時点で 122 tests green。**

### 主要な確定インタフェース（次の実装が従うべき契約）
- `RecipeFn`: `(ctx: CellContext, rng: Rng) -> MR`。**recipe は外側 seed を知らない**。pipeline が `mr.model_copy(update={"seed": seed})` で刻印。
- ソルバ（`REGISTRY.solver(name)`・全て登録済）: `math.linear_expr_from_two_points(p1,p2,method)`（method∈{slope_then_intercept, simultaneous}・op列でLv分離）／`math.linear_expr_from_slope_point(slope,point)`／`math.linear_expr_parallel_through_point(parallel_slope,point)`／`math.read_two_lattice_points(p1,p2)`。→ `Solution(answer, steps)`。
- `TemplateContext`（公開のみ）: `given:dict[str,str]`・`context_slots`・`sub_questions:list[SubQuestionView(label,asked,narrations)]`。**answer/srepr/params は載らない**（Q5を構造で防ぐ）。
- `TextResult`: `problem_text:str`・`prompts:dict[label,str]`・`explanations:dict[label,str]`・`hints:dict[label,list[str]]`・`render_keys:dict`。
- テンプレ: Jinja2文字列を `registry.register_template(name, src)` 登録・`spec_level.text["template"]` 参照・`SandboxedEnvironment`・フィルタ `num`/`frac`/`pt`/`unit`。
- ゲート段の obj: mr段=`MR`／text段=`TextStageInput(.mr,.text)`／visual段=`VisualStageInput(.mr,.svg,.visual_plan)`。`@register_gate(stage,name)`・fn `(obj,ctx)->(ok,detail)`・`run_gates` 最初の失敗で `GateFailure`→generate が `Unsupported(verification_exhausted)` 化。
- Unsupportedコード: unit_not_found/form_not_supported/level_not_supported/purpose_not_supported/cause_not_found/verification_exhausted/supply_exhausted/not_implemented。

## 2.5 追加完了（2026-07-11 セッション2・全 green・コミット済み）
| Task | 内容 | コミット |
|---|---|---|
| 5b | 数学 recipe4本(`math.linear_from_two_points`/`_slope_point`/`_parallel_condition`/`graph_read_two_points`)・T1テンプレ・families(`g2_l25`/`g2_l24` find_value・`g2_l25` graph_table)。**1013 property tests**(各200seed double-solve)。mypy strict修正込 | `77aeb8b` |
| 6 | 動的ゲート本体 `core/verify/quality_gates.py`(G-SIG/G-FP/G-Q1/G-Q2/G-Q7[+Q7r]/G-Q5t/G-GND/G-STY/G-Q5v)を `install_quality_gates(registry)` 明示登録。漏洩/接地の数値正規化は self-contained 再実装。各ゲートに壊しテスト(32) | `650f9ca` |
| §4統合 | pack側 `double_solve` checker(`packs/math/checkers/linear.py`)・`engine/bootstrap.py`(pack登録+ゲートinstallの単一入口)・**G-Q5t修正**(式の答えは係数分解でなく式全体で漏洩判定=§8.2「式中係数除外」準拠。分数傾きLv3の偽陽性解消) | `89529c1` |
| §4統合 | 金の縦串 contract テスト `engine_tests/contract/test_vertical_slice.py`(find_value全セル+remedial+G-Q7r) 17件 | `2194dbb` |
| 8 | 図エンジン `packs/math/visuals/graph.py`(座標平面SVG・matplotlib非依存・モノクロ・軸目盛のみtext)。**設計判断**: graph_table「読む」は図に式も答え座標も描かず、recipeの `given={}`(式は図提示・内部param)でG-GND自明通過。`visual_builder=math.linear_graph` をspecに配線。test_visuals/test_graph_table_slice | `8df0465` |
| 7 | 制作ツール `tools/spec_cli.py`(preview HTML/check=lint+smoke+簡易dup_rate/approve=golden保存)・golden回帰機構 `engine_tests/golden/`。find_value縦串を承認済みgoldenで固定 | `4b97471` |
| 9 | **縦串制作の仕上げ(DoD締め)**: graph_table描画範囲改善(spec domain調整=YAMLのみ・答え点y有界化±26→±16でグリッド最大36→28目盛)→ preview検収 → `spec approve` で golden固定(`engine_tests/golden/math.g2_l25.graph_table/` seed1-3)。remedial DoD機械判定 `engine_tests/contract/test_remedial_dod.py`(全誤答要因×5seedがgenerate成功+G-Q7r被覆・対応表完全性) | 本セッション |
| 10 | **eval一式** `engine/eval/`: `_harness.py`(MR構築=pipeline忠実再現/セル走査/remedial走査)・`coverage_scan.py`(生成不能0・ゲート素通り0=登録ゲート数検査・remedial対応表)・`dup_rate.py`(2系統: dup_key系セル内衝突率+fp系family横断署名跨ぎ衝突)・`level_sep.py`(署名相異[静的]+fp相異[必須]+単調性=not_declared)・`retry_stats.py`(bounded_retry発動率/構成失敗)・統合CLI `python -m engine.eval`。各CLI・JSON・終了コード。テスト `engine_tests/eval/test_eval_suite.py`(合格+わざと壊すfail経路) | 本セッション |

**現状の到達点（縦串は実物エンジンで完動）**: `from engine.bootstrap import bootstrap; bootstrap()` 後、`generate()` で以下が全ゲート通過し Problem を返す:
- `g2_l25.find_value` Lv2/Lv3・`g2_l24.find_value` Lv1/Lv3（全 seed）
- `g2_l25.graph_table` Lv2（図つき・全 seed）
- remedial: `g2_l25` fv Lv2 → cause `lf.substitution_error` → `g2_l24` fv Lv1 に解決・G-Q7r 通過
- テスト全体 **1224 passed**・mypy strict・ruff クリーン
- `tools/spec_cli.py check math.g2_l25.find_value` → lint/smoke クリーン・dup_rate 0.0
- **G-Q5t 助数詞誤検知を修正済み（`9c9dc3b`）**: graph_table のテンプレ「2**つ**の格子点」の助数詞 "2" が答え座標の "2" と衝突し 19%(38/200 seed) が偽陽性 `verification_exhausted` になっていた。§8.2 除外規則の一種として日本語助数詞（数字+つ/点/個…）を漏洩スキャンから除外。**graph_table Lv2 は 200/200 seed 生成成功**。連続 seed 全域の回帰テストで cherry-pick 隠蔽を防止（`test_graph_table_slice.py`）。

### ★サブエージェント運用の教訓（次セッション必読）
- `general-purpose` サブエージェントは `Agent` ツールを持つため、**「実装せよ」と投げると自分で書かず孫エージェントに委譲する連鎖に陥る**事例が Task8 で多発した（tool_uses 2〜4 で「起動しました。待ちます」と返して何も書かない）。結局 descendant の一部が部分的にファイルを land させたが、**packs/math/__init__ の配線・テスト2本・spec更新・mypy戻り型が抜けており、オーケストレータ(私)が git 実体を精査して手で補完**した。
- 対策: 図のような設計判断を含む中規模タスクは**サブエージェントに丸投げせずオーケストレータが主導**するか、投げるなら「委譲禁止・自分でRead/Write/Bashせよ」を明記し、**完了後は必ず git 実体+個別テスト実走+mypyで検証**（報告は信用しない）。並行サブエージェントの共有ツリー書き込みは stale pycache で `has_visual=False` 等の一時的誤検出も起こす→`__pycache__` 一掃して再確認。

## 3. 【旧】中断時に走っていた作業（下記は 2.5 で解決済み・履歴として残す）

### Task5b（数学 recipe/template/spec）— **ほぼ完成・未検証・未コミット**
作業ツリーに以下が存在（サブエージェント完了報告前に中断）:
- `engine/packs/math/recipes/linear.py`（recipe群）
- `engine/packs/math/templates/`（T1テンプレ登録）
- `engine/packs/math/__init__.py`・`recipes/__init__.py`（登録副作用の import 追加＝ M 差分）
- `engine/curriculum/math/families/{g2_l25.find_value,g2_l24.find_value,g2_l25.graph_table}.yaml`
- `engine_tests/unit/test_recipes.py`・`test_families_spec.py`
- **確認済み**: `import engine.packs.math` は成功。テスト結果は §5 の再開手順で実走して確認せよ（中断直前にバックグラウンド実行を開始したが結果未取得）。
- ブリーフ要点: recipe は answer-first（§6.1）・`@register_recipe(name, provides_concepts=[...])`。想定 recipe 名: `math.linear_from_two_points`／`math.linear_from_slope_point`／`math.linear_from_parallel_condition`／`math.graph_read_two_points`。graph_table は visual: required で **MR.visual_plan を最小構築し Task8 に TODO を残す**方針。cause_tags/concept_tags は `curriculum/math/{concepts,error_causes}.yaml` の実在IDのみ（`lf.confused_with_proportional`/`lf.substitution_error`/`lf.point_reading_error`・概念は `linear_function.*`/`graph.read_lattice_points`）。g2_l24 fv Lv1 の concept_tags は **必ず `linear_function.intercept_from_point` を含む**（G-Q7r 前提）。

### Task6（ゲート本体）— **未着手同然・要再ディスパッチ**
- 作業ツリーに新規ファイルは**まだ無い**（`core/verify/gates.py` は Task4/私の枠組みのみ）。`test_gates.py` 無し。
- ブリーフ（そのまま再利用可）: `engine/core/verify/quality_gates.py` に G-SIG/G-FP/G-Q1/G-Q2/G-Q7[+G-Q7r]/G-Q5t/G-GND/G-STY/G-Q5v を実装。**グローバル副作用を避け** `install_quality_gates(registry=REGISTRY)` 明示登録方式（既存ダミーテストを壊さないため）。
  - G-SIG: `mr.signature==ctx.spec_level.signature`
  - G-FP: `signature→fingerprint_hash` のプロセス内キャッシュで安定性（`reset_fp_cache()` 付き）
  - G-Q1: `registry.checker(f"{mr.provenance.recipe}.double_solve")(mr)->Solution` と各小問 answer 一致。未登録なら fail（H5強制）。**pack側 double_solve checker の登録は統合担当（あなた）が行う**（§4 参照）。
  - G-Q2: `ctx.frame.check_mr(mr)`
  - G-Q7/G-Q7r: concept/cause タグ実在（`ctx.curriculum_view["concept_ids"/"cause_ids"]`）・remedial時 concept_tags和 ⊇ `ctx.curriculum_view["remedial_target_concepts"]`
  - G-Q5t: 漏洩（旧 `apps/api/src/core/evaluation/leakage.py`・`number_normalize.py` を core内に self-contained 再実装。除外規則=given由来数値・係数・軸目盛）
  - G-GND: given表示値が problem_text に出現・小問数一致（全tier・旧 `grounding.py` 参考）
  - G-STY: 通貨=円・敬体 程度の最小
  - G-Q5v: svgテキスト ⊆ visual_plan.labels ＋ `frame.forbidden_visual_elements(asked)` の禁止要素チェック
  - 各ゲートに「わざと壊す」fail テスト（`engine_tests/unit/test_gates.py`）。

## 4. 統合担当（あなた＝オーケストレータ）が Task5b+Task6 後に行う配線
1. **pack側 double_solve checker の登録**: 各 recipe に対し `@register_checker("math.<recipe>.double_solve")` で、MR.params から独立ソルバを再計算し `Solution` を返す関数を `packs/math/` に用意（G-Q1 が呼ぶ）。ソルバは Task5a の登録済みものを使う。
2. **`install_quality_gates(REGISTRY)` をエンジン初期化で呼ぶ**（例: `engine/packs/math/__init__.py` の末尾 or `engine/bootstrap.py` 新設）。呼んだ状態で `generate(g2_l25 find_value Lv2/Lv3)` が **全ゲート通過して Problem を返す**ことを end-to-end で確認（縦串の base セル）。
3. remedial end-to-end: `generate(GenerateRequest(unit="g2_l25",form="find_value",level=2,purpose="remedial",options={cause_id:"lf.substitution_error"}))` が g2_l24 fv Lv1 に解決し G-Q7r 通過。
4. これらを `engine_tests/contract/` の統合テストに固定。

## 5. 再開手順（次セッションの最初のコマンド）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework のはず
git log --oneline -6                 # 7835cd0 が最新
git status --porcelain               # Task5b の未追跡ファイルが見えるはず
# Task5b の状態を検証:
.venv/bin/python -m pytest engine_tests/unit/test_recipes.py engine_tests/unit/test_families_spec.py -o addopts="" -p no:cacheprovider -q
.venv/bin/python -m mypy --strict engine/packs/math/recipes/ engine/packs/math/templates/
# 全体（Task6未実装でも core は green のはず）:
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -q
```
- Task5b が green なら **検証してコミット**（`engine M0 Task5b: recipe/template/縦串spec`）。赤なら修正。
- Task6 を再ディスパッチ（§3 のブリーフを sonnet サブエージェントへ。`engine/packs/math/` は触らせない）。
- 以降 §4 統合 → Task7(制作ツール spec preview/check/approve/golden) → Task8(図: 旧`apps/api/src/visuals/graph_renderer.py`・`builder.py`(line~855の答え漏洩が対策対象)を `packs/math/visuals/` へ・whitelist/幾何リーク/モノクロ) → Task9(縦串制作 全セルDoD+remedial DoD) → Task10(eval: coverage_scan/dup_rate2系統/level_sep(fp必須)/retry_stats)。

## 6. タスク状態（TaskList・2026-07-11 セッション3 末時点）
- #1〜#10 + §4統合 **全完了・コミット済み**（`git log --oneline` で最新確認）。
- **M0 金の縦串は実装完了**。全 base セル（find_value 4 + graph_table 1）DoD 締め済み（lint/smoke/dup_rate/level_sep/golden 承認/remedial DoD）。eval 一式が `python -m engine.eval` で 1 コマンド実行でき終了コードで CI 連携可能。
- 縦串スライスの eval 現況（全 OK）: coverage_scan=生成不能0・ゲート素通り0（mr7/text3/visual1 ゲート登録）・remedial 3要因 G-Q7r 通過／dup_rate=各セル≤0.04(閾0.20)・署名跨ぎ fp 衝突なし／level_sep=両 find_value family で署名・fp とも相異／retry_stats=発動0・構成失敗0。
- **M1 送り（未着手）**: FastAPI ラッパ・T2/T3・audit_runner(LLM監査 V3)・cost_meter・dashboard HTML・プール(Supplier差し込み)・採点フィクスチャ(D-2)・縦串クラスタ拡張(g2一次関数38セル)。

## 5.5 【完了】Task9→Task10（2026-07-11 セッション3）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework
git log --oneline -8
git status --porcelain               # 空（クリーン）のはず
# 縦串 + eval の再確認:
.venv/bin/python -m pytest engine_tests/contract/ engine_tests/golden/ engine_tests/eval/ -o addopts="" -p no:cacheprovider -q
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100    # 一式が OK・exit 0
```
- **Task9 完了**: graph_table の描画範囲を spec domain 調整（`g2_l25.graph_table.yaml`: slope±4→±3・intercept±6→±4・x±5→±4。答え点 y を±26→±16 に有界化。グリッド最大36→28目盛）。preview 機械検収（Unsupported0・答え座標が本文/図に非漏洩・グリッド有界）→ `spec approve` で golden 固定。remedial DoD は `engine_tests/contract/test_remedial_dod.py` が curriculum の全誤答要因を正として走査（要因追加で自動拡張）。
- **Task10 完了**: `engine/eval/`（core/pack を一切変更しない読み取り+生成のみ）。MR 実体が要る指標（dup_key/fp）は `_harness.build_mr` が pipeline の recipe 構成部（derive_rng + seed 刻印 + bounded_retry）を忠実に再現して MR を得る（Problem は params を運ばないため）。**設計判断**: dup_rate の fp 系はセル内では同一 signature ゆえ fp 一定（G-FP 安定の傍証）なので、意味論的に正しい「別署名を貼った実質同一構造」の検出は **family 横断の署名跨ぎ fp 衝突**として実装した（level_sep の fp 相異検査と表裏）。

### 既知の設計 smell（M1 で対処候補・今回は範囲外）
- `math.graph_read_two_points` は整数傾き a×切片 b から点を逆算するため、spec の `point_domain.y` が**実質デッド**（実際の答え点 y は a*x+b で決まる）。今回は spec domain を絞って可読性を確保したが、本筋は「2 格子点を直接選び、傾きは有理数でよい」構成に変える方が y を宣言域で有界化でき題材とも整合する（要 recipe 改修 + golden 再承認）。
- ruff nit（**私の変更外・既存**）: `engine_tests/unit/test_gates.py`・`test_core_foundation.py`・`golden/test_golden_slice.py` に未使用 import が数件残る（前セッションが engine_tests に ruff をかけていなかった痕跡）。`engine/` ソースは clean。CI で engine_tests も lint するなら別途一掃。

## 5. 【旧】再開手順（Task5b/6 用・履歴）

## 7. 注意点・落とし穴
- **並行サブエージェントの共有ツリー衝突**: 実際に `register_template` の未export で一時衝突が起きた（core に shortcut 追加で解決済）。core のインタフェース不足を見つけたら core を先に直す（§0）。
- capabilities() は families ディレクトリを走査し lint clean のセルのみ返す。recipe/template 未登録セルは R1 で落ちて capabilities に出ない（F-5/F-6 整合）＝正常動作。
- `generate` を **グローバル REGISTRY** で呼ぶと install 済みゲートが走る。ダミーテストは自前 `_Registry()` を注入して隔離している。
- MR.seed は placeholder でよい（pipeline 上書き）。
