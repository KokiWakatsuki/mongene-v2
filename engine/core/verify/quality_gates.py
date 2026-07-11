"""動的検証ゲート本体（実装設計 §5・§6・§8.2）— Task6。

`engine/core/verify/gates.py` が持つのは *枠組み*（`run_gates`・段バンドル・
`G-SCHEMA`）のみ。本モジュールはフル Q ゲート（G-SIG/G-FP/G-Q1/G-Q2/G-Q7/G-Q7r/
G-Q5t/G-GND/G-STY/G-Q5v）の実体を提供する。

グローバル副作用を避けるため、モジュール import だけでは何も登録しない。
`install_quality_gates(registry)` を明示的に呼んだときだけ `registry.register_gate`
経由で登録する（既存のダミーテスト・隔離テストを壊さないための方針）。

依存規律（§3）: `engine.packs.math` は import しない（漏洩/接地ロジックは
`apps/api/src/core/evaluation/*` を参考に、ロジックのみ self-contained で
再実装する。import はしない）。
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction
from typing import TYPE_CHECKING, Any

from engine.core.registry import REGISTRY, _Registry
from engine.core.signature import fingerprint_hash

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, AnswerPayload, CellContext, Solution
    from engine.core.verify.gates import TextStageInput, VisualStageInput


# ---------------------------------------------------------------------------
# 数値正規化（apps/api/src/core/evaluation/number_normalize.py を参考に
# self-contained 再実装。import はしない — §3 依存規律とは別に、core は
# apps 層にも依存してはならないため）。
# ---------------------------------------------------------------------------
_MINUS_VARIANTS = {
    "−": "-",  # MINUS SIGN
    "－": "-",  # FULLWIDTH HYPHEN-MINUS
    "‐": "-",  # HYPHEN
    "–": "-",  # EN DASH
    "—": "-",  # EM DASH
}

_LATEX_FRAC_RE = re.compile(r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}")
_LATEX_LEFT_RIGHT_RE = re.compile(r"\\(?:left|right)\s*([(){}\[\]|.]|\\\{|\\\})")
_LATEX_STRIP_COMMANDS = re.compile(r"\\(?:mathrm|mathbf|text|displaystyle|,|;|!|quad|qquad)\b")


def normalize_math_text(text: str) -> str:
    """数値比較のための正規化。全角→半角、マイナス異体字統一、LaTeX 装飾除去。"""
    if text is None:
        return ""
    s = str(text)
    for variant, ascii_minus in _MINUS_VARIANTS.items():
        s = s.replace(variant, ascii_minus)
    s = unicodedata.normalize("NFKC", s)
    for variant, ascii_minus in _MINUS_VARIANTS.items():
        s = s.replace(variant, ascii_minus)

    prev = None
    while prev != s:
        prev = s
        s = _LATEX_FRAC_RE.sub(lambda m: f"({m.group(1)}/{m.group(2)})", s)

    s = _LATEX_LEFT_RIGHT_RE.sub(
        lambda m: m.group(1) if m.group(1) not in (r"\{", r"\}") else ("{" if m.group(1) == r"\{" else "}"), s
    )
    s = _LATEX_STRIP_COMMANDS.sub(" ", s)
    s = s.replace("$$", "").replace("$", "")
    s = s.replace(r"\(", "").replace(r"\)", "")
    s = s.replace(r"\[", "").replace(r"\]", "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


_NUMBER_RE = re.compile(r"-\s*\([^()]*\)|-?\d+(?:\.\d+)?(?:/\d+)?")
_LEADING_MINUS_PAREN_RE = re.compile(r"^-\s*\((?P<inner>.*)\)$")


def extract_numbers(text: str) -> list[str]:
    """正規化済みテキストから数値トークン（整数・小数・分数 a/b）を抽出する。"""
    normalized = normalize_math_text(text)
    return _NUMBER_RE.findall(normalized)


def _to_fraction(token: str) -> Fraction | None:
    token = token.strip()
    negate = False
    changed = True
    while changed:
        changed = False
        m = _LEADING_MINUS_PAREN_RE.match(token)
        if m:
            token = m.group("inner").strip()
            negate = not negate
            changed = True
            continue
        if token.startswith("(") and token.endswith(")"):
            inner = token[1:-1].strip()
            if inner:
                token = inner
                changed = True
    if not token:
        return None
    try:
        if "/" in token:
            num_str, den_str = token.split("/", 1)
            result = Fraction(num_str) / Fraction(den_str)
        else:
            result = Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None
    return -result if negate else result


def contains_number(text: str, value: str) -> bool:
    """`text` 中に（正規化後の）数値 `value` が出現するか。"""
    target = _to_fraction(normalize_math_text(value))
    if target is None:
        return normalize_math_text(value) in normalize_math_text(text)
    for tok in extract_numbers(text):
        cand = _to_fraction(tok)
        if cand is not None and abs(float(cand - target)) <= 1e-9:
            return True
    return False


# ---------------------------------------------------------------------------
# G-SIG（mr段）
# ---------------------------------------------------------------------------
def _gate_sig(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    if mr.signature != ctx.spec_level.signature:
        return False, f"mr.signature={mr.signature!r} != spec_level.signature={ctx.spec_level.signature!r}"
    return True, ""


# ---------------------------------------------------------------------------
# G-FP（mr段）: 同一 signature ⇔ 同一 fingerprint の安定性。
# プロセス内キャッシュ（signature -> fp_hash）。テスト用に reset 可能。
# ---------------------------------------------------------------------------
_fp_cache: dict[str, str] = {}


def reset_fp_cache() -> None:
    """G-FP のプロセス内キャッシュを初期化する（テスト用）。"""
    _fp_cache.clear()


def _gate_fp(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    fp_hash = fingerprint_hash(mr)
    seen = _fp_cache.get(mr.signature)
    if seen is None:
        _fp_cache[mr.signature] = fp_hash
        return True, ""
    if seen != fp_hash:
        return False, f"signature={mr.signature!r} の fingerprint が不安定: 既出={seen!r} 今回={fp_hash!r}"
    return True, ""


# ---------------------------------------------------------------------------
# G-Q1（mr段）: double-solve。
#
# 対応規約: M0 の縦串は1小問構成が前提のため、`checker(mr)` が返す Solution.answer
# を `mr.sub_questions[0].answer` と比較する（代表小問）。複数小問へ一般化する場合は
# checker が sub_questions と同数の Solution 相当を返す形へ拡張し、対応する
# sub_questions[i] と突き合わせる設計にできるが、M0 では [0] 固定でよい。
# ---------------------------------------------------------------------------
def _answers_match(a: "AnswerPayload", b: "AnswerPayload") -> tuple[bool, str]:
    from engine.core.contracts import ChoiceAnswer, GraphAnswer, SymbolicAnswer

    if a.kind != b.kind:
        return False, f"answer.kind 不一致: {a.kind!r} != {b.kind!r}"
    if isinstance(a, SymbolicAnswer) and isinstance(b, SymbolicAnswer):
        if a.srepr != b.srepr:
            return False, f"symbolic.srepr 不一致: {a.srepr!r} != {b.srepr!r}"
        return True, ""
    if isinstance(a, ChoiceAnswer) and isinstance(b, ChoiceAnswer):
        if a.correct != b.correct or a.fact_id != b.fact_id:
            return False, (
                f"choice 不一致: correct={a.correct!r}/{b.correct!r} "
                f"fact_id={a.fact_id!r}/{b.fact_id!r}"
            )
        return True, ""
    if isinstance(a, GraphAnswer) and isinstance(b, GraphAnswer):
        set_a = {f.srepr for f in a.features}
        set_b = {f.srepr for f in b.features}
        if set_a != set_b:
            return False, f"graph.features(srepr集合) 不一致: {sorted(set_a)} != {sorted(set_b)}"
        return True, ""
    return False, f"未知の answer.kind: {a.kind!r}"


def _make_gate_q1(registry: _Registry) -> Any:
    """checker 参照先レジストリを閉じ込めた G-Q1 を作る（隔離テスト用に registry を捕捉）。"""

    def gate(obj: object, ctx: "CellContext") -> tuple[bool, str]:
        mr: "MR" = obj  # type: ignore[assignment]
        checker_name = f"{mr.provenance.recipe}.double_solve"
        if not registry.has_checker(checker_name):
            return False, f"double_solve checker 未登録: {checker_name!r}（H5 強制・未登録は不合格）"
        if not mr.sub_questions:
            return False, "sub_questions が空"
        checker = registry.checker(checker_name)
        solution: "Solution" = checker(mr)  # type: ignore[assignment]
        ok, detail = _answers_match(solution.answer, mr.sub_questions[0].answer)
        if not ok:
            return False, f"double-solve 不一致: {detail}"
        return True, ""

    return gate


# ---------------------------------------------------------------------------
# G-Q2（mr段）: frame.check_mr(mr)
# ---------------------------------------------------------------------------
def _gate_q2(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    ok, detail = ctx.frame.check_mr(mr)
    return ok, detail


# ---------------------------------------------------------------------------
# G-Q7（mr段）: concept_tags/cause_tags が curriculum_view に実在
# ---------------------------------------------------------------------------
def _gate_q7(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    concept_ids: set[str] = ctx.curriculum_view.get("concept_ids", set())
    cause_ids: set[str] = ctx.curriculum_view.get("cause_ids", set())

    for sq in mr.sub_questions:
        if not sq.concept_tags:
            return False, f"{sq.label}: concept_tags が空"
        unknown_concepts = [c for c in sq.concept_tags if c not in concept_ids]
        if unknown_concepts:
            return False, f"{sq.label}: concept_tags が curriculum に無い: {unknown_concepts}"
        unknown_causes = [c for c in sq.cause_tags if c not in cause_ids]
        if unknown_causes:
            return False, f"{sq.label}: cause_tags が curriculum に無い: {unknown_causes}"
    return True, ""


# ---------------------------------------------------------------------------
# G-Q7r（mr段・remedial時のみ発火）: remedial_target_concepts の被覆
# ---------------------------------------------------------------------------
def _gate_q7r(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    mr: "MR" = obj  # type: ignore[assignment]
    if ctx.purpose != "remedial":
        return True, ""
    target_concepts = ctx.curriculum_view.get("remedial_target_concepts")
    if not target_concepts:
        return True, ""

    covered: set[str] = set()
    for sq in mr.sub_questions:
        covered.update(sq.concept_tags)

    missing = [c for c in target_concepts if c not in covered]
    if missing:
        return False, f"remedial_target_concepts が被覆されていない: {missing}"
    return True, ""


# ---------------------------------------------------------------------------
# G-Q5t（text段）: 漏洩検査。
#
# 対象: problem_text と hints のみ（explanation/prompts は除外）。
# whitelist: mr.given の値から機械構築（given 文字列中の数値トークンを許可）。
# ---------------------------------------------------------------------------
def _answer_values(answer: "AnswerPayload") -> list[str]:
    if answer.kind == "symbolic":
        return [answer.srepr, answer.display]
    if answer.kind == "choice":
        return [answer.correct]
    if answer.kind == "graph":
        vals: list[str] = []
        for f in answer.features:
            vals.extend([f.srepr, f.display])
        return vals
    return []


def _build_given_whitelist(mr: "MR") -> set[str]:
    """given 由来の数値トークン許可集合（数値正規化した文字列表現）。"""
    whitelist: set[str] = set()
    for v in mr.given.values():
        for tok in extract_numbers(v):
            frac = _to_fraction(tok)
            if frac is not None:
                whitelist.add(str(frac))
    return whitelist


def _numeric_answer_tokens(answer: "AnswerPayload") -> list[str]:
    """answer 由来の値から「解答として出現しうる」数値トークンを抽出する。"""
    tokens: list[str] = []
    for v in _answer_values(answer):
        for tok in extract_numbers(v):
            tokens.append(tok)
    return tokens


def _expr_has_free_symbol(srepr: str) -> bool:
    """symbolic answer の srepr を復元し、自由変数（x 等）を含む「式」かを判定する。

    復元に失敗した場合は False（= 定数扱いで従来の値レベル検査に委ねる）。
    """
    try:
        import sympy

        expr = sympy.sympify(srepr)
    except Exception:  # noqa: BLE001 - 復元不能な srepr は定数扱いにフォールバック
        return False
    return bool(getattr(expr, "free_symbols", set()))


def _gate_q5t(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    stage_input: "TextStageInput" = obj  # type: ignore[assignment]
    mr = stage_input.mr
    text = stage_input.text

    whitelist = _build_given_whitelist(mr)

    check_texts: list[str] = [text.problem_text]
    for hint_list in text.hints.values():
        check_texts.extend(hint_list)
    full_text = "\n".join(check_texts)
    norm_full = normalize_math_text(full_text)

    for sq in mr.sub_questions:
        ans = sq.answer
        # 式（自由変数を含む symbolic answer, 例 y = ax + b）: 係数 a, b は §8.2 の
        # 除外規則「式中係数」に当たるため数値レベルの漏洩検査から外す。答えの式
        # そのものが丸ごと本文/ヒントに現れていないかだけを検査する（find_value の
        # ように答え＝式の場合、個々の係数は given 座標や構造語（「2点」等）と偶然
        # 一致するため、数値分解での検査は偽陽性になる）。
        if ans.kind == "symbolic" and _expr_has_free_symbol(ans.srepr):
            disp = normalize_math_text(ans.display)
            if disp and disp in norm_full:
                return False, f"{sq.label}: 解答の式 {ans.display!r} が problem_text/hints に漏洩"
            continue
        # 定数・choice・graph（答え＝具体値）: 個々の数値を given whitelist 除外の上で検査。
        for tok in _numeric_answer_tokens(ans):
            frac = _to_fraction(tok)
            norm_key = str(frac) if frac is not None else normalize_math_text(tok)
            if norm_key in whitelist:
                continue  # given 由来（係数・軸目盛など）は許可
            if contains_number(full_text, tok):
                return False, f"{sq.label}: 解答由来の値 {tok!r} が problem_text/hints に漏洩"
    return True, ""


# ---------------------------------------------------------------------------
# G-GND（text段・全tier必須）: grounding。
# ---------------------------------------------------------------------------
def _gate_gnd(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    stage_input: "TextStageInput" = obj  # type: ignore[assignment]
    mr = stage_input.mr
    text = stage_input.text

    # given の値は数値以外（記号式等）もありうるため、数値照合とプレーン部分一致の両方を試す。
    missing: list[str] = []
    for v in mr.given.values():
        if v in text.problem_text:
            continue
        if contains_number(text.problem_text, v):
            continue
        missing.append(v)
    if missing:
        return False, f"given の値が problem_text に出現しない: {missing}"

    if len(text.prompts) != len(mr.sub_questions):
        return False, f"小問数不一致: prompts={len(text.prompts)} sub_questions={len(mr.sub_questions)}"
    return True, ""


# ---------------------------------------------------------------------------
# G-STY（text段）: 最小スタイル lint。
# ---------------------------------------------------------------------------
_FORBIDDEN_CURRENCY_TOKENS = ("$", "ドル")


def _gate_sty(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    stage_input: "TextStageInput" = obj  # type: ignore[assignment]
    text = stage_input.text

    for tok in _FORBIDDEN_CURRENCY_TOKENS:
        if tok in text.problem_text:
            return False, f"通貨表記が不正: {tok!r} が problem_text に出現（円を使うこと）"

    if not text.problem_text.strip():
        return False, "problem_text が空"

    return True, ""


# ---------------------------------------------------------------------------
# G-Q5v（visual段）: 図内漏洩。
# ---------------------------------------------------------------------------
_SVG_TEXT_RE = re.compile(r"<text[^>]*>(.*?)</text>", re.DOTALL)


def _extract_svg_texts(svg: str) -> list[str]:
    return [m.group(1).strip() for m in _SVG_TEXT_RE.finditer(svg)]


def _gate_q5v(obj: object, ctx: "CellContext") -> tuple[bool, str]:
    stage_input: "VisualStageInput" = obj  # type: ignore[assignment]
    mr = stage_input.mr
    svg = stage_input.svg
    visual_plan = stage_input.visual_plan

    if visual_plan is None:
        return True, ""
    if svg is None:
        return True, ""

    svg_texts = _extract_svg_texts(svg)
    allowed_labels = set(visual_plan.labels)
    leaked_texts = [t for t in svg_texts if t and t not in allowed_labels]
    if leaked_texts:
        return False, f"svg 内テキストが visual_plan.labels に無い: {leaked_texts}"

    asked = [sq.asked for sq in mr.sub_questions]
    forbidden_kinds = ctx.frame.forbidden_visual_elements(asked)
    if forbidden_kinds:
        present_kinds = {el.kind for el in visual_plan.elements}
        violating = present_kinds & forbidden_kinds
        if violating:
            return False, f"visual_plan.elements に禁止 kind が含まれる: {sorted(violating)}"

    return True, ""


# ---------------------------------------------------------------------------
# install_quality_gates
# ---------------------------------------------------------------------------
_INSTALLED_MARKER = "_quality_gates_installed"


def install_quality_gates(registry: _Registry = REGISTRY) -> None:
    """フル Q ゲート一式を `registry` に登録する（べき等）。

    既に本関数で登録済みの registry には再登録しない（二重登録防止）。
    テストは毎回新しい `_Registry()` を作って呼ぶことを推奨（グローバル REGISTRY を
    汚さないため）。
    """
    if getattr(registry, _INSTALLED_MARKER, False):
        return

    registry.register_gate("mr", "G-SIG")(_gate_sig)
    registry.register_gate("mr", "G-FP")(_gate_fp)
    registry.register_gate("mr", "G-Q1")(_make_gate_q1(registry))
    registry.register_gate("mr", "G-Q2")(_gate_q2)
    registry.register_gate("mr", "G-Q7")(_gate_q7)
    registry.register_gate("mr", "G-Q7r")(_gate_q7r)

    registry.register_gate("text", "G-Q5t")(_gate_q5t)
    registry.register_gate("text", "G-GND")(_gate_gnd)
    registry.register_gate("text", "G-STY")(_gate_sty)

    registry.register_gate("visual", "G-Q5v")(_gate_q5v)

    setattr(registry, _INSTALLED_MARKER, True)


__all__ = [
    "install_quality_gates",
    "reset_fp_cache",
    "normalize_math_text",
    "extract_numbers",
    "contains_number",
]
