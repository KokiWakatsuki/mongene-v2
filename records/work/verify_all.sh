#!/bin/bash
# 全走検証を順に回す（golden 再承認が終わってから呼ぶこと）。
# 途中で落ちても次へ進む——**どこで落ちたかを残すため**に、各段のログを別ファイルへ。
#
# ★2026-08-20: エンジンが mongene-engine に移り、`engine_core/` は無くなった。
#   直したのは3つ。
#     1. `cd` の絶対パスの直書き → **このスクリプトの位置から引く**。
#        ディレクトリを動かすと壊れ、しかも cd が失敗しても bash は次へ進むので
#        呼んだ場所で全部が走ってしまう（無言で別物を検査する）。
#     2. `pytest engine_core/tests` → engine_paths.py の `TESTS_DIR` から引く。
#     3. ★**各段の終了コードを覚えて最後に表を出す**。
#        以前は段が丸ごと飛んでも最後に「VERIFY DONE」と出た。
#        1段目の pytest が「そんなパスは無い」で即死しても、そう見えた。
#        **見ていないのに合格に見える**のがこのプロジェクトで一番起きている事故なので、
#        「走った・通った・落ちた・走れなかった」を区別して必ず出す。

# このスクリプトは records/work/ にあるので、2つ上がリポジトリの根。
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || { echo "リポジトリの根に入れない: $REPO_ROOT"; exit 1; }

# 走査は engine_paths を import する（records/work を通す）。
export PYTHONPATH=records/work

# ★エンジンのテストの置き場所は engine_paths が答える。パスを書かない。
TESTS_DIR=$(.venv/bin/python -c 'from engine_paths import TESTS_DIR; print(TESTS_DIR)' 2>&1)
if [ ! -d "$TESTS_DIR" ]; then
  echo "★エンジンのテストが見つからない: $TESTS_DIR"
  echo "  pip install -e ../mongene-engine を済ませているか確認すること。"
  exit 1
fi
echo "エンジンのテスト: $TESTS_DIR"

# ★ログは **リポジトリの中**（records/work/logs/）に置く。scratchpad はセッションごとに
# 消えるので、アカウントを切り替えると引き継げない（利用制限で切れることを前提にする）。
LOGDIR=records/work/logs
STAMP=$(date +%Y%m%d_%H%M)
mkdir -p "$LOGDIR"
echo "ログ: $LOGDIR/*_$STAMP.log"

# --- 各段の結果を覚える ---------------------------------------------------
STEPS=()
CODES=()
record() { STEPS+=("$1"); CODES+=("$2"); }

echo "=== [1/7] エンジンのテスト 全件 ==="
# **--no-cov と -n 4 は必須。** pyproject の addopts は別プロジェクト（apps/・tests/）
# 向けで、`--cov=apps` は engine を1行も測らないのに計測の重さだけ乗る（実測 2.6倍）。
# しかも `--cov-fail-under=80` のせいで **テストが全部通っても終了コードは 1** になる。
# --dist worksteal: 既定の load は最初に配ったら奪い返さないので、
# eval/test_eval_suite.py の重い群が1本に固まり、残り3本が遊んで終盤が止まる
# （直列だと1時間37分たっても 0%。worksteal なら全体33分）。
# **コマンドの途中に `# コメント` を挟まないこと。** 行継続が切れて
# リダイレクトが別コマンドになり、ログが空のまま切り詰められる（実際に踏んだ）。
.venv/bin/python -m pytest "$TESTS_DIR" -q -p no:cacheprovider \
  --no-cov -n 4 --dist worksteal > "$LOGDIR/v_tests_$STAMP.log" 2>&1
record "pytest（エンジン全件）" $?
tail -3 "$LOGDIR/v_tests_$STAMP.log"

echo "=== [2/7] engine.eval（7ゲート）==="
.venv/bin/python -m engine.eval > "$LOGDIR/v_eval_$STAMP.log" 2>&1
record "engine.eval（7ゲート）" $?
tail -20 "$LOGDIR/v_eval_$STAMP.log"

echo "=== [3/7] コーパス再生成 ==="
.venv/bin/python records/work/build_corpus.py > "$LOGDIR/v_corpus_$STAMP.log" 2>&1
record "コーパス再生成" $?
tail -2 "$LOGDIR/v_corpus_$STAMP.log"

echo "=== [4/7] 解説の走査 ==="
.venv/bin/python records/work/scan_explanations.py > "$LOGDIR/v_expl_$STAMP.log" 2>&1
record "解説の走査" $?
tail -12 "$LOGDIR/v_expl_$STAMP.log"
.venv/bin/python records/work/scan_defects.py > "$LOGDIR/v_defects_$STAMP.log" 2>&1
record "欠陥の走査" $?
tail -8 "$LOGDIR/v_defects_$STAMP.log"

echo "=== [5/7] 図の走査 ==="
.venv/bin/python records/work/scan_figure_legibility.py --seeds 3 > "$LOGDIR/v_fig_$STAMP.log" 2>&1
record "図の読みやすさ" $?
cat "$LOGDIR/v_fig_$STAMP.log"
.venv/bin/python records/work/check_figure_matches_givens.py > "$LOGDIR/v_figmatch_$STAMP.log" 2>&1
record "図と与件の一致" $?
tail -3 "$LOGDIR/v_figmatch_$STAMP.log"
.venv/bin/python records/work/check_figure_numbers.py > "$LOGDIR/v_fignum_$STAMP.log" 2>&1
record "図の数と本文の一致" $?
tail -3 "$LOGDIR/v_fignum_$STAMP.log"

echo "=== [6/7] 台帳の監査 ==="
.venv/bin/python records/work/audit_progress.py > "$LOGDIR/v_audit_$STAMP.log" 2>&1
record "台帳の監査" $?
tail -6 "$LOGDIR/v_audit_$STAMP.log"

echo "=== [7/7] golden 再承認（1プロセス）==="
.venv/bin/python records/work/approve_all.py > "$LOGDIR/v_approve_$STAMP.log" 2>&1
record "golden 再承認" $?
tail -3 "$LOGDIR/v_approve_$STAMP.log"

# --- ★結果の表（走った・通った・落ちた を区別して必ず出す）-----------------
echo
echo "================ 全走の結果 ================"
NG=0
for i in "${!STEPS[@]}"; do
  c=${CODES[$i]}
  if [ "$c" -eq 0 ]; then
    mark="OK  "
  elif [ "$c" -eq 4 ] || [ "$c" -eq 5 ]; then
    # pytest: 4=使い方の誤り（パスが無い等）・5=1件も集まらなかった
    mark="★走れなかった"; NG=$((NG+1))
  else
    mark="落ちた"; NG=$((NG+1))
  fi
  printf "  %-14s %-24s (終了コード %s)\n" "$mark" "${STEPS[$i]}" "$c"
done
echo "============================================"
if [ "$NG" -eq 0 ]; then
  echo "=== VERIFY DONE — 全 ${#STEPS[@]} 段 OK ==="
else
  echo "=== ★VERIFY 未達 — ${#STEPS[@]} 段のうち $NG 段が OK でない。上の表とログを見ること ==="
  exit 1
fi
