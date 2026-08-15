"""難易度計算モジュール（難易度設計 implementation_plan.md による抜本的見直し版）

Raw Score モデル:
  raw_score = large_unit_score + lesson_score
  y_base (1-100) = normalize(raw_score)

正規化:
  RAW_MIN = 100  （最も簡単: 中1正負の数、導入、計算）
  RAW_MAX = 1300 （大単元最大 900 + 小単元最大 400）
  Difficulty = 1 + 99 * (raw - RAW_MIN) / (RAW_MAX - RAW_MIN)

問題形式ボーナス（reconciler 側で加算）:
  calculation (+0), word_problem (+400), proof (+800)
"""
from __future__ import annotations

import re

# ① 大単元スコア: 100〜900（「つまずきやすさ」を反映）
LARGE_UNIT_RAW_SCORE: dict[str, int] = {
    # 中学1年
    "正の数・負の数": 100,
    "文字の式": 150,
    "一次方程式": 250,
    "比例と反比例": 300,
    "平面図形": 350,
    "空間図形": 400,
    "データの分布と統計的探究": 200,
    "ことがらの起こりやすさ": 200,
    # 中学2年
    "式の計算": 450,
    "連立方程式": 500,
    "1次関数": 550,
    "平行と合同": 500,
    "三角形と四角形": 550,
    "確率": 450,
    "データの分布の比較": 350,
    # 中学3年
    "多項式": 650,
    "平方根": 700,
    "2次方程式": 750,
    "関数 y=ax^2": 700,
    "相似な図形": 800,
    "円": 750,
    "三平方の定理": 900,
    "標本調査": 600,
}

# ② 小単元キーワードスコア: 0〜400
LESSON_KEYWORD_SCORE: list[tuple[str, int]] = [
    (r"融合|発展|入試|最短距離|総合", 400),
    (r"利用|活用|応用|文章題|身の回り", 250),
    (r"性質|定理|逆|証明", 100),
    (r"計算|解き方|求め方|変換", 50),
    (r"意味|導入|基本|概念|定義", 0),
]

# 正規化定数（implementation_plan.md より）
RAW_MIN = 100   # 最小: 中1正負の数 + 導入 + 計算
RAW_MAX = 4300  # 最大: 大単元(900) + 小単元(400) + 証明(800) + 図なし(300)
                #        + フルステップ(500) + フル桁数(300) + 複合単元(500) + 入試構成(600)


def normalize(raw: int) -> int:
    """Raw Score → 1-100 に正規化（形式ボーナス含まず）"""
    return max(1, min(100, round(1 + 99 * (raw - RAW_MIN) / (RAW_MAX - RAW_MIN))))


def denormalize(score_1_100: int) -> int:
    """1-100 → Raw Score に逆変換"""
    return round(RAW_MIN + (RAW_MAX - RAW_MIN) * (score_1_100 - 1) / 99)


def compute_raw_y_base(large_unit: str, title: str) -> int:
    """大単元 + 小単元タイトルから Raw Score を算出する"""
    # 大単元スコア（部分一致で最も高いものを採用）
    lu_score = 300  # デフォルト
    for key, score in LARGE_UNIT_RAW_SCORE.items():
        if key in large_unit or large_unit in key:
            lu_score = score
            break

    # 小単元キーワードスコア
    lesson_score = 0
    for pattern, score in LESSON_KEYWORD_SCORE:
        if re.search(pattern, title):
            lesson_score = score
            break

    return lu_score + lesson_score


def compute_y_base(
    grade: str,
    domain: str,
    title: str,
    order_in_large_unit: int,
    total_in_large_unit: int,
    large_unit: str = "",
) -> int:
    """1〜100 スケールの y_base を返す（後方互換ラッパー）"""
    raw = compute_raw_y_base(large_unit or domain, title)
    return normalize(raw)
