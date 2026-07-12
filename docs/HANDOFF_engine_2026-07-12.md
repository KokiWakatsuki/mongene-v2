# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-12）

本書は **M0 金の縦串の完成** と、それに続く **横展開（g2 一次関数クラスタ）の進行中状態** を
別セッション（別アカウント）へ引き継ぐためのもの。アカウント切替（レート制限）のため作成。
**バックグラウンドの subagent はセッション終了で失われる**が、作業ツリーのファイルはディスク上に残る。

---

## 0. まず読む（順に）
1. 要件: `docs/requirements_2026-07-11.html`（v2.1・F/Q/N/D 番号体系）
2. 実装設計: `docs/implementation_design_2026-07-11.md`（v1.1・H1〜H8 の穴・§4契約・§5 pipeline・§6 pack・§7 T1・§8 gates・§10 制作フロー・§11 タスク表）
3. **ゴール仕様: `docs/goal_spec_2026-07-12.md`（v1.0・§1入力設計・§2組み合わせ設計R-IN1〜6・§3数値ゴール=green 630/630・台帳C1〜C16・Phase P1〜P8）**——全実装は「どのCグループ・どのPhaseか」を宣言して行う。進捗実測は `python -m engine.tools.goal_progress`（未分類セル検出=exit 1）
4. 本書（最新の進捗と横展開の手順書）
4. 旧引き継ぎ書 `docs/HANDOFF_engine_m0_2026-07-11.md`（M0 の Task1〜10 の詳細な経緯。歴史資料）

- ブランチ: **`engine-m0-rework`**（master から分岐・未マージ）
- venv: `.venv/bin/python`（Python 3.13・pydantic 2.13・sympy・jinja2 導入済）
- **鉄則**: subagent の完了報告は鵜呑みにせず **git 実体 + 個別テスト実走 + mypy --strict** で検証してから完了マーク・コミットする（過去に未実装なのに「完了」と報告された事例・私のテストが通る seed だけ選んで偽陽性を隠した事例あり）。

---

## 1. 現状サマリ（2026-07-12 更新・最新コミット `73ba361`（#19）・作業ツリー clean）

**M0 金の縦串は実装完了**（要件 §10 M0 DoD = Q1〜Q7 + F-1/2/3/5/9 を充足）。続けて **横展開を19セル分**進めた（#1〜#3 前々セッション、#4〜#11 前セッション群、#12〜#18 前セッション、#19 本セッション）。**capability を2本新設し償却を実データで実証**: #8 graph_table「かく」（GraphAnswer 経路）、#16 **knowledge form（ChoiceAnswer 経路）**。intersection solver / 「かく」/ knowledge を**新solverゼロ or 小規則だけで再利用**。
- **#11〜#15 で連立方程式クラスタ（g2_l11〜l15）完成**（同 solver `intersection_of_two_lines` が連立5+交点2セルを支える）。
- **#16〜#19 で knowledge form を4単元に展開**（g2_l21/l23/l10/l19）。#16 が初セル（capability 新設）、#17〜#19 が spec+小規則だけで作れる償却の実証。**#18 で g2_l10 verify（○×）解消**・**#19 で g2_l19 Lv2「与式が1次関数か判別」を verify 型で被覆**（式の種類で答えが変わる・微分判定＝V1相当）。

> ★**全セル フルスイート緑でコミット済み・作業ツリー clean**: 旧#11 FS未走は前セッション冒頭で **3709 passed** 確認し解消。以降 #12〜#19 は各々フルスイート緑を確認してコミット（#12=4117 / #13=4525 / #14=4933 / #15=5137 / #16=5341 / #17=5545 / #18=5749 / #19=5953 passed）。**再開時は未コミットの積み残し無し**——次の新セルからそのまま §3 プレイブックで始めてよい。

> ★**再開時の最初のコマンド**（実状態の確認）:
> ```bash
> git branch --show-current            # engine-m0-rework
> git log --oneline -6                 # 最新 73ba361（#19 l19 knowledge）＋引き継ぎ書更新
> git status --porcelain               # 空（clean）のはず
> .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式OK・exit 0（約1分）
> ```
> フルスイート（**約25分**・property テスト増で伸長。`-q` は tty 無しだと末尾までバッファ＝途中出力は空・プロセス生存で判断）は変更を積んでから走らせればよい（現時点の 73ba361 は #19 コミット時に 5953 passed 確認済み）。

- テスト全体 **5953 passed**（#19 時点・フルスイート緑）・`mypy --strict` クリーン・`ruff`（engine/ ソース）クリーン。
- **capabilities = 29 セル**（`spec check` 済みで generate 可能なセル。level 単位）:

