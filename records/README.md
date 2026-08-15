# 2. 記録群-その他

**今後の作業には必要だが、エンジンとしては不要なもの。** 大半がここに入る。

```
docs/            引き継ぎ書（回ごと）・設計書。なぜそう作ったかはここにある
work/            走査・検証の道具と、その出力
  corpus/        生成した問題（読んで直すループの出力）
  bt/            逆翻訳の読み手の答え＝日本語と数式の対応の証拠
  *.py           scan_* / bt_* / build_corpus / approve_all / verify_all.sh
phase_status.md
```

## なぜ生成した問題がここなのか

「エンジンの問題点を修復する → 再度問題を生成する → エンジンを修繕する」の
ループでは、**結果を見たい**が、エンジンを**動かすのには要らない**。だから本体
（`engine_core/`）には入れない。

**ただし、エンジンだけを持ち出すと保存先が無くなる。** その注意はルートの README と
`engine_core/README.md` に書いてある（API 化のときに直す）。

## 追跡するもの / しないもの

**道具（`.py` / `.sh`）と記録（`.md` / 逆翻訳の `.tsv`）だけを追跡する。**
ログ・図・生成コーパスは `.gitignore` に入れてある——追跡下に置くと、実行のたびに
1,000件規模の雑音が `git status` を埋め、本当の変更が埋もれる（実際に埋もれた）。

消えても困らない: `build_corpus.py` が10分で作り直す。
消えると困る: `bt/answers*.tsv`（人が問題文だけを読んで解いた答え。再生成できない）。

## 走らせ方

```bash
PYTHONPATH=engine_core            python records/work/audit_progress.py
PYTHONPATH=engine_core:records/work python records/work/scan_explanations.py
bash records/work/verify_all.sh   # 全走検証
```
