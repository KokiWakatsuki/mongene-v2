"""データ契約（要件 §4 / 実装設計 §4）— すべての層が参照する共有型。

このモジュールは *科目非依存* のカーネルに属する。math を import してはならない
（§3 依存規律）。全下流関数は `CellContext` を第一引数に取り（H7）、意図
（form/purpose/level）を型で運ぶ。

pydantic v2 + `from __future__ import annotations` で厳密契約を表現する。
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, Union, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# 語彙（Literal）
# ---------------------------------------------------------------------------
Purpose = Literal["base", "remedial", "variant"]  # final は M2
VariantMode = Literal["A", "B", "C"]
Tier = Literal["T1", "T2", "T3"]
VisualReq = Literal["none", "required", "optional"]

# Unsupported 理由コード（要件 §4.1 / 実装 §4.1）
UnsupportedCode = Literal[
    "unit_not_found",
    "form_not_supported",
    "level_not_supported",
    "purpose_not_supported",
    "cause_not_found",
    "verification_exhausted",  # F-14: ゲート全滅
    "supply_exhausted",        # avoid/variant の再抽選が有界内で尽きた（§5.3）
    "not_implemented",         # スペック未制作（capabilities に出ない）
]


# ---------------------------------------------------------------------------
# Request / Options / Unsupported
# ---------------------------------------------------------------------------
class VariantRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_ref: str
    mode: VariantMode


class GenerateOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause_id: str | None = None            # remedial 用（誤答要因ID）
    target_concepts: list[str] = Field(default_factory=list)  # 概念絞り込み
    variant_of: VariantRef | None = None   # variant 用
    avoid: list[str] = Field(default_factory=list)            # problem_ref のリスト


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str                           # "math"
    unit: str                              # "g2_l25"（curriculum の ID）
    form: str                              # "find_value"（語彙の正 = curriculum）
    level: int                             # band 絶対値 1..4
    purpose: Purpose = "base"
    seed: int | None = None                # None → エンジンが採番し必ず応答に含める
    options: GenerateOptions = Field(default_factory=GenerateOptions)


class Unsupported(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: UnsupportedCode
    detail: str = ""


# ---------------------------------------------------------------------------
# MR（中間表現）— §4.2
# ---------------------------------------------------------------------------
class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: str                # ソルバ演算名（例 "solve_linear_eq"）
    args: list[str] = Field(default_factory=list)  # 入力（表示可能形）
    result_srepr: str      # sympy srepr（機械厳密形 = moat）
    result_display: str    # 表示形（例 "x = 3"）
    narration: str         # 「なぜこの計算か」1文（T1/T3・ヒントの素材）


class SymbolicAnswer(BaseModel):  # calculation / find_value / word_problem
    model_config = ConfigDict(extra="forbid")
    kind: Literal["symbolic"] = "symbolic"
    srepr: str             # sympy srepr（moat）
    display: str


class ChoiceAnswer(BaseModel):    # knowledge（用語・真偽・選択）
    model_config = ConfigDict(extra="forbid")
    kind: Literal["choice"] = "choice"
    correct: str
    distractors: list[str] = Field(default_factory=list)  # 妨害選択肢
    fact_id: str           # 検証の根拠（curriculum の fact テーブル ID）


class Feature(BaseModel):         # graph_table「かく」の検証可能な特徴点
    model_config = ConfigDict(extra="forbid")
    kind: str              # "point" | "intercept" | "slope" | ...
    srepr: str             # 機械厳密形
    display: str


class GraphAnswer(BaseModel):     # graph_table「かく」・construction
    model_config = ConfigDict(extra="forbid")
    kind: Literal["graph"] = "graph"
    features: list[Feature] = Field(default_factory=list)
    solution_svg_ref: str = ""    # 模範解答図（問題図とは別部品・開示制御対象）


# form により直和で拡張（H4 の form 差の受け皿）。判別は kind フィールド。
AnswerPayload = Union[SymbolicAnswer, ChoiceAnswer, GraphAnswer]


class SubQuestionMR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str                     # "(1)"
    asked: str                     # 問う対象（frame 語彙 §6.3）
    answer: AnswerPayload = Field(discriminator="kind")
    steps: list[Step] = Field(default_factory=list)  # 採点粒度: 式変形1ステップ=1要素
    concept_tags: list[str] = Field(default_factory=list)  # 必須・非空
    cause_tags: list[str] = Field(default_factory=list)    # 検証できる誤答要因ID


class VisualElement(BaseModel):
    """図の描画要素宣言（幾何的リーク規則 §6.4 用）。"""
    model_config = ConfigDict(extra="forbid")
    kind: str              # "grid" | "axis" | "line" | "point" | "polygon" | ...
    attrs: dict[str, Any] = Field(default_factory=dict)


class VisualPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str = "default"                 # "grid" | "sketch" | ...
    labels: list[str] = Field(default_factory=list)   # 図に描いてよい文字列（whitelist）
    elements: list[VisualElement] = Field(default_factory=list)


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipe: str            # recipe 名 + 版
    recipe_version: str = "v1"
    spec_version: str = "v1"
    git_commit: str = ""


class MR(BaseModel):
    model_config = ConfigDict(extra="forbid")
    signature: str                         # 構造シグネチャ（§4.4）
    family: str                            # "math.g2_l25.find_value"
    level: int
    purpose: Purpose
    seed: int
    params: dict[str, Any] = Field(default_factory=dict)   # recipe が構成した具体値（正規化可能）
    given: dict[str, str] = Field(default_factory=dict)    # 問題文に出す「与えるもの」（表示形）
    context_slots: dict[str, str] = Field(default_factory=dict)  # variant B の題材スロット（dup_key に算入しない）
    sub_questions: list[SubQuestionMR] = Field(default_factory=list)
    visual_plan: VisualPlan | None = None  # frame が要求する場合のみ非 None
    provenance: Provenance


# ---------------------------------------------------------------------------
# 出力（Problem）— §4.2。フィールド名は要件 §4.2 に一致（contract テストで検証）
# ---------------------------------------------------------------------------
class SubQuestionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    prompt_text: str                       # 小問の問い
    answer: AnswerPayload = Field(discriminator="kind")
    solution_steps: list[Step] = Field(default_factory=list)
    explanation: str = ""                  # steps の narration+display を決定論テンプレで結合（§7.3）
    hints: list[str] = Field(default_factory=list)   # steps_prefix
    concept_tags: list[str] = Field(default_factory=list)
    cause_tags: list[str] = Field(default_factory=list)


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: str
    unit: str
    form: str
    level: int


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested: Coordinate                  # 元リクエスト座標
    resolved: Coordinate                   # 解決先座標（remedial 時は戻り先。通常は requested と同じ）
    purpose: Purpose
    seed: int
    signature: str
    concept_tags: list[str] = Field(default_factory=list)
    cause_tags: list[str] = Field(default_factory=list)
    provenance: Provenance
    render_keys: dict[str, str] = Field(default_factory=dict)  # 再現情報（T2/T3 キャッシュキー）


class Problem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_ref: str                       # sha256(provenance + seed + render_keys)
    problem_text: str
    visual_svg: str | None = None          # 問題図のみ（模範解答図は AnswerPayload 側）
    sub_questions: list[SubQuestionOut] = Field(default_factory=list)
    meta: Meta


GenerateResult = Union[Problem, Unsupported]


# ---------------------------------------------------------------------------
# Frame / CellContext（意図の運搬 H7）
# ---------------------------------------------------------------------------
@runtime_checkable
class FrameProtocol(Protocol):
    """form の実装（pack 側）が満たすプロトコル。core は本 Protocol にのみ依存する。"""

    form: str
    given_vocab: frozenset[str]
    asked_vocab: frozenset[str]
    visual: VisualReq          # none | required | optional

    def check_mr(self, mr: MR) -> tuple[bool, str]:
        """MR が frame 語彙・制約に適合するか（Q2）。"""
        ...

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        """asked と両立しない描画要素の種別（幾何的リーク規則 §6.4）。"""
        ...


class SpecLevel(BaseModel):
    """FamilySpec の 1 レベルブロック（§4.3）。ローダが構築する。"""
    model_config = ConfigDict(extra="forbid")
    level: int
    signature: str
    recipe: str
    params: dict[str, Any] = Field(default_factory=dict)
    given: list[str] = Field(default_factory=list)
    asked: list[str] = Field(default_factory=list)
    visual: VisualReq = "none"
    text: dict[str, Any] = Field(default_factory=dict)   # {tier, template}
    hints: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)
    cause_tags: list[str] = Field(default_factory=list)


class SpecFamily(BaseModel):
    """FamilySpec の family メタ（§4.3）。"""
    model_config = ConfigDict(extra="forbid")
    family: str                            # "math.g2_l25.find_value"
    form: str
    source_desc: str = ""                  # input_spec の desc/example 転記（R8）
    concepts_default: list[str] = Field(default_factory=list)
    levels: dict[str, SpecLevel] = Field(default_factory=dict)  # key = str(level)
    remedial_default_level: int | None = None


class CellContext(BaseModel):
    """resolve() だけが作れる不変オブジェクト。全下流関数の第一引数（H7）。

    frame は pack の実体だが型は FrameProtocol（core は Protocol にのみ依存）。
    """
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True, frozen=True)

    subject: str
    family: str
    form: str
    unit: str
    level: int
    purpose: Purpose
    frame: FrameProtocol                   # pack 実体（Protocol 経由）
    spec_family: SpecFamily
    spec_level: SpecLevel
    # そのセルが参照してよい概念・要因辞書の部分ビュー
    curriculum_view: dict[str, Any] = Field(default_factory=dict)
    # 元リクエスト座標（remedial 時は resolved と異なる）
    requested: Coordinate
    options: GenerateOptions = Field(default_factory=GenerateOptions)


__all__ = [
    "Purpose", "VariantMode", "Tier", "VisualReq", "UnsupportedCode",
    "VariantRef", "GenerateOptions", "GenerateRequest", "Unsupported",
    "Step", "SymbolicAnswer", "ChoiceAnswer", "Feature", "GraphAnswer", "AnswerPayload",
    "SubQuestionMR", "VisualElement", "VisualPlan", "Provenance", "MR",
    "SubQuestionOut", "Coordinate", "Meta", "Problem", "GenerateResult",
    "FrameProtocol", "SpecLevel", "SpecFamily", "CellContext",
]