| unit | form | levels | 内容 | recipe |
|---|---|---|---|---|
| g2_l24 | find_value | 1, 3 | 傾き+1点→式 / 平行条件→式 | linear_from_slope_point / linear_from_parallel_condition |
| g2_l25 | find_value | 2, 3 | 2点→式（Lv3=連立・分数傾き） | linear_from_two_points |
| g2_l25 | graph_table | 2 | グラフから2格子点を読む（図つき） | graph_read_two_points |
| g2_l20 | find_value | 1 | 変化の割合（2点→傾き） | rate_of_change |
| g2_l27 | find_value | 2, 3 | 2直線の交点（Lv2代入/Lv3消去） | intersection |
| g2_l23 | find_value | 2, 3 | 変域（Lv2順方向/Lv3逆算） | y_range_from_domain / expr_from_range |
| g2_l21 | graph_table | 1 | グラフから傾き・切片を読む（図つき・#4） | read_slope_intercept |
| g2_l26 | calculation | 1 | ax+by=c を y=… に変形（最初の calc・#5） | solve_equation_for_y |
| g2_l19 | calculation | 1 | y=ax+b に x を代入し y の値（最初の asked=value・#6） | evaluate_linear |
| g2_l22 | calculation | 1 | グラフが通る点を代入で求める（asked=coordinate・#7） | point_on_line |
| g2_l22 | graph_table | 1 | y=ax+b のグラフをかく（初の「かく」＝GraphAnswer・#8） | draw_linear |
| g2_l26 | graph_table | 1 | ax+by=c を変形してかく（#5＋#8 合成・新数学ゼロ・#9） | draw_linear_from_equation |
| g2_l27 | graph_table | 2 | 2直線をかき交点を読む（intersection 再利用・#10） | read_intersection_from_graph |
| g2_l11 | calculation | 1 | 連立を加減法で解く（intersection 再利用・連立クラスタ初・#11） | solve_system_elimination |
| g2_l13 | calculation | 1, 2 | 連立を代入法で解く（Lv1そのまま/Lv2変形して代入・#12） | solve_system_substitution |
| g2_l12 | calculation | 2, 3 | 加減法で係数をそろえる（Lv2片方倍/Lv3両式倍・#13） | solve_system_elim_scaled |
| g2_l14 | calculation | 2, 3 | いろいろな連立（Lv2かっこ展開/Lv3分数払い・#14） | solve_system_preprocessed |
| g2_l15 | calculation | 2 | A=B=C 形を連立に組み替えて解く（#15・連立クラスタ完了） | solve_system_abc |
| g2_l21 | knowledge | 1 | グラフの向き判別（傾きの符号→右上/右下・**knowledge初**・#16） | knowledge_slope_direction |
| g2_l23 | knowledge | 1 | 変域の端点の包含判別（≦/≧→含む・#17・knowledge償却実証） | knowledge_range_endpoint |
| g2_l10 | knowledge | 2 | 連立の解の判定（組が解か○×・#18・l10 verify解消・Q1=V1相当） | knowledge_verify_solution |
| g2_l19 | knowledge | 2 | 与式が1次関数か判別（式の種類で答え変化・verify・#19・微分判定Q1=V1相当） | knowledge_classify_linear |

