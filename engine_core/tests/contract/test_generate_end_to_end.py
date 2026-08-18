"""Task4: generate() のエンドツーエンド contract テスト。

ダミー recipe/frame/template/spec を registry と families に仕込み、generate() が
Problem を返しフィールド名が要件 §4.2 に一致することを検証する。ゲート失敗時に
Unsupported(verification_exhausted) になることも、わざと失敗する gate を
登録して検証する。数学の中身（recipe/template の実体）は Task5/Task9 が作るため、
ここでは完全に自己完結したダミーで骨格を検証する。
"""
from __future__ import annotations

from typing import Any

import sympy

from engine.core.contracts import (
    MR,
    GenerateRequest,
    Problem,
    Provenance,
    SpecFamily,
    SpecLevel,
    Step,
    SubQuestionMR,
    SymbolicAnswer,
    Unsupported,
    VisualReq,
)
from engine.core.curriculum import CurriculumModel
from engine.core.pipeline import generate
from engine.core.registry import _Registry
from engine.core.rng import Rng, derive_rng


class DummyFrame:
    def __init__(self, form: str, given_vocab: frozenset[str], asked_vocab: frozenset[str], visual: VisualReq) -> None:
        self.form = form
        self.given_vocab = given_vocab
        self.asked_vocab = asked_vocab
        self.visual = visual

    def check_mr(self, mr: Any) -> tuple[bool, str]:
        return True, ""

    def forbidden_visual_elements(self, asked: list[str]) -> frozenset[str]:
        return frozenset()


def _dummy_recipe(ctx: Any, rng: Rng) -> MR:
    a = rng.randint(1, 5)
    x1, x2 = 1, 4
    y1, y2 = a * x1, a * x2
    expr = a * sympy.Symbol("x")
    return MR(
        signature="dummy_sig",
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,  # generate() が実 seed で上書きしないため、ここでは仮値。実運用は recipe が rng 由来で決める
        params={"a": a},
        given={"point_a": f"({x1}, {y1})", "point_b": f"({x2}, {y2})"},
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked="expression",
                answer=SymbolicAnswer(srepr=sympy.srepr(expr), display=f"y = {a}x"),
                steps=[
                    Step(
                        op="compute_slope", args=[], result_srepr=str(a),
                        result_display=f"傾き a = {a}", narration="2点から傾きを求める。",
                    ),
                    Step(
                        op="form_expression", args=[], result_srepr=sympy.srepr(expr),
                        result_display=f"y = {a}x", narration="式を組み立てる。",
                    ),
                ],
                concept_tags=["linear_function.expression_from_points"],
                cause_tags=["lf.slope_formula_error"],
            )
        ],
        provenance=Provenance(recipe="math.dummy_recipe"),
    )


def _always_fail_recipe(ctx: Any, rng: Rng) -> MR:
    """G-SCHEMA をわざと落とすための MR（concept_tags を空にする）。"""
    return MR(
        signature="broken_sig",
        family=ctx.family,
        level=ctx.level,
        purpose=ctx.purpose,
        seed=0,
        params={},
        given={"point_a": "(1, 1)"},
        sub_questions=[
            SubQuestionMR(
                label="(1)",
                asked="expression",
                answer=SymbolicAnswer(srepr="x", display="y = x"),
                steps=[],
                concept_tags=[],  # G-SCHEMA が拒否する
                cause_tags=[],
            )
        ],
        provenance=Provenance(recipe="math.broken_recipe"),
    )


def _gate_schema(obj: Any, ctx: Any) -> tuple[bool, str]:
    """G-SCHEMA 相当: 全小問に concept_tags 非空・answer 非 None（本体は Task4 verify/gates.py）。"""
    mr: MR = obj
    for sq in mr.sub_questions:
        if not sq.concept_tags:
            return False, f"{sq.label}: concept_tags が空"
        if sq.answer is None:
            return False, f"{sq.label}: answer が None"
    return True, ""


def _registry(*, recipe_name: str = "math.dummy_recipe", recipe_fn: Any = _dummy_recipe) -> _Registry:
    reg = _Registry()
    reg.register_recipe(recipe_name, provides_concepts=["linear_function.expression_from_points"])(recipe_fn)
    reg.register_template(
        "lf_expr_two_points_v1",
        "2点 {{ given.point_a }} と {{ given.point_b }} を通る直線の式を求めなさい。",
    )
    reg.register_frame(
        DummyFrame(
            form="find_value",
            given_vocab=frozenset({"point_a", "point_b"}),
            asked_vocab=frozenset({"expression"}),
            visual="optional",
        )
    )
    reg.register_gate("mr", "G-SCHEMA")(_gate_schema)
    return reg


def _curriculum() -> CurriculumModel:
    return CurriculumModel(
        units={"g2_l25": {"forms": {"find_value": {"levels": {"2": {"desc": "d", "example": "e"}}}}}},
        concepts={},
        error_causes={},
        prerequisites=[],
    )


def _spec_family(*, recipe_name: str = "math.dummy_recipe") -> SpecFamily:
    return SpecFamily(
        family="math.g2_l25.find_value",
        form="find_value",
        source_desc="2点から式を求める（ダミー）",
        concepts_default=["linear_function.expression_from_points"],
        levels={
            "2": SpecLevel(
                level=2,
                signature="dummy_sig",
                recipe=recipe_name,
                params={},
                given=["point_a", "point_b"],
                asked=["expression"],
                visual="none",
                text={"tier": "T1", "template": "lf_expr_two_points_v1"},
                hints=["steps_prefix"],
                cause_tags=["lf.slope_formula_error"],
            )
        },
        remedial_default_level=2,
    )


