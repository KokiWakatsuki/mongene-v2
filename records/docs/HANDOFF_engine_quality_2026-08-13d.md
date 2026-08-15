# 引き継ぎ（2026-08-13d・8回目のセッション）

前の引き継ぎ書は `docs/HANDOFF_engine_quality_2026-08-13c.md`（7回目）。
**この文書は8回目の分。「エンジンの完成」まで進める回。**

利用制限で止まったら、**この文書だけで別アカウントが継げる**ように書く。

---

## 0. 依頼されていること（利用者の言葉）

> 「エンジンの問題点を修復する → 再度問題を生成する → エンジンを修繕する」のループを回す。
> その後、1. エンジンの完成 → 2. 式と場面の切り分け → 3. 第一段階完了 →
> 4. ディレクトリ整理・本命プロジェクトへ API として組み込み → 5. 場面と式の量産。
> **エンジンの完成は必須事項。完成まではこちらの判断で進めてよい。**

つまり **いまの担当は「1. エンジンの完成」だけ**。2 以降には手を出さない。

---

## 1. 開始時点の状態（7回目の終わり・実測済み）

| 検査 | 結果 |
|---|---|
| `engine_tests` 全件 | 49,616 passed / 0 failed（約1時間8分） |
| `python -m engine.eval` | **7ゲート全て OK** |
| `scratchpad/audit_progress.py` | 台帳 630 / 実装 630 / 未実装 0 |
| `check_figure_matches_givens.py` | 図905枚 / 食い違い0 |
| コーパス走査（8周目） | 実物の欠陥0件 |
| G-BT（逆翻訳） | 130問 / 意味の食い違い0 |

**未着手として残っていたのは2つだけ:**

- **面③ 解説の中間値**（エンジンの仕事・このセッションの主対象）
- 面⑤ カリキュラムモデルの中身（**エンジンの仕事ではない**＝教育者が入れる共有データ資産。
  配線が動くことは実測済み）

---

## 2. このセッションでやったこと

（作業しながら追記する。§3 に「次の人が最初に読む1行」を置く）

### 2.0 結果（実測）

```
走査 630 セル × 3 seed / 手 3,573 個
括弧に値が入っていない手 0 個 / op 0 個
```

**始めたときは 1,024 手 / 255 op**（2 seed 換算）。解説の途中の手がすべて
「その手で得た式・値」を持つようになった。例:

```
（前）まず、左辺を因数分解する。（左辺を因数分解する）
（後）まず、左辺を因数分解する。（(x + 2)(x + 11) = 0）

（前）まず、データを大きさの順に並べ、中央値を境に下組と上組に分ける。（中央値を境に下組と上組に分ける）
（後）…（下組 1、11、12、16、16、24 / 上組 24、30、40、42、49、50）
```

### 2.1 面③ の測り方をコーパス文から MR へ移した

`scratchpad/scan_step_values.py`（新規）。書き上がった解説文ではなく **MR の `Step`**
を直接見る。文からでは「括弧が無い手」と「複数文の narration」が区別できない。

判定は3つ:

- **空** … `result_display` が空（括弧なしの行になる）
- **言い直し** … `result_display` が `narration` の言い直し（文字の重なり 0.9 以上）
- **指示形** … 値も記号も無く、「〜する」「〜を読み取る」で終わる

**名詞で終わる括弧は落とさない。** `整数`・`錯角`・`点Cを中心とする弧` は
**その手で得たもの**で、用語を答える手・図をかく手ではこれが正しい。
最初これを「値なし」として一律に落としたら 2,012 手が挙がり、大半が誤検出だった。

出力は **op（ソルバ演算名）ごと**。直す単位が solver なので、op で括らないと
どこを直せばよいか分からない。

```
PYTHONPATH=. .venv/bin/python scratchpad/scan_step_values.py --seeds 2
PYTHONPATH=. .venv/bin/python scratchpad/scan_step_values.py --op <op名>   # 該当セル一覧つき
```

### 2.2 直し方（どの solver も同じ形）

どの solver も `_○○_PHRASE` という**指示の言い直しの表**を持っていて、
最後の手だけに答えを入れ、途中の手にはその表の文を入れていた。直し方は同じ:

1. `_○○_PHRASE` を消し、**その手で得た式・値を組む関数**に置きかえる
2. 途中の式は **sympy に渡す前に文字列で組む**（`sympy.Add` にすると同類項が
   勝手にまとまり、「まとめる前」を見せる手の括弧に答えが出てしまう）