- M0 縦串 = g2_l25 + 戻り先 g2_l24（find_value）+ g2_l25 graph_table + remedial。**横展開分** = l20 / l27(fv) / l23(fv) / l21(graph) / l26(calc) / l19 / l22(calc) / l22(graph) / l26(graph) / l27(graph) / **連立クラスタ l11/l13/l12/l14/l15(calc)** / **knowledge l21/l23**。
- **償却の実証（当初目的の達成確認）**:
  - (#7) solver `evaluate_linear_at_x` を素関数化し g2_l19/g2_l22(calc) で共有。
  - (#8) **graph「かく」capability 新設**（GraphAnswer 生成経路・初）。
  - (#9) g2_l26.graph は `_solve_equation_for_y_core`(#5)＋`_draw_linear_features_core`(#8) の**合成 solver だけ**（新数学ゼロ）で作成。
  - (#10) g2_l27.graph は `intersection_of_two_lines`(#2 の solver) を再利用（新 solver ゼロ）。
  - (#11) g2_l11.calc（連立・加減法）も `intersection_of_two_lines` を再利用＝**同 solver が4セル**（l27fv/l27graph/l11、＋派生）を支える。連立クラスタ（l11〜l15の9レベル）は全て同 solver で作れる見込み（§下の調査）。
- `git log --oneline`: b5c4ec5(#11 l11.calc・**FS未走**) / 07af176(#10 l27.graph) / 44aa938 / 04d3813(#9 l26.graph) / 4364abf(#8 かくcapability) / d680c3d(#7)。

### 再開時の最初のコマンド（実状態の確認）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework
git log --oneline -6                 # 最新 b5c4ec5（#11 l11.calc・★FS未走でコミット）
git status --porcelain               # 空（クリーン）のはず。preview_*.html / problem_*.svg は生成物なので無視/削除可
# 縦串 + 横展開 + eval が緑であることを再確認:
.venv/bin/python -m pytest engine_tests/contract/ engine_tests/golden/ engine_tests/eval/ -o addopts="" -p no:cacheprovider -q
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100   # 一式 OK・exit 0
```

---

## 2. アーキテクチャ要点（詳細は実装設計 §3〜§8）

```
engine/
  core/            科目非依存カーネル（packs/curriculum を import しない）
    contracts.py   pydantic 契約（GenerateRequest/MR/Problem/Unsupported/CellContext/...）
    pipeline.py    generate()/resolve()/capabilities()/Supplier
    rng.py         derive_rng（唯一の乱数源）+ ドメイン記法 v1（draw/draw_many）
    registry.py    recipe/solver/checker/template/frame/gate/visual/hint の登録機構
    signature.py   fingerprint(fp)/dup_key
    spec/          FamilySpec ローダ + spec_lint(R1-R8)
    render/t1_template.py  T1 決定論テンプレ（Jinja2 sandbox）
    verify/quality_gates.py  9ゲート（G-SIG/G-FP/G-Q1/G-Q2/G-Q7[+Q7r]/G-Q5t/G-GND/G-STY/G-Q5v）
  packs/math/      solvers/ recipes/ checkers/ templates/ frames.py visuals/graph.py
  curriculum/math/ units.generated.yaml（自動生成・手編集禁止）/ concepts.yaml / error_causes.yaml / families/*.yaml
  eval/            coverage_scan / dup_rate / level_sep / retry_stats + 統合 `python -m engine.eval`
  tools/           spec_cli.py（preview/check/approve）/ generate.py（1問生成CLI）
engine_tests/      unit/ golden/ contract/ eval/
```

- **依存規律**: `core` は何も import しない。`packs/math` → core のみ。`eval`/`tools` → 両方可。
- **単一入口** `engine.bootstrap.bootstrap()`: 数学パック登録 + `install_quality_gates()`。generate 前に1回呼ぶ（べき等）。
- **登録は import 副作用**: `packs/math/{solvers,recipes,checkers,templates}/linear.py` に `@register_*` で足すと、各 `__init__.py` が import するだけで登録される（**新ファイル不要・既存 linear.py に追記**）。
- **FamilySpec（YAML）に書けるのは選択と参照と定数のみ**。ロジックは pack の recipe/solver に置き名前参照（H1）。
- **DoD**（§10・機械判定）: `spec check`(lint+smoke+dup_rate) → `spec approve`(golden 固定) → `eval`(coverage/dup_rate/level_sep/retry_stats)。**eval は capabilities を走査するのでセルを増やすと自動被覆**（eval 側の変更不要）。

---

## 3. 横展開のプレイブック（★セルを1つ増やす手順・実証済み）

新セル = **部品（solver/recipe/checker/template）＋ spec ＋ concept の追加だけ**。frame/ゲート/eval は原則不変。
以下は g2_l20/l27/l23 で実際に踏んだ手順。**1セルずつ DoD 緑にしてコミット**する（まとめて雑にやらない＝要件 §10「1つの完全な見本」）。

### 手順
1. **題材の正を読む**: `units.generated.yaml` の当該 unit の `forms.<form>.levels.<lv>.{desc, example, market_ref}` が**忠実な正**。これを `source_desc` に転記（R8）。**レベル間は必ず構造（steps の op 列 or asked）を変える**——数値ジッターだけの違いは禁止（P-1 回帰。level_sep が fp 相異で機械検証する）。
2. **solver 追加**（`packs/math/solvers/linear.py`・`@register_solver("math.<name>")`）: 問題パラメータだけから答えと steps を導く独立再計算（recipe の構成値を見ない）。`Solution(answer, steps)` を返す。**既存 solver を再利用できるなら新規不要**（例: 逆算セルは 2点→式ソルバを再利用）。
3. **recipe 追加**（`packs/math/recipes/linear.py`・`@register_recipe("math.<name>", provides_concepts=[...])`）: answer-first（綺麗な答えを先に決め逆算）。draw/draw_many 以外で乱数・ドメインを触らない。構成直後に solver で再計算し一致を assert（recipe 内 double-solve）。MR を返す。
4. **checker 追加**（`packs/math/checkers/linear.py`・`@register_checker("math.<recipe>.double_solve")`）: MR.params から独立に solver を呼び `Solution` を返す（G-Q1 が呼ぶ）。**名前は必ず `<recipe名>.double_solve`**。
5. **template 追加**（`packs/math/templates/linear.py`）: Jinja2 文字列を定義し `_register_all()` に `register_template(name, SRC)` を1行足す。参照できるのは `given`/`context_slots`/`sub_questions[].{label,asked,narrations}` のみ（answer/params は構文的に触れない＝Q5 構造防止）。
6. **frame 語彙**（必要時のみ・`packs/math/frames.py`）: given/asked のキーが frame 語彙に無ければ追加（Open-Closed の frame 拡張）。追加したら `engine_tests/unit/test_frames.py` の該当語彙 assert も更新。
7. **concept 追加**（`curriculum/math/concepts.yaml`）: `concept_tags` に使う概念 ID を `{id,label,unit}` で追加。`unit` は `units.generated.yaml` に実在するもの。
8. **spec 作成**（`curriculum/math/families/<unit>.<form>.yaml`・新規1ファイル）: levels 毎に signature（family 内一意）/recipe/params(ドメイン記法)/given/asked/visual/text/hints/concept_tags/cause_tags。`cause_tags: []` は可（G-Q7 は concept_tags のみ非空必須。remedial 不要なら空でよい）。
9. **DoD**:
   ```bash
   find engine -name __pycache__ -type d -exec rm -rf {} +   # 並行編集後の stale 対策
   .venv/bin/python -m engine.tools.generate <unit> <form> <lv> --seed 4   # 目視
   .venv/bin/python -m engine.tools.spec_cli check math.<unit>.<form>       # lint0/smoke0/dup_rate
   # 連続100+seed で偽陽性（G-Q5t 等）が隠れていないか広域確認（cherry-pick 隠蔽防止）:
   .venv/bin/python -c "from engine.bootstrap import bootstrap; from engine.core.contracts import GenerateRequest,Problem; from engine.core.pipeline import generate; bootstrap();
   print([s for s in range(1,121) if not isinstance(generate(GenerateRequest(subject='math',unit='<unit>',form='<form>',level=<lv>,seed=s)),Problem)])"
   .venv/bin/python -m engine.tools.spec_cli approve math.<unit>.<form>      # golden 固定（seed1-3）
   .venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100                 # 新セルが自動被覆・全OK
   ```
10. **property テスト**（`engine_tests/unit/test_recipes.py`）: construct 1本 + double-solve 200 seed（既存セルに倣う）。
11. **検証してコミット**: 変更ファイルだけ全部 → 個別テスト緑 → mypy strict → ruff（engine/）→ **フルスイート `pytest engine_tests/`（約8分）緑** → commit（1セル1コミット）。

---

## 4. 検証コマンドまとめ
```bash
# テスト（recipe property が重く全体で約8分。変更箇所は個別ファイルで先に確認）
.venv/bin/python -m pytest engine_tests/ -o addopts="" -p no:cacheprovider -q
# 型・lint
.venv/bin/python -m mypy --strict engine/packs/ engine/core/ engine/eval/
.venv/bin/ruff check engine/                    # engine/ ソースは常にクリーンに保つ
# eval 一式（CI 相当・JSON は --json）
.venv/bin/python -m engine.eval --seeds 5 --dup-seeds 100
# 手元で1問試す / ブラウザで一覧
.venv/bin/python -m engine.tools.generate g2_l27 find_value 2
.venv/bin/python -m engine.tools.spec_cli preview math.g2_l23.find_value --seeds 5 --out /tmp/p.html && open /tmp/p.html
```
既知の未クリーン: `engine_tests/unit/test_gates.py` 等に **既存の** ruff 未使用 import nit が数件（前セッションが engine_tests に ruff をかけていなかった痕跡）。engine/ ソースは clean。CI で engine_tests も lint するなら別途一掃。

---

## 5. 既知の落とし穴（必読）
1. **G-Q5t 助数詞の偽陽性**: 答えが数値/座標のセルで、テンプレ/narration の「2直線」「2式」等の数字が答えの値と衝突して漏洩誤検出になる。助数詞除外リスト（`quality_gates.py` の `_COUNTER_EXPR_RE`）は つ/点/個/本/次… を持つが **「直線」「式」は無い**。→ 文言を「2**つの**直線」等（つ は除外対象）に言い換える（**core は触らない**）。必ず連続100+ seed で広域確認。
2. **レベルは構造を変える**: Lv 間で signature と fp（steps op 列 or asked or 小問数）が必ず相異すること。数値域だけ変える偽レベルは level_sep が落とす（H2/Q3・過去最大級の失敗 P-1 の再発防止）。
3. **RNG 消費順は契約**: recipe 内の draw 順を変えると golden が壊れる（正しい変更なら `spec approve` で再承認）。テンプレ版数アップも同様。
4. **並行編集後は `__pycache__` 一掃**: stale で `has_visual=False` 等の一時的誤検出が出る。
5. **subagent 運用**: `general-purpose` は Agent ツールを持ち「実装せよ」で委譲連鎖に陥り何も書かないことがある。中規模の設計判断はオーケストレータ主導、投げるなら「委譲禁止・自分で Read/Write/Bash」を明記し **完了後 git 実体 + 個別テスト + mypy で検証**。
6. **答えの形が新しいとき**（範囲・座標など）: SymbolicAnswer.srepr は正規形（sympy srepr）、display は表記（例 `-1 ≦ y ≦ 5`）。checker が同じ solver で再計算して一致を担保。
7. **frame 語彙を足したら** `test_frames.py` の語彙 assert も更新（`-k` フィルタ実行だと deselect されて漏れるので注意）。
8. **`spec check` の dup_rate は当てにならない（★#5 で発覚）**: `spec_cli` の dup_rate は `problem_ref`（seed 込みハッシュ）ベースの簡易測定で、seed が違えば別ハッシュになるため **常に 0.0**（`spec_cli.py:260` にコメント明記）。**本物の重複率ゲートは `eval/dup_rate.py`**（`dup_key`=signature+正規化 params・閾値 0.20・`--dup-seeds 100`）。組合せ数が小さいセル（特に calculation で域が狭いと数百通り以下になりやすい）は check が緑でも eval で落ちる。**新セルは必ず下記スニペットで 100seed の実 dup_rate を測ってから approve する**（#5 で 132通り→実 0.29 超過を検出し域を 600通りに拡張した）。
   ```python
   from engine.bootstrap import bootstrap; from engine.core.spec.loader import load_family_dir
   from engine.core.contracts import CellContext, Coordinate, GenerateOptions
   from engine.core.curriculum import load_curriculum; from engine.core.registry import REGISTRY
   from engine.core.rng import derive_rng; from engine.core.signature import dup_key; from pathlib import Path
   bootstrap(); fams=load_family_dir(Path('engine/curriculum/math/families'))
   fam='math.<unit>.<form>'; sf=fams[fam]; sl=sf.levels['<lv>']; cur=load_curriculum(); unit=fam.split('.')[1]
   ctx=lambda: CellContext(subject='math',family=fam,form=sf.form,unit=unit,level=int('<lv>'),purpose='base',frame=REGISTRY.frame(sf.form),spec_family=sf,spec_level=sl,curriculum_view=cur.curriculum_view(unit),requested=Coordinate(subject='math',unit=unit,form=sf.form,level=int('<lv>')),options=GenerateOptions())
   k=[dup_key(REGISTRY.recipe(sl.recipe)(ctx(),derive_rng(fam,int('<lv>'),'base',s))) for s in range(1,101)]
   print('dup_rate=',(100-len(set(k)))/100)  # 0.20 以下であること
   ```
9. **calculation セルの数値答えは G-Q5t 高リスク**（#6）: 答えが1つの数値だと `_COUNTER_EXPR_RE` の助数詞衝突が起きやすい。ただし「1次関数」の "1次" は 次 が除外対象なので通る。narration は数字を含めない文言にし、必ず 100+ seed 広域で **拒否 seed 0** を確認（数値答えセルは偽陽性が seed 依存で隠れる）。

---

## 6. 残クラスタの見通し（g2 一次関数 l19〜l30 ほか）
`units.generated.yaml` に各セルの desc/example があり、それが忠実の正。セル型ごとに必要な土台が違う:
- **find_value / graph_table 系**（グラフ読み l21/l26、ダイヤ交点 l30、動点面積 l29 等）: recipe 追加＋一部 frame 語彙で **T1 のまま作れる**（本書 §3 の手順）。graph_table は図（`visuals/graph.py`）を使い、幾何的リーク規則（asked と両立しない描画要素の禁止・§6.4）に注意。
- **knowledge 系**: **fact テーブル**（`facts.yaml`・§6.2 V2）＋ knowledge 用 recipe が要る（未整備）。
- **word_problem 系**: **T3 翻訳（LLM・Gemini）＝M1 本体**が要る（T1 では作らない）。
- **calculation 系**: 各計算 recipe 群（式変形・連立解法など）が要る。
- **図形/確率/データの単元**（l31〜l57）: 一次関数クラスタの外。幾何 recipe・fact table 等が要る。

**faithful なレベル分けが不確かな単元は、`source_desc` に設計モデルを明記し preview 検収（人間・Q4）に委ねる**——これは設計が sanction した手順（§10）。推測で量産しない。

### 次の一手 ― ★重要な分岐（純T1セルは出し切った）
**済（本セッション #4〜#7）**: g2_l21 graph_table[1]読む / g2_l26 calc[1] ax+by=c→y= / g2_l19 calc[1] 代入→値 / g2_l22 calc[1] 代入→座標。

**一次関数クラスタで「部品ほぼ流用＋spec だけ」で作れる純T1セルは、ここでほぼ枯れた**（残りの unit×form×level を全走査して確認済み）。残りは3つとも**新しい capability の実装**が要る＝これまでの「1セル追加」とは作業の質が変わる。どれを次に投資するかは方針判断:

1. **graph_table「かく」capability（draw_graph）** ― ★T1 で最大の解放。l22/l23/l26/l27/l28/l29 の作図セルを一気に開ける。要実装: `GraphAnswer(features+solution_svg_ref)` の answer 経路、特徴点 double-solve（§6.2 V1'）、解答図の決定論描画、問題図＝空グリッド。**LLM は不要（T1のまま）**なので「T1優先」方針と両立。現 graph_table は全て「読む」→SymbolicAnswer なので、これが初の「かく」。gate 枠組みが GraphAnswer を通すか要確認。→ **推奨の第一候補**。
2. **連立方程式クラスタ（g2_l10〜l15）へ intersection 資産を横展開** ― `intersection_of_two_lines`（＝2×2連立の解法）は加減法/代入法そのもの。別クラスタだが償却効果は最大級（1 solver が多数の calc セルを支える）。「一次関数クラスタ」の指示からは外れるので要相談。
3. **knowledge capability（fact テーブル）** ― l19/l21/l26 等。`facts.yaml`＋ChoiceAnswer frame＋fact 照合ゲート（§6.2 V2）が未整備。T1 で解説まで出せるが機構が要る。

**当面 T1 で作れないもの**: word_problem/利用（l28〜l30・T3 翻訳＝M1本体）。g2_l30 find_value[2] は交点計算は `intersection` 流用可だが、忠実な文面はシナリオ翻訳が要り word_problem 側（推測量産の禁止）。

※ 上記1〜3 はいずれも旧引き継ぎ書の「M1 寄り」に該当。**次セッションは「セルを1つ足す」より先に、どの capability を1本作るかを決めてから着手すること**（capability を1本作れば、その形式のセルは再び spec だけで量産に戻れる＝償却の本丸）。

---

## 7. M1 送り（横展開と別軸の本体作業）
FastAPI ラッパ / T2(磨き)・T3(翻訳) / audit_runner(LLM 監査 V3) / cost_meter / dashboard HTML / プール(Supplier 差し込み・授業内≤3秒) / 採点フィクスチャ(D-2 スキーマ合意) / variant・avoid(supply_exhausted 機構)。

## 7.5 graph_table「かく」capability（★#8 で実装完了・commit 4364abf）
下記は当初の実装計画。**#8 で計画どおり実装済み**（solver `math.draw_linear_features`／recipe `math.draw_linear`／`visuals/graph.py` の `render_grid_svg(params,*,draw_line)`＋`render_line_solution_svg`／G-Q5t 符号対称化）。★の設計判断は「(a) `_build_given_whitelist` を両符号化」を採用して確定・実装済み。次の作図セルはこの構造を踏襲する（下の「次の作図セル」参照）。

feasibility 精査（当時）: **answer 経路とゲートは既に GraphAnswer 対応済み**（`contracts.GraphAnswer(features, solution_svg_ref)`／`AnswerPayload` union に kind="graph"／`quality_gates._answers_match` は features の srepr 集合一致で G-Q1 を判定＝§6.2 V1' が実装済／`_answer_values` も graph 対応）。**GraphAnswer を生成する recipe/solver と解答図の描画だけが未実装**。最初のセルは g2_l22.graph_table[1]「y=ax+b のグラフをかく」（例「y=2x−1 のグラフをかけ」）が最小。

実装手順（パイプライン改修は不要と判明）:
1. `visuals/graph.py` を軽く refactor: 描画本体を `render_grid_svg(a,b,pts,*,draw_line: bool)` に切出し、`render_linear_graph(mr,ctx)` は `draw_line = ("line" in [e.kind for e in visual_plan.elements])` で呼ぶ（**既存 read セルは line 要素を宣言済 → draw_line=True で不変＝後方互換**）。作図セルの**問題図は空グリッド**（elements=[grid,axis]・line なし→ draw_line=False）。
2. solver `math.draw_linear_features(a,b)` → `Solution(answer=GraphAnswer(features=[Feature(kind="slope",...), Feature(kind="point", (0,b) の切片)], solution_svg_ref=""))`。**solver は SVG を描かない**（features のみ）。
3. recipe `math.draw_linear`: a,b,pts を選び solver で features 構成→一致 assert。**解答図は visual 層の純ヘルパ `render_grid_svg(a,b,pts,draw_line=True)` を recipe から呼んで `GraphAnswer.solution_svg_ref` に格納**（問題図＝空グリッドは通常の visual 段が visual_plan から描く）。MR.sub_question.answer=GraphAnswer。
4. checker `math.draw_linear.double_solve` → solver。`_answers_match` は features 集合のみ比較（solution_svg_ref は無視）なので checker 側 svg は "" でよい。
5. template「1次関数 {{ given.expression }} のグラフを、座標平面にかけ。」／concept `linear_function.draw_graph`（unit g2_l22）／spec `g2_l22.graph_table.yaml`（asked=[draw_graph]・visual=required・**問題図の grid 範囲は固定推奨**＝答えを示唆しない方眼紙）。frame は draw_graph 済（vocab 済・forbidden 空でよい：問題図が空グリッドなので幾何リークなし）。

**★実装前に確定すべき設計判断（§0・core を触る戦略事項）**: 作図セルは **答え(傾き・切片)＝given の式係数** なので、`_gate_q5t` の given whitelist と feature トークンの**符号整合**が問題になる。実測（本セッション）: given `y = 2x - 1` → `extract_numbers` は `['2','1']`（符号なし）で whitelist=`{2,1}`。一方 切片 feature `-1` は `_to_fraction('-1')=-1`→ norm_key `'-1'` が whitelist に無く、`contains_number(scan_text,'-1')` が本文の "- 1" に一致 → **負の切片で G-Q5t が漏洩誤検出→ Unsupported になる**（§5-#9 の具体化。文言では回避不可）。要決定: (a) `_build_given_whitelist` を式について符号込みで数値抽出するよう core を原則的に改良（推奨・全 draw セルに効く）、または (b) draw セルは feature 数値を whitelist に明示合流させる仕組み。**どちらも core/verify に触れるので設計を先に確定してから実装**。決めたら必ず「負の切片を含む連続100+seed」で拒否0を確認（数値/座標答えの偽陽性隠蔽防止）。→ **(a) を採用・実装済み**（両符号を whitelist に追加。負係数 200seed で拒否0 を確認）。

### 次の作図セル
- **g2_l26 graph_table[1]** = #9 実装済み／**g2_l27 graph_table[2]**（2直線＋交点読み）= #10 実装済み（空の方眼＋ `intersection_of_two_lines` 再利用。当初懸念の "grid_with_both_lines 禁止" は問題図を空の方眼にしたため不発＝規則変更不要だった）。
- 残る作図セルは描画拡張が要る: **g2_l23 graph_table[2]**（端点の開閉つき線分＝segment 描画と端点マーカーの追加）／**g2_l28/l29 graph**（対応表→折れ線・動点面積＝word_problem/データ表寄り・M1）。

## 7.6 連立方程式クラスタ（g2_l11〜l15）＝ intersection 再利用の最大の償却先（#11〜#15・**完成**）
**結論: g2_l11〜l15 の calculation は全て既存 `intersection_of_two_lines`（method=substitute/elimination）で答え(x,y)を出せた＝新 solver ゼロ**。前処理を伴う l14／組み替えの l15 も「整理後の整数系」に対して同 solver を再利用。**クラスタは #15 で完成**（残は l10 のみ・下記）:
- **#11 g2_l11** 加減法（係数の絶対値が等しい・単一Lv）`solve_system_elimination`
- **#12 g2_l13** 代入法（Lv1 そのまま/Lv2 変形して代入）`solve_system_substitution`
- **#13 g2_l12** 加減法・係数そろえ（Lv2 片方倍/Lv3 両式倍）`solve_system_elim_scaled`
- **#14 g2_l14** いろいろな連立（Lv2 かっこ展開/Lv3 分数払い）`solve_system_preprocessed`
- **#15 g2_l15** A=B=C 形（Lv2 のみ・A=C,B=C に組み替え）`solve_system_abc`
- **同 solver `intersection_of_two_lines` が連立5セル＋交点2セル（l27 fv/graph）を支える＝最大の償却ハブ**。
- 実装方針（踏襲）: 「解を先に決め→係数を構成→ intersection solver で答え検算→ steps は各解法の代数手順を recipe で別建て」。given は equation_a/equation_b（複数式）または equation（A=B=C の1本）。
- **★level_sep（P-1 回帰防止）**: multi-level 単元は **Lv 間で steps の op 列を必ず変える**（数値域だけの差は不可）。実績: l13={substitute_expr,…} vs {isolate_variable,…}／l12={scale_one_equation,…} vs {scale_both_equations,…}／l14={expand_parentheses,…} vs {clear_denominators,…}。いずれも先頭 op を変えて fp を相異にした。
- **★faithfulness（本セッションで学んだ落とし穴）**: 「Lv の骨格（op 列）」だけでなく「その Lv が要求する操作が本当に必要か」も要確認。l12 で当初、x 係数が偶然そろって"倍が不要"になり **Lv2/Lv3 が l11 相当（倍不要）に退化**する題材が混じった。→ 係数を互いに素な大きさに固定して「そろえる倍が真に必要」な構成にした（recipe 内コメント参照）。**新 calc セルは「その Lv でしか解けない」かを生成物 5〜10 個で目視**すること。
- **★G-Q5t 偽陽性（本セッションで再発）**: l13 の isolate narration に書いた「係数が **1** の式」の "1" が答え座標の値 1 と衝突して漏洩誤検出→ Unsupported。**narration/ヒントには数字を一切書かない**（#9 の再確認。§5-#9）。修正後 250seed 広域で拒否0 を確認。
- **g2_l10 verify（○×）は #18 で解消済み**（下 §7.7）: knowledge/ChoiceAnswer 経路が開いたため、代入判定 solver `verify_system_solution` で g2_l10.knowledge Lv2 として実現。当初「新 answer 型が要る小 capability」と見ていたが、#16 の knowledge 資産で spec+小規則だけで作れた。**連立クラスタは calc(l11〜l15)＋verify(l10.knowledge) まで被覆**。
- 残 capability（連立以外）: word_problem=T3（M1）。**knowledge は #16 で開通済み**（下 §7.7）。

## 7.7 knowledge form capability（#16 開通・#17/#18/#19 で償却実証・4単元被覆）
**knowledge form（ChoiceAnswer 単一選択）を新設**。要件のフォーム被覆で唯一ゼロだった大穴（g2_l10/l19/l20/l21/l23/l26/l27 の7単元に定義）を開けた。**core/frame/ゲートの改修はゼロ**——既存資産だけで通った。**実績4セル**: #16 g2_l21（向き判別・初セル）／#17 g2_l23（端点包含・償却実証）／#18 g2_l10 Lv2（連立の解の判定・verify・Q1=V1相当の代入検証）／**#19 g2_l19 Lv2（与式が1次関数か判別・verify・Q1=微分判定で V1相当）**。#18/#19 は「答えが真に変化する verify 型」で、l26/l27 系の"常に同じ答え"の弱点を回避する好例。
- **#19 の要点（微分判定＝V1相当の knowledge）**: solver `math.classify_linear_function(rhs)` は式を x で微分し「導関数が x を含まない非ゼロ定数か」で1次関数を判定＝規則(V2)でなく**恒真な数学判定(V1相当)**。recipe `math.knowledge_classify_linear` が category(0=1次/1=定数/2=2次/3=反比例)を引き式を構成、solver は式そのものだけ見て double-solve。式の種類で correct が「1次関数である/ではない」に変わる（category 一様＝「である」約25%）。**"1次関数である" の "1" は G-Q5t を素通り**（本文の "1次" は `_COUNTER_EXPR_RE` の「次」で除去・given 式係数は whitelist 両符号・250seed 拒否0 実測）。
- **★#19 で学んだ dup_rate の落とし穴（knowledge の category 型）**: 「答えの種類＝category」型は、狭い category（#19 の 定数 y=c・反比例 y=k/x は各12通り＝1係数のみ）が 100seed 中で衝突し **dup_rate が跳ねる（実測 0.36 > 0.20）**。1次/2次は a×b で広い(228通り)ので薄まらない。→ **狭い category の係数域を専用に広げる**（#19 は c,k を `int_range:[-40,40]` の専用 domain に＝定数値/反比例定数は線形性判定に無関係な surface param）で **0.36→0.07**。「答えに無関係な係数を広い専用域で引く」が §7.7 の surface param 定石の具体形。**pack ヘルパ `_fmt_expr` に `**2`→`²` 上付き変換を追加**（2次式提示のため・既存1次式に冪は無く golden 不変）。
- **既存資産の再利用**: `knowledge` frame（frames.py・given=statement/term_context, asked=term/true_false/choice, visual 禁止）／`ChoiceAnswer` 契約（correct/distractors/fact_id）／`_answers_match` の choice 分岐（correct+fact_id 照合）は**すべて実装済みだった**。#16 が初めてこの経路を生成で通した。
- **★漏洩ゲートは素通り（重要）**: `_gate_q5t` は答え由来の**数値トークンだけ**を検査する（`_answer_values(choice)=[correct]` → `extract_numbers` で数字なし → 検査対象ゼロ）。よって**テキストの選択肢答え（「右上がり」「ふくまれる」等）は G-Q5t 偽陽性を起こさない**。選択肢の文言はテンプレ本文に固定で並記してよい（両方見せるのは漏洩でない）。
- **★F-3 無限性の定石（knowledge の勘所）**: knowledge の答えは2値/少数で **params 変化が乏しく dup_rate が上がりやすい**。→ **答えに無関係な surface パラメータ**（#16=切片 b・#17=関数 y=ax+b と端点 n）を式の見かけとして混ぜ、dup_key(params) を広く分散させる（#16=0.12 / #17=0.0）。「答えは a の符号だけで決まるが、b も引いて式の見かけを変える」がパターン。
- **Q1（double-solve）は V2（規則ベース）**: solver は問題パラメータから**規則**で答えを再判定（#16=傾きの符号→向き／#17=不等号の等号→包含）。fact_id は根拠規則の識別子（`lf.slope_sign_to_direction` 等）。**現状 fact_id の実在検証（facts.yaml 照合）は無い**（_answers_match は recipe/checker 間の一致のみ検査）＝設計 §6.2 の facts.yaml は未整備。当面は規則ベースで faithful に作れる（用語想起系のように fact 表が要る種別は facts.yaml 整備後）。**この差は spec の source_desc に設計モデルとして明記し preview 検収に委ねる**（§6 の sanction 手順）。
- **実装パターン（次の knowledge セルはこれをコピー）**: solver `math.<rule>`（規則→ChoiceAnswer 返す・純関数）＋ recipe `math.knowledge_<x>`（surface param を引いて statement 構成・solver で double-solve）＋ checker `.double_solve`（params から solver 再判定）＋ template（`given.statement` を出し選択肢は本文固定）＋ concept（unit 実在）＋ spec（given=[statement], asked=[choice], visual=none）。#16/#17 の `knowledge_*` をそのまま雛形に。
- **次の knowledge セル候補（spec+小規則で作れる）**: ~~g2_l19~~（#19 で被覆済）／g2_l26 knowledge（ax+by=c の解の集合は直線か）／g2_l27 knowledge（連立の解＝2直線の交点）。**ただし l26/l27 は「答えが常に固定」型**（"直線"/"交点"）で verify にならず F-3 も surface のみ頼み＝弱点型。作るなら妨害選択肢（放物線・接点 等）で単一選択化し surface param で無限性を出すが、#18/#19 のような「答えが変わる」型が枯れたら価値は下がる。用語「何というか」系の自由記述は ChoiceAnswer 化（正解語＋妨害語）で対応。g2_l19 は Lv1（a/b の用語想起）も未着手＝2レベル化するなら Lv2(判別) と op 列を変えて level_sep を満たすこと。

### 次の一手（#20 以降）——★ゴール仕様 v1.0（2026-07-12）で確定
**`docs/goal_spec_2026-07-12.md` §3.6 の Phase 順に従う**: 次は **P1（C5 g2一次関数の残16セル → C2 g2数と式の残23セル）**。規律: (1) C グループ単位で T1 を 100% にしてから次へ（薄く広くの宙ぶらりん禁止）、(2) 事業優先（知人塾範囲=D-4）判明時は該当グループ前倒しのみ許す。進捗は `python -m engine.tools.goal_progress` で実測（現在 29/630=4.6%）。
（参考・旧候補の評価）残 knowledge（l26/l27/l19Lv1）は「答え固定」型が主で verify の妙味は薄い（#18/#19 で verify 型は概ね出し切った）——P1 の中で C5 の一部として埋める。
2. **g2_l23 graph_table[2]**（作図の残り）＝端点の開閉つき線分（segment 描画＋端点マーカー）。graph「かく」capability の延長（visuals/graph.py 拡張）。純 T1 で残る作図セル。
3. **別の calc/find_value クラスタへ横展開**（一次方程式・比例反比例・式の計算 等）＝既存 solver で作れる純 T1 セルを他単元で探す。
4. **word_problem（T3・LLM）着手＝M1 本体**（利用 l16/l17/l18/l28〜l30）。T1 では作れない・翻訳ゲート実装が要る。
※ 1 は #16 の knowledge 資産が効いて最低コスト。着手前にどれを投資するか §6 の指針で決める。**M0 の T1 純粋セルは連立・knowledge・作図で相当埋まった**——次は「別クラスタへ横展開して面を広げる」か「M1（T3/remedial/採点結合）へ移る」かの分岐が近い。

### G-Q5t の助数詞除外に追加した語（core・数値答えセルの偽陽性対策の履歴）
`_COUNTER_EXPR_RE` に「次」に加え **「元」**（2元1次方程式の "2元"）を追加済み（#9 で傾き=2 が衝突）。数値/座標/特徴を答えに持つ新セルを作るときは、本文中の「N○○（○○=数える語）」が答え値と衝突しないか**必ず連続200+seed の広域で確認**する（check の smoke=20seed はすり抜ける・#9 で実証）。新たな衝突語が出たら同リストに追記（core を触るが原則的な対処）。

## 8. 既知の設計 smell（M1 で対処候補）
- `graph_read_two_points` の spec `point_domain.y` は実質デッド（答え点 y は a*x+b で決まる）。可読性は domain を絞って確保済みだが、本筋は「2格子点を直接選び傾きは有理数でよい」構成へ（要 recipe 改修 + golden 再承認）。
