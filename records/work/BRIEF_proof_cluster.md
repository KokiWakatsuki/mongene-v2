# 証明セル横展開ブリーフ（proof form・単元クラスタ単位）

## 何を作るのか

`form: proof`（図形の証明）のセルを、**規則カタログと構成カタログを足すことで**開く。
機構（推論器・証明文の組み立て・質のフィルタ）は完成しているので**触らない**。
設計書は `docs/proof_engine_design_2026-08-08.md`。まずこれを読むこと。

生成の筋道:

```
構成（作図手順）→ 事実の集合 → 前向き推論で飽和 → Lv に合う結論を選ぶ → 証明文
   constructions_*.py        deduce.saturate      naturalness.select_goal   render_text
```

**問題を手で書かない。** 図は作図手順で組み、事実は手順そのものが持つ（座標から測らない）。
「解き方の違う問題」は、手順と規則の組合せを変えることで出てくる。

## 手本にする既存実装（必ず先に読む）

- `engine/packs/math/geometry/rules_congruence.py` — 規則の書き方の手本
- `engine/packs/math/geometry/constructions_congruence.py` — 構成の書き方の手本
- `engine/packs/math/geometry/facts.py` — 述語と正規形。**述語は先に足してある**
- `engine/packs/math/geometry/construct.py` — 作図の基本手順（`free_point` `point_on_circle`
  `point_on_perpendicular_bisector` `reflected_point` `translated_point` `midpoint_of` …）
- `engine/packs/math/recipes/geometry_proof.py` — recipe（**触らない**）
- `engine/curriculum/math/families/g2_l41.proof.yaml` — family YAML の手本（Lv2/Lv3 の書き分け）

## あなたが触ってよいファイル（これ以外は触らない）

他の2つのエージェントが**同時に別クラスタを進めている**。下のファイル以外を編集すると
衝突する。必要な共有側の下ごしらえ（述語・概念ID・TOPIC_SETS・recipe の
`provides_concepts`）は**すべて済ませてある**。

- `engine/packs/math/geometry/rules_<あなたのクラスタ>.py`
- `engine/packs/math/geometry/constructions_<あなたのクラスタ>.py`
- `engine/curriculum/math/families/<あなたの単元>.proof.yaml`（新規作成）
- `scratchpad/` 配下の作業ファイル

**共有ファイル（`rules.py` `catalog.py` `facts.py` `concepts.yaml` `geometry_proof.py`
`construct.py` `render_text.py` `naturalness.py` `deduce.py`）を編集してはならない。**
足りないものが出たら、勝手に足さず**報告に「共有側にこれが要る」と書いて止める**
（その部分だけ諦めて、残りは完成させる）。

## family YAML の書き方

`concepts_default` と各 Lv の `concept_tags` に使う概念IDは、**recipe の
`_PROOF_CONCEPTS` に載っているものだけ**（`engine/packs/math/recipes/geometry_proof.py`）。
そこに無いIDを書くと lint R6 が落ちるか、**check_cell は通るのに台帳に載らない**（既知の罠）。

params で指定できるもの:

| key | 意味 |
|---|---|
| `construction` | 構成の登録名（あなたの `constructions_*.py` で `@register_construction`） |
| `topic_set` | その単元で習っている定理の範囲（`catalog.TOPIC_SETS` のキー） |
| `proof_depth` | 結論の深さ。**Lv と深さの対応は単元ごとに違う**（下記） |
| `prefer` | 結論に選ぶ述語（`tri_cong` `seg_eq` `ang_eq` `parallelogram` `tri_sim` …）。既定 `tri_cong` |
| `exclude_rules` | **証明したい定理そのものを規則から外す**（下記・最重要） |
| `base_domain` / `angle_domain` / `offset_domain` | 図のパラメータ（`{int_range: [a, b]}`） |

`text:` には必ず `visual_builder: math.geometry_construction` を書く（書かないと図が出ない）。

## 落とし穴（過去に全部踏んだ）

1. **循環（最重要）**。「〜であることを証明せよ」の単元で、その定理を規則として使えると
   1手で終わる。`exclude_rules` でその規則を外す。単元ごとに「これから示すこと」を外す。
2. **Lv と深さの対応は単元ごとに違う**。「合同を直接示す」単元の Lv2 は深さ1だが、
   「合同を示してから対応する辺が等しいと結論する」単元の Lv2 は最初から深さ2。
   台帳の desc（`units.generated.yaml`）を正として決める。
3. **Lv 間で op 列が同じだと eval の level_sep が落ちる**。証明の各行がそのまま steps に
   なるので、Lv2 と Lv3 で**使う規則の並びが違う**ことを必ず確かめる（下の検証コマンド）。
4. **概念IDの配線切れ**。上記のとおり `_PROOF_CONCEPTS` に無いIDを使わない。
5. **図は必ず PNG に起こして目視する**。ゲートは図の内容の誤りを検出しない。
   過去に「二等辺三角形が上下逆さま」「交点のラベルが線に埋もれる」を目視だけで発見した。
6. **`reason` は教科書の言い回しに固定する**。そのまま証明文の根拠欄に出る。
   市販の問題集の模範解答と一字一句そろえること。

## 検証（これを全部通すまで完了ではない）

```bash
# 1) セル単位の DoD（rejects=0/120・dup_rate ≤ 0.20）
PYTHONPATH=. .venv/bin/python scratchpad/check_cell.py <unit> proof <lv,lv,...>

# 2) Lv 間で op 列が相異するか（level_sep）
PYTHONPATH=. .venv/bin/python -c "
from engine.bootstrap import bootstrap; bootstrap()
from engine.core.contracts import Coordinate
from engine.core.pipeline import generate
from engine.eval._harness import make_env
env = make_env()
for lv in (2,3,4):
    try:
        mr = generate(Coordinate(subject='math', unit='<unit>', form='proof', level=lv), seed=1, env=env)
    except Exception as e:
        print(lv, 'ERR', e); continue
    print(lv, [s.op for s in mr.sub_questions[0].steps])
"

# 3) 図を PNG にして目視（cairosvg 等・既存の scratchpad スクリプトを流用してよい）

# 4) 全体
PYTHONPATH=. .venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python scratchpad/audit_progress.py
```

`audit_progress.py` の検査[1]（family 宣言があるのに台帳に載らない）が 0 でないなら
配線が切れている。

## 報告

- 開いたセルの一覧（unit / Lv / 図 / 深さ / 筋道を1行ずつ）
- 追加した規則と構成の名前
- 検証の実測値（rejects・dup_rate・op 列）
- 開けなかったセルと、その理由（共有側に何が要るか）
- **git commit はしない**（親がまとめて行う）