3. 書かれた順を保つ（`engine/packs/math/solvers/_step_text.py` の `top_level_parts`）

**新設**: `engine/packs/math/solvers/_step_text.py`
（`top_level_parts` / `flatten_factors` / `fmt_expr` / `join_signed`）。

### 2.3 「読み取るだけの手」は括弧を空にする

`read_rule_context`・`identify_description` のような**問題を読むだけの手**には、
計算した値が無い。ここに言い直しを入れると

```
まず、説明されている式や数の部分がどれかを読み取る。（説明されている対象を読み取る）
```

となり、読んでも何も増えない。**括弧を空にする**と `t1_template` は括弧ごと出さないので

```
まず、説明されている式や数の部分がどれかを読み取る。
```

と読める文になる。`scan_step_values.py` も、narration が「読み取る／見分ける／
確かめる／思い出す／見つける」で終わる手の空括弧は正常として数えない。

### 2.4 済んだ solver（実測で確認済み）

| ファイル | 何を入れたか |
|---|---|
| `arithmetic.py` | 正負の数の四則15 mode 全部（符号の決定・項の並べ替え・通分・逆数・累乗の積・分配法則の分け方） |
| `polynomial.py` | 同類項の組・かっこを外した形・逆数の積・係数の積・展開12 mode・因数分解8 mode |
| `letter_expr.py` | 一次式の整理・代入した式（`6 × 9 - 3`）・累乗を計算した形・記法のきまり |
| `quadratic.py` | 平方完成・平方根・係数 a b c・判別式・因数分解・**空だった `apply_zero_product`** |
| `quadratic_function.py` | 代入・変域の端点・変化の割合・交点・面積の比・動点の位置 |
| `linear.py` | 代入した左辺・傾きの進み方・傾き/切片の符号・変化の割合 |
| `equation.py` | 移項・分母をはらった式・たすきがけ（**手をつないで持ち回る**）・往復の式 |
| `radical.py` | 1つの根号にまとめた形・平方の因数の分け方・共役をかけた形（**文字列から読む**） |
| `motion.py` | 動点の座標・区間の分け方・区間ごとの式・折れ点 |
| `probability.py` | 全部で何通り／あてはまるのは何通り（数え上げはここが要） |
| `quartile.py` | 並べかえた列・下組と上組・四分位数・箱ひげ図の読み値 |
| 幾何（`angle_tracking` / `inscribed_angle` / `triangle_properties` / `quadrilateral_properties` / `plane_geometry` / `plane_transform` / `pythagorean` / `similarity*` / `congruence_correspondence`） | 読み取った角・辺・比・移動後の座標 |
| `solid_view.py` / `solid_figure.py` | 回転の軸・寸法・展開した面・立てた方程式 |
| `statistics_distribution.py` / `distribution_chart.py` / `sample_survey.py` | 階級値・相対度数・累積度数・比例式 |
| `arithmetic.py`（素因数分解・科学的記数法） | わり出した素数・四捨五入した数・動かした桁数 |

**罠2つ**（どちらも実際に踏んだ）:

- **`sympy.sympify` は読んだ時点で簡約する。** `sympify("sqrt(20)")` は `2√5`、
  `sympify("(-7)*x+(-9)*x")` は `-16x`。「まとめる前」を見せる手の括弧に**答えが
  そのまま出ていた**。文字列のまま読むか、`_terms_in_written_order` を使う。
- **手は前の手の結果につなぐ。** 毎回もとの式から組み直すと、分母をはらった次の手が
  分数のままの式を見せる（`equation.py` の `_apply_step` が (表示, 左辺, 右辺) を返す形）。

---

### 2.5 走査そのものの誤検出を4回直した（大事）

1. **紛らわしい語尾**。「条件を満たす」「同じ機会になる」「垂直に交わる」を
   `たす`・`なる`・`わる` で拾っていて、**直したあとの正しい括弧まで挙がっていた**。
2. **最後の手は答え**。「全員に聞いて比べる」のような答えは動詞で終わるので、
   最終手を見ると必ず挙がる。`sq.steps[:-1]` だけを見る。

3. **値があれば通す、が抜け道になっていた**。`2つの項の文字の部分を比べる` は
   数字を含むので素通りしていた。**指示の語尾を先に見て、そのあとで値を見る**。
   これは MR 側の走査では見つからず、**コーパス側の走査（`scan_explanations`）が
   拾って**分かった——2つの走査は測り方が違うので、両方回す意味がある。
