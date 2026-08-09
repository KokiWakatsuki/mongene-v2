# g1_l50 投影図（3セル）の設計メモ

台帳 desc/example:
- Lv1: 投影図から立体を読む・立体から見た図を選ぶ
  ex: 立面図が長方形、平面図が円である立体は何か、次から選べ。ア三角柱 イ円柱 ウ円錐 エ四角錐。
- Lv2: 立体の立面図・平面図を正確にかく
  ex: 底面が1辺3cmの正方形、高さ4cmの正四角柱。この立体の投影図をかけ。
- Lv3: 投影図の一部から立体を特定し他の図を構成する
  ex: 平面図が正三角形であることだけがわかっている。立面図が長方形になる立体は何か特定し、その立面図をかいて示せ。

## 立体 → (立面図, 平面図) の表（visuals/solid.py の _PROJECTION_SHAPES）

| 立体 | 立面図 | 平面図 |
|---|---|---|
| 四角柱（正四角柱） | 長方形 | 正方形 |
| 立方体 | 正方形 | 正方形 |
| 円柱 | 長方形 | 円 |
| 円錐 | 三角形 | 円 |
| 球 | 円 | 円 |
| 正四角錐 | 三角形 | 正方形＋対角線 |
| 三角柱 | 長方形 | 三角形 |

**この表は (立面図, 平面図) の組で立体が一意に決まる**ことが要点。
Lv1/Lv3 はこの一意性を問う。

## セル設計

- Lv1 `read_from_projection`: 投影図（両方）を図で示し、立体を選ぶ。
  - 問題図: view=projection, shown_view="both"
  - 答え: ChoiceAnswer（立体の名前）
  - ops: [read_elevation_and_plan, identify_solid_from_projection]
- Lv2 `draw_projection`: 立体を本文で与え、投影図をかく。
  - 問題図: 見取図（view=sketch）… ただし draw_solid は "solid" を禁止するので
    問題図は出さない。→ 本文だけで立体が定まる（「底面が1辺3cmの正方形、高さ4cmの正四角柱」）
    ので、問題図は**空**でよい。graph_table は visual required なので visual_plan は要る。
    → elements=[] の空の枠（＝生徒がかく紙）にする。
  - 答え: GraphAnswer（立面図の形・平面図の形・寸法）＋ solution_svg（view=projection, both）
  - ops: [determine_elevation, determine_plan, draw_projection]
- Lv3 `complete_projection`: 平面図だけを与え、立体を特定して立面図をかく。
  - 問題図: view=projection, shown_view="plan"（片方だけ）
  - 答え: GraphAnswer（立体名・立面図の形）＋ solution_svg（view=projection, both）
  - ops: [read_given_view, identify_solid_from_partial, draw_missing_view]

## dup
- 立体の種類（7）× 寸法2つ（14×14 相異）× ... = 7×14×13 = 1274 ✓
- Lv3 は平面図だけで立体が一意に決まる必要 → 平面図が重複する立体を除く
  （正方形: 四角柱/立方体/正四角錐 が重複、円: 円柱/円錐/球 が重複、三角形: 三角柱のみ）
  → Lv3 は「平面図 + 立面図が長方形」のように追加条件で絞る。
  example どおり「平面図が正三角形・立面図が長方形 → 三角柱」の形にする。
  一意に決まる (平面図, 立面図の種類) の組だけを構成で列挙する。
