"""評価プログラム群（実装設計 §8.3・Task10）。

engine.eval は core/packs/curriculum を「読むだけ」（生成と読み取りのみ）で、
core/pack を変更しない。各プログラムは CLI・JSON レポート・終了コードを持ち CI に連携する。

- coverage_scan: 生成不能0・ゲート素通り0（N-5）＋ remedial 対応表の検証
- dup_rate: 重複率の2系統（dup_key 系 / fp 系）
- level_sep: レベル分離（署名相異[静的]＋fp 相異[必須]）
- retry_stats: 有界リトライ発動率・構成失敗分布
"""
from __future__ import annotations

from engine.eval.coverage_scan import run_coverage_scan
from engine.eval.dup_rate import run_dup_rate
from engine.eval.level_sep import run_level_sep
from engine.eval.retry_stats import run_retry_stats

__all__ = ["run_coverage_scan", "run_dup_rate", "run_level_sep", "run_retry_stats"]