4. **句点で終わる括弧は証明の文**（`c、n を整数とする。`）。動詞で終わるので
   引っかかるが、これは括弧に入るのが正しい。

**走査の数だけを見て直したつもりになるとここで間違える。** 必ず実物（narration と
result_display の組）を出して読む。

### 2.5b コーパス側の走査で見つかった2件（面③の副作用と、前からあった漏洩）

- **解説の分母が13以上**: 通分の手（`24/40 - 4/40 - 5/40 + 10/40`）で正しく出るように
  なった。検査のほうを直した（通分の行を除いてから見る）。
- **ヒントに答えがそのまま出ている**（g2_l43.knowledge.Lv2）: narration に
  「正三角形であるといえる」と書いてあり、それがそのままヒントになっていた。
  **narration に答えの文字列を書かない**（G-Q5t は数字しか見ないので気づけない）。

---

## 2.6 面③ で触っていないもの（意図）

- **`narration` は原則そのまま。** 触ったのは6か所だけで、いずれも
  「括弧の中身と言葉が食い違うから」（`置きかえた式` → `かたまりのままの式`、
  `それぞれ a√b の形に直す` → `1つの根号にまとめる`）。数字は入れていない。
- **答え（最後の手）は触っていない。** 面③は途中の手だけの話。
- **図・問題文・答えの値は1つも動いていない**（`git diff` で確かめること）。

---

## 3. 全走検証の結果（2026-08-14 04:06 時点・すべて実測）

| 検査 | 結果 |
|---|---|
| `scan_step_values`（630セル×3seed） | **括弧に値が入っていない手 0 個** |
| `engine_tests` 全件 | **49,616 passed / 0 failed**（1:20:51） |
| `python -m engine.eval` | **7ゲート全て OK** |
| コーパス走査（解説・1,466問） | 言い直し0・空0・sympy0・半角スペース0・最後の手0 |
| コーパス走査（欠陥） | 既知の正当なもののみ（確率の分数・同位角で答えが本文に出る6件ほか） |
| `check_figure_matches_givens` | 図905枚 / 食い違い0 |
| `audit_progress` | 台帳 630 / 実装 630 / 未実装 0・**監査 OK** |

**残っている既知の非ゼロ**（実物を見て正当と判断したもの）:

- `ヒントに答えがそのまま出ている 4問/2セル` … 証明の答え（長文）を `、` で割って
  ヒントと部分一致しただけ。検査の粒度の問題で、漏洩ではない
- `答えが問題文にそのまま出ている 6問` … 5回目から既知（同位角・円周角・有理化ほか）

---

## 3.5 次の人がまずやること

1. **面③は終わっている。** 走査を回すと 0 が出るのが正しい状態
2. 残っているエンジンの仕事は §7 を見る（ここに書いた「次に開ける面」）
3. カリキュラムモデルの中身（前提関係・誤答要因）は**教育者と作る仕事**で、
   エンジン側は待ちの状態（`audit_progress` に充足率が出る）

---

## 4. 変えてはいけないもの（7回目から継続・理由つき）

- **`narration` に数字を書かない。** ヒントは `narration` だけを見る
  （`t1_template._build_hints` → `[step.narration for step in sq.steps[:-1]]`）ので、
  narration に値を書くと**答えの先出し**になる。27 solver に明記がある。
  **面③ で触るのは `result_display` の側だけ。**
- **`engine/eval/_harness.py` に pipeline の写しを作らない。** 7回目に、harness が
  独自の構成経路を持っていたせいで **ゲートが生徒に出るのと違う MR を測っていた**。
- **定義域を広げて dup を通さない。** 上限を決めてから組の数を数える
  （`dup ≤ 0.20` には約250通り要る）。
- **D-8 の走査で出る6件は正当**（同位角・円周角の定理・等積変形・有理化ほか）。

## 4.5 golden の再承認（面③のあと必ず要る）

解説文が全セルで変わるので、**golden は 281 family ぶんすべて動く**。

```bash
nohup bash scratchpad/approve_all.sh > scratchpad/out_approve.txt 2>&1 & disown
```

