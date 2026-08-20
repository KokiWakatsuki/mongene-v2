# mongene-v2

mongene エンジンの**開発の記録**。設計の経緯・走査（検査の道具）・失敗カタログを持つ。

★**エンジン本体はここには無い。** 別リポジトリ `mongene-engine` にあり、
ここはそれを**インストールして使う**。

```
mongene-master/
├── mongene-engine   エンジンの正本（engine・tests・app・API）
└── mongene-v2       ← ここ。記録と走査だけ
```

なぜ分けたか: 同じコードを2か所に置くと**片方だけ直る**。このプロジェクトで
いちばん多く事故を起こしている形で、1日のうちに「頂点名から I を外す（4か所に散在）」
「往復の距離の上限（2か所にあり片方だけ直っていた）」が実際に出た。
**コードの正本は1つ**にする。

## 使い方

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ../mongene-engine     # ★エンジンを editable で入れる
pip install -e ".[dev]"

# エンジンの場所が解決できるか（走査は全部これを通す）
PYTHONPATH=records/work python records/work/engine_paths.py
```

走査の実行例:

```bash
PYTHONPATH=records/work python records/work/check_cell.py g1_l25 word_problem 2
PYTHONPATH=records/work python records/work/check_unit_fit.py --seeds 3
PYTHONPATH=records/work python records/work/check_layer_split.py
```

★**エンジンのコードを直すのは `mongene-engine` 側。** ここでは直さない。
`records/work/check_write_scope.py` が、誰がどこを書いたかを差分で見る。

---

## 1. エンジン本体は別リポジトリ

`mongene-engine` にある。中身:

```
mongene-engine/
├── engine/    Python パッケージ（`import engine`）
│   ├── core/        契約・パイプライン・ゲート・レンダラ
│   ├── packs/math/  recipe / solver / checker / visuals（教科の中身）
│   ├── curriculum/  単元・family の spec（YAML）＝**データだが無いと動かない**
│   ├── eval/        7ゲートの測定
│   └── tools/       spec_cli（preview / check / approve）
├── app/       FastAPI（GET /health・GET /units・POST /generate）
└── tests/     golden 回帰を含む
```

走査からエンジンのファイルを読むときは、パスを直書きせず
`records/work/engine_paths.py` を通す（**場所を答えるのは1か所だけ**）。

## 2. `records/` — 記録群-その他

**今後の作業には必要だが、エンジンとしては不要なもの。** 大半がここに入る。

```
records/
├── docs/            引き継ぎ書（回ごと）・設計書
├── work/            走査・検証の道具と、その出力
│   ├── corpus/      **生成した問題**（読んで直すループの出力）
│   ├── bt/          逆翻訳（G-BT）の読み手の答え＝日本語と数式の対応の証拠
│   └── *.py         走査ツール（scan_* / bt_* / build_corpus / verify_all.sh）
└── phase_status.md
```

「エンジンの問題点を修復する → 再度問題を生成する → エンジンを修繕する」の
ループが出す**生成物はここに置く**。エンジンを動かすのに要らないので本体には入れない。

### ★ エンジンだけを持ち出すときの注意（あとで直すこと）

**問題の保存先が `records/work/corpus/` に固定されている。**
`records/work/build_corpus.py` が書き出し先を持っているので、`engine_core/` だけを
本命プロジェクトへ移すと、**生成した問題の置き場が無くなる**。

直し方は決めていない。候補は2つ。

1. 出力先を引数（または環境変数）にして、呼ぶ側が決める
2. エンジン側に「出力の受け皿」の抽象（`ProblemSink` のような）を1つ置き、
   保存先の実装は外に出す

API 化のときに**どちらかを必ず入れる**。入れずに移すと「生成はできるが結果が
どこにも残らない」状態になる。

---

## 3. `archive/` — 過去のもの

**もう使っていない。** 消すのは惜しいので、過去に何があったかを見に行くために残す。

```
archive/
├── legacy_app/          LLM 世代の API（FastAPI + Gemini）。atoms / blueprints / verbs で組んでいた
├── legacy_scripts/      その頃の収集・評価スクリプト
├── legacy_tests/        その頃のテスト
├── legacy_master_data/  その頃のマスタ（atoms.yaml / blueprints.yaml / verbs.yaml …）
├── reports/             比較調査（第1〜4回）・カバレッジ・評価バッチ
└── Makefile             旧 API の起動用（`uvicorn apps.api.main:app`）
```

**なぜ捨てたのか**は `records/docs/` の引き継ぎ書に残っている。要点は
「LLM に文を書かせると、ゲートを全部通るのに日本語と数式が食い違う問題が出る」で、
そこから**答えを先に作って日本語を後から当てる**決定論的な作り方に変えた。

`legacy_master_data/cache/` は当時の LLM 応答キャッシュ（625MB）。追跡していない。

---

## 開発の回し方

```bash
# テスト全件（約33分）
PYTHONPATH=engine_core pytest engine_core/tests

# 7ゲート
PYTHONPATH=engine_core python -m engine.eval

# 全走検証（テスト → ゲート → コーパス再生成 → 各走査 → golden 再承認）
bash records/work/verify_all.sh
```

**カバレッジは既定で切っている**（`pyproject.toml`）。前は `--cov=apps` が既定に
入っていて、engine を1行も測らないのに計測の重さだけ乗り（実測2.6倍）、さらに
`--cov-fail-under=80` のせいで**全部通っても終了コードが 1** になっていた。
