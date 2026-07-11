"""登録機構（実装設計 §3 core/registry.py・§6.1）。

recipe / solver / template / checker / frame / gate を名前で登録し、spec から
名前参照させる。これが Open-Closed（F-19）の追加単位：新能力の追加は「登録関数を
足す」であり、既存コード・スペックの diff は 0 行。

core は本レジストリの *枠組み* のみを持つ。実体（数学の recipe 等）は pack が
import 時に `@register_*` で登録する。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:  # pragma: no cover - 型のみ
    from engine.core.contracts import MR, CellContext, FrameProtocol, VisualPlan
    from engine.core.rng import Rng


class RecipeFn(Protocol):
    """構成的ジェネレータ（answer-first）。CellContext + Rng → MR。"""
    def __call__(self, ctx: "CellContext", rng: "Rng") -> "MR": ...


class GateFn(Protocol):
    """検証ゲート。(mr/text/svg, ctx) → (ok, detail)。段は登録時に指定。"""
    def __call__(self, obj: object, ctx: "CellContext") -> tuple[bool, str]: ...


class _Registry:
    def __init__(self) -> None:
        self._recipes: dict[str, RecipeFn] = {}
        # recipe が「提供できる概念タグ集合」を宣言（spec_lint R6・題材ズレ検出）
        self._recipe_concepts: dict[str, frozenset[str]] = {}
        self._solvers: dict[str, Callable[..., object]] = {}
        self._templates: dict[str, object] = {}      # 版付き T1 テンプレ
        self._checkers: dict[str, Callable[..., object]] = {}
        self._frames: dict[str, "FrameProtocol"] = {}
        self._visual_builders: dict[str, Callable[..., object]] = {}
        # 段別ゲート: stage -> [(name, fn), ...]（登録順 = 実行順）
        self._gates: dict[str, list[tuple[str, GateFn]]] = {"mr": [], "text": [], "visual": []}
        self._hint_generators: dict[str, Callable[..., list[str]]] = {}

    # ---- recipe ----
    def register_recipe(
        self, name: str, *, provides_concepts: list[str] | None = None
    ) -> Callable[[RecipeFn], RecipeFn]:
        def deco(fn: RecipeFn) -> RecipeFn:
            if name in self._recipes:
                raise ValueError(f"recipe 名の重複登録: {name}")
            self._recipes[name] = fn
            self._recipe_concepts[name] = frozenset(provides_concepts or [])
            return fn
        return deco

    def recipe(self, name: str) -> RecipeFn:
        if name not in self._recipes:
            raise KeyError(f"未登録 recipe: {name}")
        return self._recipes[name]

    def recipe_concepts(self, name: str) -> frozenset[str]:
        return self._recipe_concepts.get(name, frozenset())

    def has_recipe(self, name: str) -> bool:
        return name in self._recipes

    # ---- solver ----
    def register_solver(self, name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def deco(fn: Callable[..., object]) -> Callable[..., object]:
            self._solvers[name] = fn
            return fn
        return deco

    def solver(self, name: str) -> Callable[..., object]:
        if name not in self._solvers:
            raise KeyError(f"未登録 solver: {name}")
        return self._solvers[name]

    # ---- template ----
    def register_template(self, name: str, template: object) -> None:
        self._templates[name] = template

    def template(self, name: str) -> object:
        if name not in self._templates:
            raise KeyError(f"未登録 template: {name}")
        return self._templates[name]

    def has_template(self, name: str) -> bool:
        return name in self._templates

    # ---- checker ----
    def register_checker(self, name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def deco(fn: Callable[..., object]) -> Callable[..., object]:
            self._checkers[name] = fn
            return fn
        return deco

    def checker(self, name: str) -> Callable[..., object]:
        if name not in self._checkers:
            raise KeyError(f"未登録 checker: {name}")
        return self._checkers[name]

    def has_checker(self, name: str) -> bool:
        return name in self._checkers

    # ---- frame ----
    def register_frame(self, frame: "FrameProtocol") -> "FrameProtocol":
        self._frames[frame.form] = frame
        return frame

    def frame(self, form: str) -> "FrameProtocol":
        if form not in self._frames:
            raise KeyError(f"未登録 frame(form): {form}")
        return self._frames[form]

    def has_frame(self, form: str) -> bool:
        return form in self._frames

    # ---- visual builder ----
    def register_visual(self, name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
        def deco(fn: Callable[..., object]) -> Callable[..., object]:
            self._visual_builders[name] = fn
            return fn
        return deco

    def visual(self, name: str) -> Callable[..., object]:
        if name not in self._visual_builders:
            raise KeyError(f"未登録 visual builder: {name}")
        return self._visual_builders[name]

    def has_visual(self, name: str) -> bool:
        return name in self._visual_builders

    # ---- hint generator ----
    def register_hint(self, name: str) -> Callable[[Callable[..., list[str]]], Callable[..., list[str]]]:
        def deco(fn: Callable[..., list[str]]) -> Callable[..., list[str]]:
            self._hint_generators[name] = fn
            return fn
        return deco

    def hint(self, name: str) -> Callable[..., list[str]]:
        if name not in self._hint_generators:
            raise KeyError(f"未登録 hint generator: {name}")
        return self._hint_generators[name]

    def has_hint(self, name: str) -> bool:
        return name in self._hint_generators

    # ---- gate ----
    def register_gate(self, stage: str, name: str) -> Callable[[GateFn], GateFn]:
        if stage not in self._gates:
            raise ValueError(f"未知の段: {stage}（mr/text/visual）")
        def deco(fn: GateFn) -> GateFn:
            self._gates[stage].append((name, fn))
            return fn
        return deco

    def gates(self, stage: str) -> list[tuple[str, GateFn]]:
        return list(self._gates.get(stage, []))

    # ---- utility ----
    def clear(self) -> None:
        """テスト用にレジストリを初期化。"""
        self.__init__()  # type: ignore[misc]


# プロセス全体で共有する単一レジストリ
REGISTRY = _Registry()

# デコレータのショートカット（pack から import される）
register_recipe = REGISTRY.register_recipe
register_solver = REGISTRY.register_solver
register_checker = REGISTRY.register_checker
register_frame = REGISTRY.register_frame
register_visual = REGISTRY.register_visual
register_hint = REGISTRY.register_hint
register_gate = REGISTRY.register_gate

__all__ = [
    "REGISTRY", "RecipeFn", "GateFn",
    "register_recipe", "register_solver", "register_checker",
    "register_frame", "register_visual", "register_hint", "register_gate",
]
