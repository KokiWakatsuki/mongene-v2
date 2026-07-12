# 引き継ぎ書: Education OS 問題供給エンジン（2026-07-12）

本書は **M0 金の縦串の完成** と、それに続く **横展開（g2 一次関数クラスタ）の進行中状態** を
別セッション（別アカウント）へ引き継ぐためのもの。アカウント切替（レート制限）のため作成。
**バックグラウンドの subagent はセッション終了で失われる**が、作業ツリーのファイルはディスク上に残る。

---

## 0. まず読む（順に）
1. 要件: `docs/requirements_2026-07-11.html`（v2.1・F/Q/N/D 番号体系）
2. 実装設計: `docs/implementation_design_2026-07-11.md`（v1.1・H1〜H8 の穴・§4契約・§5 pipeline・§6 pack・§7 T1・§8 gates・§10 制作フロー・§11 タスク表）
3. 本書（最新の進捗と横展開の手順書）
4. 旧引き継ぎ書 `docs/HANDOFF_engine_m0_2026-07-11.md`（M0 の Task1〜10 の詳細な経緯。歴史資料）

- ブランチ: **`engine-m0-rework`**（master から分岐・未マージ）
- venv: `.venv/bin/python`（Python 3.13・pydantic 2.13・sympy・jinja2 導入済）
- **鉄則**: subagent の完了報告は鵜呑みにせず **git 実体 + 個別テスト実走 + mypy --strict** で検証してから完了マーク・コミットする（過去に未実装なのに「完了」と報告された事例・私のテストが通る seed だけ選んで偽陽性を隠した事例あり）。

---

## 1. 現状サマリ（2026-07-12・最新コミット `d680c3d`）

**M0 金の縦串は実装完了**（要件 §10 M0 DoD = Q1〜Q7 + F-1/2/3/5/9 を充足）。続けて **横展開を7セル分**進めた（#1〜#3 前セッション、#4〜#7 本セッション）。**一次関数クラスタの「純T1で作れる」find_value/calculation/graph読み取りセルはここで出し切り**（残りは新capability必須＝下記 §6）。

- テスト全体 **2893 passed**・`mypy --strict` クリーン・`ruff`（engine/ ソース）クリーン。
- **capabilities = 14 セル**（`spec check` 済みで generate 可能なセル）:

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

- M0 縦串 = g2_l25 + 戻り先 g2_l24（find_value）+ g2_l25 graph_table + remedial。**横展開分** = g2_l20 / g2_l27 / g2_l23 / g2_l21 / g2_l26 / g2_l19 / g2_l22。
- **償却の前進（#7）**: solver `evaluate_linear_at_x` を素関数 `_evaluate_linear_at_x_core` に切り出し、g2_l19（値）と g2_l22（座標）の**2セルで共有**。1演算が複数セルを支える最初の実例（recipe:セル比が下がり始めた）。
- `git log --oneline -6`: d680c3d(横展開#7 l22) / 352dcd7(引継書) / 916fb3c(#6 l19) / f1fd124(#5 l26) / 5c8c8ab(#4 l21) / 99e4d19(引継書)。

### 再開時の最初のコマンド（実状態の確認）
```bash
cd /Users/koki/workspace/mongene-v2
git branch --show-current            # engine-m0-rework
git log --oneline -6                 # 最新 d680c3d（横展開#7 l22）
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

## 8. 既知の設計 smell（M1 で対処候補）
- `graph_read_two_points` の spec `point_domain.y` は実質デッド（答え点 y は a*x+b で決まる）。可読性は domain を絞って確保済みだが、本筋は「2格子点を直接選び傾きは有理数でよい」構成へ（要 recipe 改修 + golden 再承認）。
