"""データ契約（要件 §4 / 実装設計 §4）— すべての層が参照する共有型。

このモジュールは *科目非依存* のカーネルに属する。math を import してはならない
（§3 依存規律）。全下流関数は `CellContext` を第一引数に取り（H7）、意図
（form/purpose/level）を型で運ぶ。

pydantic v2 + `from __future__ import annotations` で厳密契約を表現する。
"""
from __future__ import annotations

from typing import Any, Literal, Protocol, Union, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    """解き方の1手。

    ## narration と detail を分ける理由

    `narration` は**ヒントにそのまま流れる**（`t1_template._build_hints`）。ヒントは
    G-Q5t（漏洩）の検査対象なので、narration に数字を書くと答えの先出しとして落ちる
    ——これが「narration には数字を書かない」規約（鉄則⑦）。その結果、解説の指示文が
    「両辺に同じ数をたすかひくかする」のように**その問題で実際に何をしたのかを
    言わない**形になっていた。実物（佐賀県教委の学習プリント・005net）は逆に
    「両辺から ５ をひいて」と操作を名指しする。

    `detail` は**解説にしか出ない**（ヒントにも問題文にも流れない）。だから実際の値で
    操作を名指しできる。解説の行は `detail or narration` で組む＝detail を書いた手は
    そちらが勝ち、書かない手は従来どおり narration が出る。

      narration  左辺を x の項だけにするために、両辺に同じ数をたすかひくかする。（ヒント）
      detail     左辺を x の項だけにするために、両辺から 5 をひく。            （解説）
    """

    model_config = ConfigDict(extra="forbid")
    op: str                # ソルバ演算名（例 "solve_linear_eq"）
    args: list[str] = Field(default_factory=list)  # 入力（表示可能形）
    result_srepr: str      # sympy srepr（機械厳密形 = moat）
    result_display: str    # 表示形（例 "x = 3"）
    narration: str         # 「なぜこの計算か」1文（T1/T3・ヒントの素材）
    detail: str = ""       # 同じ手を**実際の値で名指しした**1文（解説だけに出る。下記）

    @field_validator("narration", "detail")
    @classmethod
    def _narration_owns_no_connective(cls, v: str) -> str:
        """narration/detail は「文の本体」だけを持つ。接続詞はレンダラの持ち物。

        T1 は解説を組むとき先頭に「まず、／次に、／最後に、」を付ける（`_connective`）。
        narration 自体が接続詞で始まると「次に、次に、乗法と除法を…」と二重になる
        （実際に arithmetic の 2 ステップで起きていた）。narration は hints にも
        そのまま流れるので、位置を語る語は narration に置けない、を契約で閉じる。
        """
        for connective in ("まず、", "次に、", "最後に、", "さらに、"):
            if v.startswith(connective):
                raise ValueError(
                    f"narration/detail は接続詞 {connective!r} で始めない"
                    f"（順序はレンダラが付ける）: {v!r}"
                )
        return v


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


class ProofStep(BaseModel):       # proof: 証明文の1行（主張＋根拠）
    """証明の1行。**構造のまま持つ**ので、採点する側が根拠の列で照合できる。

    自由文の模範解答だけを渡すより、(主張, 根拠) の列を渡すほうが、生徒の記述との
    突き合わせがぶれない（採点は別の LLM エンジンが行う前提・docs/proof_engine_design）。
    """
    model_config = ConfigDict(extra="forbid")
    claim: str                     # 「AB ＝ AD」など
    reason: str                    # 「仮定より」「3組の辺がそれぞれ等しい」など
    number: int | None = None      # 証明文中の通し番号（①②③）。結論の行は None
    refs: list[int] = Field(default_factory=list)  # この行が引く先行行の番号
    op: str = ""                   # 適用した規則の識別子（op 列＝level_sep の材料）


class ProofAnswer(BaseModel):     # proof（記述式の証明）
    """証明の答え。**証明文そのもの**と、その構造（行の列）を両方持つ。

    engine が採点するのではなく、engine は「問題・図・模範解答」を出すところまでを担う。
    `text` が解説にそのまま出る証明文で、`lines` はその構造（採点側が使う）。
    """
    model_config = ConfigDict(extra="forbid")
    kind: Literal["proof"] = "proof"
    text: str                                        # レンダリング済みの証明文
    lines: list[ProofStep] = Field(default_factory=list)
    solution_svg_ref: str = ""                       # 模範解答図（あれば）


# form により直和で拡張（H4 の form 差の受け皿）。判別は kind フィールド。
AnswerPayload = Union[SymbolicAnswer, ChoiceAnswer, GraphAnswer, ProofAnswer]


