#!/bin/bash
set -e

# 現在実行中のマッピングスクリプトがあればそれを待つか、再度実行する
# すでに実行中なので、ここではシンプルに完了を待つような仕組みを入れるか、
# または collect_all_problems をそのまま実行する。
# 今回は念のため、両方を直列で走らせる。

echo "--- Phase 1: Generating URL Mapping ---"
.venv/bin/python scripts/generate_url_mapping.py

echo "--- Phase 2: Collecting 1134 Problem Images ---"
.venv/bin/python scripts/collect_all_problems.py

echo "--- All Complete ---"