- **1プロセスで順に回す**（同時に2つ走らせると互いに上書きする）。約20分
- 終わったら `git diff engine_tests/golden` を見て、**変わっているのが
  `explanation` と `hints` だけ**であることを確かめる（問題文・答えが動いていたら
  それは事故）
- `APPROVE-FAIL __pycache__` の1件は無視してよい（family ではない）

### ★ここで見つけたこと: **golden が6・7回目の直しに追いついていなかった**

再承認後の diff に、解説だけでなく**答えと問題文が変わったセルが28ファイル**あった。
中身を見ると

```
- 9/7÷1/3×3/7 → 81/49
+ 9/5÷(-3/2)×(-1/6) → 1/5
```

で、**古いほうの答え（分母49）は今のエンジンでは作れない**（6回目に入れた
`answer_size` の既定上限は分母12。超えたら組み直す）。つまり golden は
6・7回目の「答えの大きさ・問題文の大きさで組み直す」より前の姿のまま残っていた。
`第1四分位数 21/2` → `10.5` も同じで、7回目の表示の統一が入っていなかった。

**教訓: recipe の構成に触ったら、その場で golden を再承認する。**
あとでまとめて承認すると、解説の差分に紛れて「答えが変わったこと」を見落とす。

## 5. 手順（毎回守る）

```bash
# 重い実行はセッションから切り離す（前任者は3回落とされている）
nohup env PYTHONPATH=. .venv/bin/python -m engine.eval > /tmp/eval.log 2>&1 & disown

PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>   # 定義域や構成を触ったら必ず
PYTHONPATH=. .venv/bin/python -m pytest engine_tests -q -x                     # pytest -q だけではエンジンを1本も見ない
PYTHONPATH=. .venv/bin/python -m engine.tools.spec_cli approve <family>        # golden 再承認は1プロセスで
```

- shell は fish。`timeout` は無い。python は `.venv/bin/python`
- `pkill -f spec_cli` は効かない（`python -` で起動するため）。`ps` で pid を探して kill
- 図は目で見ない。`scratchpad/check_figure_matches_givens.py` を使う

---

## 6. 全走検証の回し方（この順で）

```bash
# ① 解説の中間値（速い・4分）
PYTHONPATH=. .venv/bin/python scratchpad/scan_step_values.py --seeds 3

# ② golden 再承認（**recipe/solver を触ったら必ず。1プロセスで・約25分**）
nohup bash scratchpad/approve_all.sh > scratchpad/out_approve.txt 2>&1 & disown
git diff engine_tests/golden   # 変わってよいのは explanation / hints / result_display

# ③ テストとゲート（並行してよい。テスト約1時間20分・ゲート約50分）
nohup env PYTHONPATH=. .venv/bin/python -m pytest engine_tests -q --no-cov > scratchpad/out_tests.txt 2>&1 & disown
nohup env PYTHONPATH=. .venv/bin/python -m engine.eval > scratchpad/out_eval.txt 2>&1 & disown

# ④ コーパス再生成と走査（約4分＋各1分）
PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/build_corpus.py
PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/scan_explanations.py
PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/scan_defects.py
PYTHONPATH=. .venv/bin/python scratchpad/check_figure_matches_givens.py
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py
```

**`until ! pgrep -f <名前>` で待つと自分自身に一致して止まらない**（何度か引っかかった）。
`grep -q "終わりの目印" ファイル` で待つか、ログの中身を見る。

---

## 7. 次に開ける面（まだ測っていないもの）

1. **図が教材として読めるか**。いま見ているのは「座標が仮定と食い違わない」だけで、
   ラベルの重なり・線の見やすさ・図と問題文の対応は誰も測っていない
2. **全 seed での日本語と数式の対応**。G-BT（7回目）は 130問＝文型ごとに数 seed を
   見ただけ。文型を足したら**必ず1回通す**
3. **解説の日本語そのもの**。値は入った（面③）が、「その手をなぜやるのか」の文
   （narration）は 2026-08-08 以来ほぼ触っていない
4. **カリキュラムモデルの中身**（教育者と作る。エンジンの配線は動く）

## 8. コミットについて

**作業ツリーは未コミット**（追跡ファイル約90＋golden 1,269＋新規ファイル）。
コミットは利用者の指示があるまで行っていない。分けるなら:

1. `engine/packs/math/**` + `engine/packs/math/solvers/_step_text.py`（面③の本体）
2. `engine_tests/golden/**`（再承認）
3. `scratchpad/**` + `docs/**`（走査ツールと記録）