class Solution(BaseModel):
    """独立ソルバの出力（§6.2 double-solve）。問題パラメータのみから導く。

    answer は AnswerPayload（form により symbolic/choice/graph）。steps は採点粒度。
    """
    model_config = ConfigDict(extra="forbid")
    answer: AnswerPayload = Field(discriminator="kind")
    steps: list[Step] = Field(default_factory=list)


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
    # **このレベルで使ってよい数式・文型の名前**（棚から選ぶ）。
    #
    # 空なら「recipe が棚に持っているもの全部」＝これまでの動き。名前を並べると
    # そのぶんだけに絞る。**絞るためだけでなく、増やしたものを届かせるための欄**でもある
    # ——数式を10本量産しても、設計書が1本しか指せないなら出力には1本しか出ない。
    #
    # 名前は recipe が `register_recipe(provides_formulas=..., provides_scenes=...)` で
    # 宣言したものに限る（綴り違いは spec_lint R9 で落ちる。**黙って通ると、
    # 絞ったつもりで絞れていない設計書ができる**）。
    formulas: list[str] = Field(default_factory=list)
    scenes: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    given: list[str] = Field(default_factory=list)
    asked: list[str] = Field(default_factory=list)
    visual: VisualReq = "none"
    text: dict[str, Any] = Field(default_factory=dict)   # {tier, template}
    hints: list[str] = Field(default_factory=list)
    concept_tags: list[str] = Field(default_factory=list)
    cause_tags: list[str] = Field(default_factory=list)
    # **問題空間が本質的に狭いセルの、重複率の上限**（既定 0.20 を上書きする）。
    #
    # 多角形の内角・外角のように、**教材にありうる設定が十数通りしかない**単元がある。
    # 正多角形なら三角形〜正三十六角形あたりまでで、それ以上は問題集に出ない。
    # 既定の 0.20 を通そうとすると「正348角形」「1つの内角が 4860/29°」を作ることになり、
    # 実際そうなっていた（確率の「1から28までの目が出るさいころ」も同じ理由で入っていた）。
    #
    # **数を現実に戻すのが先で、重複は仕様として宣言する。** 宣言するときは
    # `dup_rate_reason` に「なぜ狭いのか」を書くこと（書かないとロードで落ちる）。
    dup_rate_max: float | None = None
    dup_rate_reason: str = ""
    # **答えの大きさの上限**（`engine/eval/answer_size.py` の既定を上書きする）。
    #
    # `{"denominator": 343, "numerator": 279}` のように、超えてよい項目だけ書く。
    # 既定は「分母12・分子100・根号の中60」で、これは**教材として書き写せる形**の線。
    # 確率は約分した分数で答えるのが作法なので、**分母が大きいのが正しい**単元がある
    # （17個から2個で 136 分の、7通りを3回くり返して 343 分の）。そこを一律の上限で
    # 落とすと、通すために場面を作り替えることになる——`dup_rate` で「正348角形」を
    # 生んだのと同じ失敗なので、**場面はそのままで上限を宣言する**。
    #
    # 宣言するときは `answer_size_reason` に「なぜ大きいのが正しいのか」を書くこと
    # （書かないとロードで落ちる）。
    answer_size_max: dict[str, int] | None = None
    answer_size_reason: str = ""
    # **問題文に出る数の、単位ごとの上限**（`engine/core/verify/statement_size.py`）。
    #
    # `{"cm": 400}` のように、超えてよい単位だけ書く。既定は「図形の寸法は 100cm まで」
    # 「道のりは 3000m まで」など、実測の「正しい側の最大」に合わせてある。
    # 標本調査の母集団（76000人）・有効数字の測定値（615cm）・体育の記録（201cm）は
    # 大きいのが正しいので、そのセルだけ宣言で通す。
    statement_size_max: dict[str, int] | None = None
    statement_size_reason: str = ""

    @model_validator(mode="after")
    def _dup_rate_needs_reason(self) -> "SpecLevel":
        if self.dup_rate_max is not None and not self.dup_rate_reason.strip():
            raise ValueError(
                "dup_rate_max を宣言するときは dup_rate_reason に理由を書くこと"
                "（問題空間が狭い根拠が無いまま閾値を上げると、質の低下が隠れる）"
            )
        if self.answer_size_max is not None and not self.answer_size_reason.strip():
            raise ValueError(
                "answer_size_max を宣言するときは answer_size_reason に理由を書くこと"
                "（答えが大きくてよい根拠が無いまま上限を上げると、質の低下が隠れる）"
            )
        if self.statement_size_max is not None and not self.statement_size_reason.strip():
            raise ValueError(
                "statement_size_max を宣言するときは statement_size_reason に理由を書くこと"
                "（問題文の数が大きくてよい根拠が無いまま上限を上げると、質の低下が隠れる）"
            )
        return self


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
    "Step", "SymbolicAnswer", "ChoiceAnswer", "Feature", "GraphAnswer", "AnswerPayload", "Solution",
    "SubQuestionMR", "VisualElement", "VisualPlan", "Provenance", "MR",
    "SubQuestionOut", "Coordinate", "Meta", "Problem", "GenerateResult",
    "FrameProtocol", "SpecLevel", "SpecFamily", "CellContext",
]
