# 3. 過去のもの

**もう使っていない。** 消すのは惜しいので、過去に何があったかを見に行くために残す。
**ここのコードは動かさない。CI も検査しない。**

```
legacy_app/          LLM 世代の API（FastAPI + Gemini）。atoms / blueprints / verbs で組んでいた
legacy_scripts/      その頃の収集・評価スクリプト
legacy_tests/        その頃のテスト（1件だけ engine を参照している＝geometry proof の検査）
legacy_master_data/  その頃のマスタ（atoms.yaml / blueprints.yaml / verbs.yaml …）
reports/             比較調査（第1〜4回）・カバレッジ・評価バッチ
Makefile             旧 API の起動用（`uvicorn apps.api.main:app`）
```

## なぜ捨てたのか

LLM に文を書かせる作り方をやめた。理由は**ゲートを全部通るのに日本語と数式が
食い違う問題が出る**こと。checker が recipe と同じ立式関数を呼び直していたので、
検証していたのは「数値 → 立式 → 解」の連鎖で、「その日本語が本当にその数式を
意味しているか」ではなかった。

そこから**答えを先に作って日本語を後から当てる**決定論的な作り方に変えた。
経緯は `records/docs/` の引き継ぎ書に回ごとに残っている。

`legacy_master_data/cache/` は当時の LLM 応答キャッシュ（625MB）。追跡していない。
