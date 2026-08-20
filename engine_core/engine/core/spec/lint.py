"""spec_lint（実装設計 §4.3・§8.1）— FamilySpec の静的検査 R1〜R9。

`engine.core` は `engine.packs` / `engine.curriculum` を import してはならない
（§3 依存規律）。したがって registry・curriculum ビュー（概念ID集合・要因ID集合）・
frame 辞書はすべて **引数で注入** される（グローバル依存を持たない）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from engine.core.contracts import SpecFamily, SpecLevel
from engine.core.registry import REGISTRY, _Registry
from engine.core.rng import DomainError, validate_domain

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import FrameProtocol


@dataclass
class LintError:
    rule: str                  # "R1".."R9"
    message: str
    level_key: str | None = None


def _iter_params_values(params: dict[str, Any]) -> list[Any]:
    """R3 の検査対象: params の各トップレベル値。"""
    return list(params.values())


def lint_family(
    spec: SpecFamily,
    *,
    registry: _Registry = REGISTRY,
    concepts: set[str] | None = None,
    causes: set[str] | None = None,
    frames: dict[str, "FrameProtocol"] | None = None,
) -> list[LintError]:
    """FamilySpec を検査し `LintError` のリストを返す（例外は投げない）。

    concepts/causes/frames が None の場合、それらに依存する規則（R4/R5 の一部）は
    スキップする（注入されなければ検査しない）。
    """
    errors: list[LintError] = []

    seen_signatures: dict[str, str] = {}  # signature -> 最初に見た level_key

    for level_key, level in spec.levels.items():
        errors.extend(_lint_r1_registered_names(level, level_key, registry))
        errors.extend(_lint_r2_signature_dup(level, level_key, seen_signatures))
        errors.extend(_lint_r3_domain(level, level_key))
        errors.extend(_lint_r4_tags_exist(spec, level, level_key, concepts, causes))
        errors.extend(_lint_r5_frame_conformance(spec.form, level, level_key, frames))
        errors.extend(_lint_r6_recipe_concepts(spec, level, level_key, registry))
        errors.extend(_lint_r7_hints(level, level_key))
        errors.extend(_lint_r9_parts_exist(level, level_key, registry))

    # R8 は family 単位の規則（levels の有無によらず1回だけ検査）
    errors.extend(_lint_r8_source_desc(spec))

    return errors


# ---------------------------------------------------------------------------
# R1: 未登録の recipe/template/checker 名
# ---------------------------------------------------------------------------
def _lint_r1_registered_names(level: SpecLevel, level_key: str, registry: _Registry) -> list[LintError]:
    errors: list[LintError] = []
    if not registry.has_recipe(level.recipe):
        errors.append(LintError("R1", f"未登録の recipe: {level.recipe!r}", level_key))

    template_name = level.text.get("template") if isinstance(level.text, dict) else None
    if template_name is not None and not registry.has_template(template_name):
        errors.append(LintError("R1", f"未登録の template: {template_name!r}", level_key))

    # checker は SpecLevel に専用フィールドが無いため、あれば params/text 経由の任意フィールドを見る
    # （M0 時点では SpecLevel に checker 参照フィールドが無い。将来 checkers リストが追加されたら
    #  ここに検査を足す。現状は no-op。）
    checker_names = getattr(level, "checkers", None)
    if checker_names:
        for name in checker_names:
            if not registry.has_checker(name):
                errors.append(LintError("R1", f"未登録の checker: {name!r}", level_key))

    return errors


# ---------------------------------------------------------------------------
# R2: 同一 family 内で signature 重複
# ---------------------------------------------------------------------------
def _lint_r2_signature_dup(
    level: SpecLevel, level_key: str, seen_signatures: dict[str, str]
) -> list[LintError]:
    errors: list[LintError] = []
    sig = level.signature
    if sig in seen_signatures:
        errors.append(
            LintError(
                "R2",
                f"signature 重複: {sig!r}（{seen_signatures[sig]} と {level_key} で重複）",
                level_key,
            )
        )
    else:
        seen_signatures[sig] = level_key
    return errors


# ---------------------------------------------------------------------------
# R3: params の各値がドメイン記法として妥当か（validate_domain）
# ---------------------------------------------------------------------------
def _lint_r3_domain(level: SpecLevel, level_key: str) -> list[LintError]:
    errors: list[LintError] = []
    for value in _iter_params_values(level.params):
        try:
            validate_domain(value)
        except DomainError as e:
            errors.append(LintError("R3", f"params のドメイン記法が不正: {e}", level_key))
    return errors


# ---------------------------------------------------------------------------
# R4: concept_tags / cause_tags / concepts_default が curriculum に実在するか
# ---------------------------------------------------------------------------
def _lint_r4_tags_exist(
    spec: SpecFamily,
    level: SpecLevel,
    level_key: str,
    concepts: set[str] | None,
    causes: set[str] | None,
) -> list[LintError]:
    errors: list[LintError] = []

    if concepts is not None:
        effective_concepts = level.concept_tags or spec.concepts_default
        for c in effective_concepts:
            if c not in concepts:
                errors.append(LintError("R4", f"未知の concept: {c!r}", level_key))

    if causes is not None:
        for c in level.cause_tags:
            if c not in causes:
                errors.append(LintError("R4", f"未知の cause: {c!r}", level_key))

    return errors


# ---------------------------------------------------------------------------
# R5: form と frame の整合
#
# frames は {form: FrameProtocol} で注入される。当該 family.form に対応する frame が
# 無ければ検査不能としてスキップする（frames が None の場合も同様）。
# ---------------------------------------------------------------------------
def _lint_r5_frame_conformance(
    spec_form: str,
    level: SpecLevel,
    level_key: str,
    frames: dict[str, "FrameProtocol"] | None,
) -> list[LintError]:
    errors: list[LintError] = []
    if frames is None:
        return errors
    frame = frames.get(spec_form)
    if frame is None:
        # form に対応する frame が注入されていない → 検査不能（スキップ）
        return errors

    for g in level.given:
        if g not in frame.given_vocab:
            errors.append(LintError("R5", f"given の語彙が frame に無い: {g!r}（form={spec_form!r}）", level_key))
    for a in level.asked:
        if a not in frame.asked_vocab:
            errors.append(LintError("R5", f"asked の語彙が frame に無い: {a!r}（form={spec_form!r}）", level_key))

    # visual 宣言と frame.visual の矛盾検査:
    # frame.visual="none" なのに spec.visual="required"（または "optional"）は不可。
    if frame.visual == "none" and level.visual != "none":
        errors.append(
            LintError(
                "R5",
                f"frame.visual=none なのに spec.visual={level.visual!r} が宣言されている（form={spec_form!r}）",
                level_key,
            )
        )

    return errors


# ---------------------------------------------------------------------------
# R6: 題材ズレの静的検出（recipe が宣言した concept 集合の部分集合検査）
# ---------------------------------------------------------------------------
def _lint_r6_recipe_concepts(
    spec: SpecFamily, level: SpecLevel, level_key: str, registry: _Registry
) -> list[LintError]:
    errors: list[LintError] = []
    if not registry.has_recipe(level.recipe):
        return errors  # R1 で既に報告済み

    declared = registry.recipe_concepts(level.recipe)
    if not declared:
        # recipe が概念集合を宣言していない（未宣言）→ スキップ
        return errors

    effective_concepts = set(level.concept_tags or spec.concepts_default)
    if not effective_concepts.issubset(declared):
        extra = effective_concepts - declared
        errors.append(
            LintError(
                "R6",
                f"レベルの概念集合が recipe 宣言の部分集合でない: {sorted(extra)}"
                f"（recipe={level.recipe!r} が提供する集合={sorted(declared)}）",
                level_key,
            )
        )
    return errors


# ---------------------------------------------------------------------------
# R7: hints が steps_prefix のみで空になり得る場合はテンプレ定義ヒント必須
#
# design のニュアンス: 本来は「そのレベルの steps 期待長が 2 未満になり得る場合」を
# 判定すべきだが、SpecLevel は steps 期待長の宣言フィールドを持たない（M0 時点で
# contracts.py に追加しない方針）。ここでは過剰実装を避け、
# 「hints が空リストなら R7 エラー」という最小判定に留める。
# ---------------------------------------------------------------------------
def _lint_r7_hints(level: SpecLevel, level_key: str) -> list[LintError]:
    errors: list[LintError] = []
    if not level.hints:
        errors.append(LintError("R7", "hints が空: steps_prefix のみでは不十分な場合のテンプレ定義ヒントが無い", level_key))
    return errors


# ---------------------------------------------------------------------------
# R8: source_desc が非空
# ---------------------------------------------------------------------------
def _lint_r8_source_desc(spec: SpecFamily) -> list[LintError]:
    errors: list[LintError] = []
    if not spec.source_desc.strip():
        errors.append(LintError("R8", "source_desc が空（input_spec の desc/example 転記が必須）", None))
    return errors


# ---------------------------------------------------------------------------
# R9: formulas / scenes が recipe の棚にある名前か
# ---------------------------------------------------------------------------
def _lint_r9_parts_exist(level: SpecLevel, level_key: str, registry: _Registry) -> list[LintError]:
    """設計書が選んだ数式・文型が、その recipe の棚に実在するか。

    ★**綴り違いを黙って通してはいけない。** 通すと「絞ったつもりで絞れていない」
    設計書ができ、生成物を見るまで気づけない（絞りが効いていないことは、
    出てきた問題を数えないと分からない）。棚が空の recipe に欄を書いた場合も同じ扱い。
    """
    errors: list[LintError] = []
    for field, declared in (
        ("formulas", registry.recipe_formulas(level.recipe)),
        ("scenes", registry.recipe_scenes(level.recipe)),
    ):
        chosen = getattr(level, field)
        if not chosen:
            continue
        if not declared:
            errors.append(LintError(
                "R9",
                f"{field} を書いているが recipe={level.recipe!r} は棚を宣言していない"
                f"（register_recipe の provides_{field} が空）",
                level_key,
            ))
            continue
        unknown = [name for name in chosen if name not in declared]
        if unknown:
            errors.append(LintError(
                "R9",
                f"{field} に棚に無い名前: {unknown}（棚={sorted(declared)}）",
                level_key,
            ))
    return errors


__all__ = ["LintError", "lint_family"]