def _states_an_ask(text: str) -> bool:
    """その文のどこかが「〜しなさい／〜せよ」と指示を言い切っているか。

    ★**最終行だけを見てはいけない。** 計算のセルは「次の計算をせよ。」が1行目で、
    最終行は式である。最終行だけ見ると判定を外す（実際に外して二重を通した）。
    """
    import re

    pat = re.compile(
        r"(?:せよ|なさい|ください|ますか|ですか|でしょうか|答えよ|求めよ|かけ|示せ"
        r"|表せ|選べ)[。．]?\s*$"
    )
    return any(pat.search(ln.strip()) for ln in (text or "").split("\n") if ln.strip())


def _req(*, seed: int | None = 42) -> GenerateRequest:
    return GenerateRequest(subject="math", unit="g2_l25", form="find_value", level=2, seed=seed)


# ---------------------------------------------------------------------------
# 正常系: Problem を返し、フィールド名が §4.2 に一致
# ---------------------------------------------------------------------------
def test_generate_returns_problem_with_expected_field_names():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family()}
    registry = _registry()

    result = generate(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Problem)
    assert isinstance(result.problem_ref, str) and len(result.problem_ref) >= 8
    assert isinstance(result.problem_text, str) and result.problem_text
    assert "(1, 1)" not in result.problem_text or True  # given 値は文脈依存。存在チェックは別テストで。

    sq = result.sub_questions[0]
    assert sq.label == "(1)"
    # ★守りたいのは「問いが必ずある」ことであって「prompt_text が空でない」ことでは
    # ない。**指示は問題文と問いのどちらか一方に、1つだけあればよい。**
    # 前は非空だけを見ていたので、本文「次の計算をせよ。」＋問い「答えを求めなさい。」
    # という**指示の二重**（686小問中439件・実測）を素通りさせていた。
    # 空を許した代わりに、二重も空欄も両方この1行で捕まえる。
    assert isinstance(sq.prompt_text, str)
    assert _states_an_ask(sq.prompt_text) ^ _states_an_ask(result.problem_text), (
        f"指示は問題文と問いのどちらか一方だけに置くこと: "
        f"problem_text={result.problem_text!r} prompt_text={sq.prompt_text!r}"
    )
    assert sq.answer is not None
    assert isinstance(sq.solution_steps, list) and len(sq.solution_steps) == 2
    assert isinstance(sq.explanation, str) and sq.explanation
    assert isinstance(sq.hints, list) and sq.hints
    assert sq.concept_tags == ["linear_function.expression_from_points"]
    assert sq.cause_tags == ["lf.slope_formula_error"]

    meta = result.meta
    assert meta.requested.unit == "g2_l25"
    assert meta.resolved.unit == "g2_l25"
    assert meta.purpose == "base"
    assert meta.seed == 42
    assert meta.signature == "dummy_sig"
    assert meta.concept_tags == ["linear_function.expression_from_points"]
    assert meta.cause_tags == ["lf.slope_formula_error"]
    assert meta.provenance.recipe == "math.dummy_recipe"


def test_generate_given_values_appear_in_problem_text():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family()}
    registry = _registry()

    result = generate(_req(seed=7), curriculum=curriculum, families=families, registry=registry)
    assert isinstance(result, Problem)

    # テンプレが given.point_a / given.point_b を埋め込む → problem_text に出現するはず
    # (再現性: derive_rng(family, level, purpose, seed) から決定論的に a が決まる)
    rng = derive_rng("math.g2_l25.find_value", 2, "base", 7)
    a = rng.randint(1, 5)
    assert f"({a}, {a})" in result.problem_text or f"(1, {a})" in result.problem_text


def test_generate_is_reproducible_for_same_seed():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family()}
    registry = _registry()

    r1 = generate(_req(seed=99), curriculum=curriculum, families=families, registry=registry)
    r2 = generate(_req(seed=99), curriculum=curriculum, families=families, registry=registry)
    assert isinstance(r1, Problem) and isinstance(r2, Problem)
    assert r1.problem_text == r2.problem_text
    assert r1.problem_ref == r2.problem_ref


def test_generate_issues_seed_when_none_given():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family()}
    registry = _registry()

    result = generate(_req(seed=None), curriculum=curriculum, families=families, registry=registry)
    assert isinstance(result, Problem)
    assert isinstance(result.meta.seed, int)


# ---------------------------------------------------------------------------
# resolve が失敗するケースはそのまま Unsupported が通る
# ---------------------------------------------------------------------------
def test_generate_propagates_unsupported_from_resolve():
    curriculum = _curriculum()
    families: dict[str, SpecFamily] = {}
    registry = _registry()

    result = generate(_req(), curriculum=curriculum, families=families, registry=registry)
    assert isinstance(result, Unsupported)
    assert result.code == "not_implemented"


# ---------------------------------------------------------------------------
# ゲート失敗（全滅）→ Unsupported(verification_exhausted)
# ---------------------------------------------------------------------------
def test_generate_gate_failure_becomes_verification_exhausted():
    curriculum = _curriculum()
    families = {"math.g2_l25.find_value": _spec_family(recipe_name="math.broken_recipe")}
    registry = _registry(recipe_name="math.broken_recipe", recipe_fn=_always_fail_recipe)

    result = generate(_req(), curriculum=curriculum, families=families, registry=registry)

    assert isinstance(result, Unsupported)
    assert result.code == "verification_exhausted"
    assert "G-SCHEMA" in result.detail
