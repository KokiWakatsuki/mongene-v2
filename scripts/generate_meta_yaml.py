"""§16.1.1〜16.1.4 のメタ YAML を atoms/verb/blueprint レジストリから生成

LLM が参照するための機械可読メタデータを出力する。
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Dict, List

import yaml

# Atom/Verb/Blueprint をレジストリに登録するため全モジュールを import
from apps.api.src.atoms.noun import (  # noqa: F401
    circle_angle_atom, circle_atom, data_set_atom, equation_atom, event_atom,
    inverse_func_atom, line_angle_atom, linear_func_atom, moving_point_atom,
    number_atom, point_atom, polygon_atom, polynomial_atom, prism_atom,
    proportion_atom, pyramid_atom, quadratic_func_atom, sample_atom,
    sequence_atom, sphere_atom, square_root_atom,
)
from apps.api.src.atoms.verb import (  # noqa: F401
    analyze_data_verb, calculate_arithmetic_verb, calculate_probability_verb,
    construct_geometry_verb, cutout_verb, estimate_population_verb,
    find_angle_verb, find_divisors_verb, form_shape_verb,
    generalize_formula_verb, intersect_verb, locus_verb,
    measure_geometry_verb, prove_algebraic_verb, prove_geometry_verb,
    slice_solid_verb, solve_eq_verb, solve_linear_diophantine_verb,
    transform_shape_verb, unfold_net_verb,
)
from apps.api.src.atoms.registry import _NOUN_REGISTRY, _VERB_REGISTRY
from apps.api.src.blueprints.registry import _builder_map

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER = REPO_ROOT / "master_data"


def _category_for_atom(cls_name: str) -> str:
    if cls_name in {"NumberAtom", "PolynomialAtom", "SquareRootAtom", "EquationAtom", "ProportionAtom"}:
        return "A"  # 数と式
    if cls_name in {"PointAtom", "LinearFuncAtom", "InverseFuncAtom", "QuadraticFuncAtom"}:
        return "C"  # 関数
    if cls_name in {"PolygonAtom", "CircleAtom", "LineAngleAtom", "CircleAngleAtom",
                    "PrismAtom", "PyramidAtom", "SphereAtom", "MovingPointAtom"}:
        return "B"  # 図形
    if cls_name in {"EventAtom", "DataSetAtom", "SampleAtom"}:
        return "D"  # データの活用
    return "E"  # 数列


def build_atoms_yaml() -> Dict[str, Any]:
    atoms: List[Dict[str, Any]] = []
    for name, cls in sorted(_NOUN_REGISTRY.items()):
        sig = inspect.signature(cls.__init__)
        properties = [p for p in sig.parameters.keys() if p != "self"]
        atoms.append({
            "class_name": name,
            "category": _category_for_atom(name),
            "default_tags": list(getattr(cls, "tags", [])),
            "properties": properties,
        })
    return {"atoms": atoms}


def build_verbs_yaml() -> Dict[str, Any]:
    verbs: List[Dict[str, Any]] = []
    for name, cls in sorted(_VERB_REGISTRY.items()):
        arity = getattr(cls, "arity", 2)
        verbs.append({
            "class_name": name,
            "arity": arity if isinstance(arity, int) else str(arity),
            "accepted_noun_types": list(getattr(cls, "accepted_noun_types", [])),
            "tags": list(getattr(cls, "tags", [])),
        })
    return {"verbs": verbs}


def build_blueprints_yaml() -> Dict[str, Any]:
    blueprints: List[Dict[str, Any]] = []
    for bp_id, builder in sorted(_builder_map().items()):
        bp = builder()
        blueprints.append({
            "blueprint_id": bp.blueprint_id,
            "blueprint_version": bp.blueprint_version,
            "supported_forms": list(bp.supported_forms),
            "story_required": bp.story_required,
            "noun_slots": {
                slot_name: {
                    "accepted_tags": list(slot.accepted_tags),
                    "accepted_noun_types": list(slot.accepted_noun_types),
                    "required": slot.required,
                }
                for slot_name, slot in bp.noun_slots.items()
            },
            "main_verbs": [type(inv.verb).__name__ for inv in bp.verb_invocations],
            "visual_component": bp.visual_slot.component_type if bp.visual_slot else None,
        })
    return {"blueprints": blueprints}


def build_visual_components_yaml() -> Dict[str, Any]:
    return {
        "visual_components": [
            {"name": "NullRenderer", "library": "-", "output_format": "empty"},
            {"name": "2D_Geometry_Renderer", "library": "svgwrite", "output_format": "SVG"},
            {"name": "3D_Renderer", "library": "matplotlib", "output_format": "SVG"},
            {"name": "Graph_Renderer", "library": "matplotlib", "output_format": "SVG"},
            {"name": "Table_&_Chart_Renderer", "library": "matplotlib+html", "output_format": "SVG+HTML"},
            {"name": "Tree_Renderer", "library": "svgwrite", "output_format": "SVG"},
        ]
    }


def main() -> None:
    targets = {
        "atoms.yaml": build_atoms_yaml(),
        "verbs.yaml": build_verbs_yaml(),
        "blueprints.yaml": build_blueprints_yaml(),
        "visual_components.yaml": build_visual_components_yaml(),
    }
    for fname, data in targets.items():
        path = MASTER / fname
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        print(f"  {fname}: {len(next(iter(data.values())))} entries -> {path}")


if __name__ == "__main__":
    main()
