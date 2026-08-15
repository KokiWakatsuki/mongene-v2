# 実際の問題画像収集：初期セットアップとPoC結果 (Walkthrough)

## 実施した内容

ユーザーのシステムと実際の問題を比較するための「画像収集」について、以下の準備と小規模テスト（PoC）を実施しました。

1. **進捗管理シートの生成**
   - `forms_research.csv` から全てのレッスンと問題形式の組み合わせ（1134件分）を抽出し、`reports/problem_collection_progress.csv` を作成しました。
   - すべての初期ステータスを「未着手」として登録しています。

2. **画像保存用ディレクトリの作成**
   - プロジェクト内に `tests/fixtures/real_problems/` フォルダを作成しました。

3. **PoC（小規模テスト）の実行と技術的突破**
   - 当初、Web上のフリー教材サイトから単純な直リンクで画像をダウンロードしようとしましたが、スクレイピング対策（直リンク禁止）によりHTMLエラーページが保存されてしまう問題に直面しました。
   - これを突破するため、**ブラウザ自動操作ツール（Playwright）とPDF画像変換ライブラリ（PyMuPDF）**を導入しました。
   - スクリプトが自動でサイトを開き、広告をブロックしながら「問題詳細ページ」へ遷移。さらにそこから**「問題本体のPDFファイル」を直接ダウンロードし、A4サイズの高画質画像（PNG）に変換して保存**する仕組みを構築しました。
   - 結果として、サイトの枠や余計なヘッダーが一切ない、テストに最適な純粋なプリント画像（`tests/fixtures/real_problems/g1_l1/word_problem_min.png`）の取得に成功しました。

## 結果の確認方法

以下のファイルとディレクトリで結果をご確認いただけます。

*   **進捗管理シート**: [problem_collection_progress.csv](file:///Users/koki/workspace/mongene-v2/reports/problem_collection_progress.csv)
*   **PoC収集スクリプト**: [poc_playwright_screenshot.py](file:///Users/koki/workspace/mongene-v2/scripts/poc_playwright_screenshot.py)
*   **収集された画像（検証用）**: `tests/fixtures/real_problems/g1_l1/word_problem_min.png`

## 今後の進め方

PDFから高画質画像を自動取得する技術検証（PoC）が完了しました。
今後は、このPoCスクリプトをベースにして**「各レッスン（`lesson_id`）と、取得先のURL」を紐付けるマッピングリスト**を作成し、残りの1134件のタスクに対して本格的な自動収集（バッチ処理）を実行していくことが可能です。
