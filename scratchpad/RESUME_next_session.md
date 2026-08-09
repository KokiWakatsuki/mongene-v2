# 次セッションへの引き継ぎ（2026-08-09 更新・**Phase F/G が終盤**）

## 到達点（2026-08-09 夜）

**622/630 (98.7%)**。`scratchpad/audit_progress.py` = 監査 OK（配線切れ0・未使用資産0）。
**残り8はすべて proof**。construction 9セルは完成した。

```
proof   8   g2_l38 Lv2/Lv3（仮定と結論・反例）
            g2_l40 Lv4・g2_l41 Lv4・g2_l42 Lv3（推論器で開く最上位）
            g3_l51 Lv3/Lv4（三平方の証明）・g3_l52 Lv3（三平方の逆）
その他   0   construction 9 を含め、他の form はすべて 100%
```

<details><summary>2026-08-08 時点の記述（Phase A〜E 完了時・履歴として残す）</summary>

**570/630 (90.5%)**。証明（proof 51）と作図（construction 9）以外の 570 セルは全部実装済み。
</details>

## この一連で効いた設計判断（次も同じ手が使える）

1. **問い方が同じなら、単元がばらばらでも1投資で束ねられる。**
   端物11セルはこれで片付いた——図の要素を記号で答える3セル（frame の asked に
   `read_figure_element` ＋ `visuals/plane_figure.py`）と、樹形図2セル
   （`draw_tree_diagram` ＋ `visuals/tree_diagram.py`）。
2. **記述の設問は「選ぶ」に畳めば採点可能になる。**
   「逆を述べよ」「反例を挙げよ」→ 候補から選ばせる（判別も提示も同じ操作）。
   作図は「作図の結果である値」（断面の辺の長さ・回転の中心の座標・場合の列）を答えにする。
3. **exam セルは exam_fusion.py ではなく既存単元の recipe モジュールに同居させる。**
4. **図は必ず PNG に起こして目視する。** この一連で4件の図のバグを目視だけで見つけた
   （断面の頂点の並び違い／角度の測り元の食い違い／線が枠外に抜けてラベルが消える／
   座標を答えさせるのに軸が無い）。ゲートもテストも検出しない。

## Phase F（proof 51セル）— 次の最大の投資

form ごと未実装で、**frame・solver・checker・テンプレートを新規に設計する**。
現状わかっていること:

- `PROOF_FRAME` は語彙とコメントだけ宣言済みで、ロジックは `check_mr` に委ねてある。
  答えの型（proof_text）が無いのが本体の欠落。
- `docs/goal_spec_2026-07-12.md` の 2026-07-30 の注記に見立てがある——
  **中学の証明問題の実物は大半が穴埋め**（根拠・合同条件・対応する辺の選択）なので、
  `ChoiceAnswer` の列に落とせば I3（proof frame の全体設計）を待たずに相当数が射程に
  入る見込み（未検証）。この一連で「記述は選ぶに畳める」を3回実証したので、
  その見立ての確度は上がっている。
- **着手したら `test_unsupported_codes.py` の `not_implemented` 座標
  （現在 exam_l6.proof Lv3）を、まだ未実装の別セルに差し替えること。**

## 完成条件でまだ測っていないもの（planning の前提）

- **`写像監査 ≥95%` は一度も測っていない。** goal_spec §3.1 の G1-BASE-DONE は
  (a) green 630/630 ∧ (b) eval exit 0 ∧ **(c) 写像監査 ≥95%** の3つで、(c) を測る道具が
  `engine/tools/` に無い。630 に届いてから立ち上げるのでは順序が逆
  （写せない外部問題が見つかれば台帳そのものが増減する）。
- **分母 630 は動きうる。** `unit_flag` が ok でない単元が2つ（g2_l15=merge・g3_l53=split）。

## 実測コマンド

```bash
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py     # 進捗更新前に必ず
PYTHONPATH=. .venv/bin/python scratchpad/verify_progress.py 3  # 全セルを実生成して裏取り
PYTHONPATH=. .venv/bin/python -m engine.tools.goal_progress    # C1〜C16 の公式集計
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> <form> <lv,lv>
PYTHONPATH=. .venv/bin/python scratchpad/peek.py <unit> <form> <lv> <seed>
PYTHONPATH=. .venv/bin/python -m engine.eval                   # 約20分・exit 0 が DoD
.venv/bin/python -m pytest engine_tests --no-cov -q            # 約35分・49525 tests
PYTHONPATH=. .venv/bin/python -m engine.tools.coverage_page    # docs/coverage.html
```
