"""T1 決定論テキストレンダラ（実装設計 §7・§7.2〜§7.5）。

T1 = Jinja2 テンプレート + 整形フィルタ（登録制）。LLM ゼロ・完全決定論。
M0 は T1 のみ実装する（T2/T3 は将来対応。tier != "T1" は本モジュールでは扱わない）。

TemplateContext は「テンプレートから参照できるもの」の契約そのもの: 公開するのは
given（表示形）/context_slots/sub_questions[].label/.asked/steps[].narration のみ。
answer・srepr・params は **属性として存在しない**——テンプレートから答えが構文的に
書けない、という構造で Q5（漏洩）を防ぐ（§7.2）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import TYPE_CHECKING, Any

import sympy
from jinja2 import DictLoader
from jinja2.sandbox import SandboxedEnvironment

from engine.core.registry import REGISTRY, _Registry

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import CellContext, Step, MR


# ---------------------------------------------------------------------------
# TemplateContext（§7.2）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SubQuestionView:
    """テンプレートに公開する小問ビュー。asked と steps の narration のみ。

    answer/srepr は載せない（Q5 を構造で防ぐ）。
    """

    label: str
    asked: str
    narrations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TemplateContext:
    """テンプレートが参照できるものの全体（§7.2 の契約）。

    公開: given / context_slots / sub_questions[].label / .asked / .narrations。
    非公開: answer・srepr・params（属性として存在しない）。
    """

    given: dict[str, str]
    context_slots: dict[str, str]
    sub_questions: list[SubQuestionView]

    @classmethod
    def from_mr(cls, mr: "MR") -> "TemplateContext":
        sqs = [
            SubQuestionView(
                label=sq.label,
                asked=sq.asked,
                narrations=[s.narration for s in sq.steps],
            )
            for sq in mr.sub_questions
        ]
        return cls(given=dict(mr.given), context_slots=dict(mr.context_slots), sub_questions=sqs)


# ---------------------------------------------------------------------------
# 整形フィルタ（登録制）§7.2
# ---------------------------------------------------------------------------
def _to_number(v: Any) -> Any:
    """sympy / Fraction / str / int / float を sympy 数値へ正規化する試み。"""
    if isinstance(v, (sympy.Basic,)):
        return v
    if isinstance(v, Fraction):
        return sympy.Rational(v.numerator, v.denominator)
    if isinstance(v, (int, float)):
        return sympy.nsimplify(v)
    if isinstance(v, str):
        try:
            return sympy.nsimplify(v)
        except Exception:
            return v
    return v


def filter_num(value: Any) -> str:
    """負数は括弧で囲む（例: -3 -> "(-3)"）。それ以外はそのまま文字列化。"""
    v = _to_number(value)
    try:
        if v.is_number and v < 0:
            return f"({sympy.sstr(v)})"
    except Exception:
        pass
    return str(sympy.sstr(v)) if isinstance(v, sympy.Basic) else str(value)


def filter_frac(value: Any) -> str:
    """既約分数表記（帯分数禁止）。整数はそのまま、分数は "a/b" 形。"""
    v = _to_number(value)
    if isinstance(v, sympy.Rational) and not isinstance(v, sympy.Integer):
        num, den = v.p, v.q
        # 帯分数禁止: 常に仮分数 "num/den" のまま出す（負数は "-num/den"）
        return f"{num}/{den}"
    return str(sympy.sstr(v)) if isinstance(v, sympy.Basic) else str(value)


def filter_pt(value: Any) -> str:
    """座標表記 "(a, b)"。tuple/list/sympy.Tuple を受け付ける。"""
    if isinstance(value, (tuple, list, sympy.Tuple)) and len(value) == 2:
        a, b = value[0], value[1]
        return f"({sympy.sstr(_to_number(a))}, {sympy.sstr(_to_number(b))})"
    return str(value)


def filter_unit(value: Any, unit: str) -> str:
    """単位付与（例: filter_unit(3, "cm") -> "3cm"）。"""
    return f"{value}{unit}"


_REGISTERED_FILTERS: dict[str, Any] = {
    "num": filter_num,
    "frac": filter_frac,
    "pt": filter_pt,
    "unit": filter_unit,
}


def _make_env() -> SandboxedEnvironment:
    env = SandboxedEnvironment(loader=DictLoader({}))
    env.filters.update(_REGISTERED_FILTERS)
    return env


# ---------------------------------------------------------------------------
# TextResult（render_text の戻り値）
# ---------------------------------------------------------------------------
@dataclass
class TextResult:
    problem_text: str
    prompts: dict[str, str] = field(default_factory=dict)
    explanations: dict[str, str] = field(default_factory=dict)
    hints: dict[str, list[str]] = field(default_factory=dict)
    render_keys: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# explanation（§7.3）: steps の narration + result_display を接続詞テンプレで結合
# 「最後に、」は最終ステップ専用（steps>=3 のとき）。steps が 4 個以上でも
# 「最後に、」が途中に出ないよう、中間ステップはすべて「次に、」で繋ぐ。
# ---------------------------------------------------------------------------
_CONNECTIVE_FIRST = "まず、"
_CONNECTIVE_MIDDLE = "次に、"
_CONNECTIVE_LAST = "最後に、"


def _connective(index: int, total: int) -> str:
    """index 番目（0 始まり）のステップに付ける接続詞を返す。

    steps=1 → 「まず、」／steps=2 → 「まず、次に、」／steps=3 → 「まず、次に、最後に、」
    steps=4 → 「まず、次に、次に、最後に、」（従来は 3 番目に「最後に、」が出るバグがあった）
    """
    if index == 0:
        return _CONNECTIVE_FIRST
    if index == total - 1 and total >= 3:
        return _CONNECTIVE_LAST
    return _CONNECTIVE_MIDDLE


def _explanation_line(index: int, total: int, step: "Step") -> str:
    """1ステップ = 1行。`result_display` は括弧に入れて narration と切る。

    以前は `f"{narration} {result_display}"` を区切りなしで連結していたため、
    result_display の末尾に次の文の接続詞が直付けされて
    「…に着目する。 冊数と値段の比次に、その量を…」と読めない文になっていた
    （narration は句点で終わるが result_display は「x = 125」のような裸の断片で
    終わるため）。括弧で閉じることで、result_display が結果でも言い換えでも文が切れる。
    """
    body = f"{_connective(index, total)}{step.narration}"
    if not step.result_display:
        return body
    return f"{body}（{step.result_display}）"


def _build_explanation(mr: "MR", sq_index: int) -> str:
    sq = mr.sub_questions[sq_index]
    total = len(sq.steps)
    return "\n".join(
        _explanation_line(i, total, step) for i, step in enumerate(sq.steps)
    )


# ---------------------------------------------------------------------------
# hints（§7.4）: steps_prefix = steps の narration を前から k 個開示（k=1..len-1）
# steps<2 の時は空にせず、テンプレ定義ヒント（spec に無ければ最小の定型ヒント1つ）を返す。
# ---------------------------------------------------------------------------
_DEFAULT_MINIMAL_HINT = "問題文の与えられた値をもう一度確認しよう。"


def _build_hints(mr: "MR", ctx: "CellContext", sq_index: int) -> list[str]:
    sq = mr.sub_questions[sq_index]
    hint_modes = ctx.spec_level.hints

    if "steps_prefix" in hint_modes and len(sq.steps) >= 2:
        return [step.narration for step in sq.steps[:-1]]

    # steps < 2、または steps_prefix が宣言されていない場合はテンプレ定義ヒントを使う
    # （**手で書かれたヒントがあれば、それがいちばん良い**ので最優先）。
    template_hints = ctx.spec_level.text.get("hints") if isinstance(ctx.spec_level.text, dict) else None
    if template_hints:
        return list(template_hints)

    # **1手で解ける問題は、前から開示できる手が無い。**「最後の手は答えを明かすので
    # ヒントにしない」という規則が候補を空にし、既定の「与えられた値をもう一度
    # 確認しよう」——何も言っていない文——に落ちていた（EVALUATION D-17・26セル）。
    #
    # narration には数字を書かない規約（鉄則⑦。値は result_display にだけ置く）が
    # あるので、1手のときはその手の narration をそのまま出してよい。
    # 「(√105)² を計算せよ」に対して「根号のついた数を2乗し、根号の中の数にもどす」と
    # 言うことになる＝**使う規則を、答えの値を明かさずに教える**。
    if "steps_prefix" in hint_modes and len(sq.steps) == 1 and sq.steps[0].narration:
        return [sq.steps[0].narration]

    return [_DEFAULT_MINIMAL_HINT]


# 小問の問いかけ。**asked は内部の符号なので、そのまま出すと日本語にならない**
# （「choice を求めなさい。」「draw_graph を求めなさい。」）。台帳で使われている
# asked をすべてここに並べる。既定にこぼすと英語が問題文に出る。
#
# **言い回しに数字を入れないこと。** 品質ゲートは本文に出る数値を given 由来のものだけに
# 限るので、「1つ選びなさい」の「1」が弾かれる。「正しいものを選びなさい。」でよい。
_ASKED_PROMPTS: dict[str, str] = {
    # 求値
    "value": "答えを求めなさい。",
    "solution": "解を求めなさい。",
    "area": "面積を求めなさい。",
    "coordinate": "座標を求めなさい。",
    "intersection": "交点の座標を求めなさい。",
    "domain_range": "変域を求めなさい。",
    "rate_of_change": "変化の割合を求めなさい。",
    "degree": "次数を答えなさい。",
    # 式
    "simplified_expr": "式を簡単にしなさい。",
    "expression": "式に表しなさい。",
    "formulation": "式に表しなさい。",
    # 選ぶ・答える
    "choice": "正しいものを選びなさい。",
    # 読み取る
    "read_point": "点の座標を読み取りなさい。",
    "read_table": "表から読み取りなさい。",
    "read_box_plot": "箱ひげ図から読み取りなさい。",
    "read_slope_intercept": "傾きと切片を読み取りなさい。",
    "read_intersection": "交点の座標を読み取りなさい。",
    "read_figure_element": "図から読み取りなさい。",
    "read_solid": "立体の図から読み取りなさい。",
    "read_position": "位置を読み取りなさい。",
    # かく
    "draw_graph": "グラフをかきなさい。",
    "draw_solid": "見取図をかきなさい。",
    "draw_transformed_polygon": "移した図形をかきなさい。",
    "draw_tree_diagram": "樹形図をかきなさい。",
    "draw_segment": "線分をかきなさい。",
    "draw_box_plot": "箱ひげ図をかきなさい。",
    "construction_steps": "作図しなさい。",
    # 記述
    "proof_text": "証明しなさい。",
}


# ---------------------------------------------------------------------------
# render_text
# ---------------------------------------------------------------------------
def render_text(mr: "MR", ctx: "CellContext", *, registry: _Registry = REGISTRY) -> TextResult:
    """MR → TextResult。tier は ctx.spec_level.text.get("tier", "T1")。M0 は T1 のみ。"""
    tier = ctx.spec_level.text.get("tier", "T1") if isinstance(ctx.spec_level.text, dict) else "T1"
    if tier != "T1":
        # T2/T3 は将来対応（実装設計 §7）。M0 スコープ外のため未実装として明示する。
        raise NotImplementedError(f"tier={tier!r} は M0 未対応（T1 のみ実装）")

    template_name = ctx.spec_level.text.get("template") if isinstance(ctx.spec_level.text, dict) else None
    if not template_name:
        raise ValueError("spec_level.text.template が指定されていない")

    template_source = registry.template(template_name)
    if not isinstance(template_source, str):
        raise TypeError(f"template {template_name!r} は文字列（Jinja2 ソース）であること")

    env = _make_env()
    jinja_template = env.from_string(template_source)
    tctx = TemplateContext.from_mr(mr)

    problem_text = jinja_template.render(
        given=tctx.given,
        context_slots=tctx.context_slots,
        sub_questions=tctx.sub_questions,
    )

    prompts: dict[str, str] = {}
    explanations: dict[str, str] = {}
    hints: dict[str, list[str]] = {}
    for i, sq in enumerate(mr.sub_questions):
        asked = tctx.sub_questions[i].asked
        prompts[sq.label] = _ASKED_PROMPTS.get(asked, f"{asked} を求めなさい。")
        explanations[sq.label] = _build_explanation(mr, i)
        hints[sq.label] = _build_hints(mr, ctx, i)

    render_keys = {"tier": "T1", "template": template_name}

    return TextResult(
        problem_text=problem_text,
        prompts=prompts,
        explanations=explanations,
        hints=hints,
        render_keys=render_keys,
    )


# ---------------------------------------------------------------------------
# render_visual: 骨格のみ（実際の SVG ビルダは Task8）
# ---------------------------------------------------------------------------
def render_visual(mr: "MR", ctx: "CellContext", *, registry: _Registry = REGISTRY) -> str | None:
    """`ctx.frame.visual` が required、または optional かつ mr.visual_plan があるときのみ実行。

    実際の SVG ビルダ（`registry.visual(name)`）が無ければ None を返す（骨格のみ）。
    visual 不要なのに mr.visual_plan が非 None なら例外（H7 の二重防御）。
    """
    frame = ctx.frame
    needs_visual = frame.visual == "required" or (frame.visual == "optional" and mr.visual_plan is not None)

    if not needs_visual:
        if mr.visual_plan is not None:
            raise ValueError(
                f"frame.visual={frame.visual!r} で図が不要なのに mr.visual_plan が設定されている（H7 二重防御）"
            )
        return None

    builder_name = ctx.spec_level.text.get("visual_builder") if isinstance(ctx.spec_level.text, dict) else None
    if not builder_name or not registry.has_visual(builder_name):
        # 図ビルダ未登録（Task8 が本体を実装する）。骨格のみのため None を返す。
        return None

    builder = registry.visual(builder_name)
    svg = builder(mr, ctx)
    return str(svg) if svg is not None else None


__all__ = [
    "TemplateContext",
    "SubQuestionView",
    "TextResult",
    "render_text",
    "render_visual",
    "filter_num",
    "filter_frac",
    "filter_pt",
    "filter_unit",
]
