#!/bin/bash
# 全走検証を順に回す（golden 再承認が終わってから呼ぶこと）。
# 途中で落ちても次へ進む——**どこで落ちたかを残すため**に、各段のログを別ファイルへ。
cd /Users/koki/workspace/mongene-v2
export PYTHONPATH=.

echo "=== [1/6] engine_tests 全件 ==="
# **--no-cov と -n 4 は必須。** pyproject の addopts は別プロジェクト（apps/・tests/）
# 向けで、`--cov=apps` は engine を1行も測らないのに計測の重さだけ乗る（実測 2.6倍）。
# しかも `--cov-fail-under=80` のせいで **テストが全部通っても終了コードは 1** になる。
# --dist worksteal: 既定の load は最初に配ったら奪い返さないので、
# eval/test_eval_suite.py の重い群が1本に固まり、残り3本が遊んで終盤が止まる
# （直列だと1時間37分たっても 0%。worksteal なら全体33分）。
# **コマンドの途中に `# コメント` を挟まないこと。** 行継続が切れて
# リダイレクトが別コマンドになり、ログが空のまま切り詰められる（実際に踏んだ）。
.venv/bin/python -m pytest engine_tests -q -p no:cacheprovider \
  --no-cov -n 4 --dist worksteal > scratchpad/v_tests.log 2>&1
tail -3 scratchpad/v_tests.log

echo "=== [2/6] engine.eval（7ゲート）==="
.venv/bin/python -m engine.eval > scratchpad/v_eval.log 2>&1
tail -20 scratchpad/v_eval.log

echo "=== [3/6] コーパス再生成 ==="
.venv/bin/python scratchpad/build_corpus.py > scratchpad/v_corpus.log 2>&1
tail -2 scratchpad/v_corpus.log

echo "=== [4/6] 解説の走査 ==="
PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/scan_explanations.py > scratchpad/v_expl.log 2>&1
tail -12 scratchpad/v_expl.log
PYTHONPATH=.:scratchpad .venv/bin/python scratchpad/scan_defects.py > scratchpad/v_defects.log 2>&1
tail -8 scratchpad/v_defects.log

echo "=== [5/6] 図の走査 ==="
.venv/bin/python scratchpad/scan_figure_legibility.py --seeds 3 > scratchpad/v_fig.log 2>&1
cat scratchpad/v_fig.log
.venv/bin/python scratchpad/check_figure_matches_givens.py > scratchpad/v_figmatch.log 2>&1
tail -3 scratchpad/v_figmatch.log

echo "=== [6/6] 台帳の監査 ==="
.venv/bin/python scratchpad/audit_progress.py > scratchpad/v_audit.log 2>&1
tail -6 scratchpad/v_audit.log

echo "=== [7/7] golden 再承認（1プロセス）==="
.venv/bin/python scratchpad/approve_all.py > scratchpad/v_approve.log 2>&1
tail -3 scratchpad/v_approve.log

echo "=== VERIFY DONE ==="
