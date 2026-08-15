# 1. エンジン本体

**なければ動かないものだけ**を入れる。ここは**このディレクトリごと**本命の
プロジェクトへ移して、そちらで API 化する前提で作ってある。

## 入れる / 入れない

| | |
|---|---|
| 入れる | エンジンが動くのに必要なコードとデータ（`engine/curriculum/` の spec は**データだが無いと動かない**） |
| 入れない | 記録・引き継ぎ書・走査ツール・生成した問題 → `records/` |
| 入れない | もう使っていないもの → `archive/` |

## CWD に依存しない

family の spec は**パッケージからの相対**で引く（`Path(__file__)` 起点）。
`Path("engine/curriculum/...")` のように書くと、リポジトリの根から実行することが
暗黙の前提になり、**持ち出した瞬間に family が1つも見つからなくなる**。

確かめ方（どこから呼んでも通る）:

```bash
cd /tmp && PYTHONPATH=<repo>/engine_core python -c "
from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest
from engine.core.pipeline import generate
bootstrap(); print(generate(GenerateRequest(subject='math', unit='g1_l1', form='calculation', level=1, seed=1)).problem_text)"
```

## ★ 融合するときに必ず入れるもの

**生成した問題の保存先が、いまこの中に無い。** 出力は `records/work/corpus/` に
置いていて、書き出しているのは `records/work/build_corpus.py`（＝本体の外）。

`engine_core/` だけを移すと**生成はできるが結果がどこにも残らない**。
API 化のときに「出力の受け皿」を引数か抽象で1つ入れること。詳細はルートの README。

## tests/ をここに置いた理由

厳密には「なくても動く」。それでも本体に置いたのは、**融合後に動くことを確かめる
手段が無いと融合できない**から。とくに `tests/golden/` は「承認した問題文と再生成が
一致するか」を見る唯一の関門。分けたいなら `records/` へ移してよい。
