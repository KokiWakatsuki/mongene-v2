"""決定論的評価ゲート群（フェーズ2-2a）。

LLM を一切使わず、`/problems/inspect`（ground truth・LLMフリー）と
`/problems/generate`（product・LLM後の最終出力）を突き合わせて
問題の健全性を機械採点する。

各ゲートは `scripts/eval_gates/gN_xxx.py` に1ファイル1ゲートで実装し、
下記の純関数シグネチャに従う:

    def check(product: dict, ground_truth: dict) -> GateResult

`GateResult` は `scripts.eval_gates.common.GateResult` を参照。
"""
