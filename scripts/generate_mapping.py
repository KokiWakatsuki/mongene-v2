"""177 lesson 全体のマッピング JSON を生成する（§21.1, §28）

LLM を用いず、curriculum_math.json + §24 y_base ルール + キーワード推論で
決定論的に生成する。mapping_seed.json の手動エントリは尊重する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from apps.api.src.core.constants import JHS_GRADE_FROM_LABEL
from apps.api.src.core.difficulty.base_difficulty import compute_y_base

REPO_ROOT = Path(__file__).resolve().parent.parent
CURRICULUM_PATH = REPO_ROOT / "master_data" / "curriculum_math.json"
SEED_PATH = REPO_ROOT / "master_data" / "mapping_seed.json"
OUTPUT_PATH = REPO_ROOT / "master_data" / "mapping.json"


# (regex, blueprint_id) — 上から順に最初にマッチしたものを採用
BLUEPRINT_RULES: List[Tuple[str, str]] = [
    (r"証明|合同|相似", "ProofStructure"),
    (r"作図|軌跡", "ConstructionStructure"),
    (r"確率|樹形図|平均|中央値|最頻値|度数|相対度数|ヒストグラム|箱ひげ|四分位|標本|起こりやすさ|データの分布", "DataProbabilityStructure"),
    (r"規則性|数列|マッチ棒|並べ方|個数の規則", "SequencePatternStructure"),
    (r"動点|点 P|時間 t", "MovingPointStructure"),
    (r"角度|円周角|中心角|接弦角|内接四角形|内角|外角|平行線.*角|錯角|同位角", "AngleCalculationStructure"),
    # 関数系を幾何系より先に判定（「グラフ」と「面積」が同居しないよう）
    (r"比例|反比例|一次関数|二次関数|放物線|y\s*=\s*ax|交点|グラフ", "FunctionGeometryFusionStructure"),
    (r"くり抜|切断|回転体|展開図", "BasicDifferenceStructure"),
    (r"面積|体積|表面積|周$|円周|弧", "BasicGeometryMeasurementStructure"),
    (r"文章題|利用|問題を解く|身の回り", "WordProblemStructure"),
]


# キーワード → required_tags の追記
TAG_RULES: List[Tuple[str, List[str]]] = [
    (r"正の数|負の数|整数|自然数", ["number"]),
    (r"分数", ["fraction"]),
    (r"平方根|根号|有理化", ["square_root"]),
    (r"多項式|展開|因数分解", ["polynomial"]),
    (r"一次方程式|方程式の解き方", ["linear_equation"]),
    (r"二次方程式|解の公式", ["quadratic_equation"]),
    (r"連立方程式", ["linear_equation"]),
    (r"不定方程式", ["diophantine"]),
    (r"比例式|比の値", ["proportion_equation"]),
    (r"反比例", ["inverse_proportion"]),
    (r"一次関数|比例", ["linear_function"]),
    (r"二次関数|放物線|y=ax\^2", ["quadratic_function"]),
    (r"三平方|ピタゴラス", ["pythagorean"]),
    (r"相似", ["similarity"]),
    (r"合同", ["congruence"]),
    (r"円周角|中心角", ["circle_angles"]),
    (r"作図", ["construction"]),
    (r"確率|樹形図", ["probability"]),
    (r"ヒストグラム|度数分布|箱ひげ|四分位", ["data_analysis"]),
    (r"標本|母集団", ["sampling_survey"]),
    (r"数列|規則性", ["sequence"]),
    (r"立体|空間|柱|錐|球|多面体", ["space_geometry"]),
    (r"三角形|四角形|多角形|平行四辺形|台形|ひし形|正方形|長方形", ["plane_geometry"]),
    (r"円$|円の", ["plane_geometry", "circle"]),
]


# Blueprint → デフォルトの atom_constraints
DEFAULT_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "BasicCalculationStructure": {
        "NumberAtom": {"allow_negative": True, "max_value": 30, "force_fraction": False},
        "EquationAtom": {"degree": 1, "max_coefficient": 10, "is_integer_solution": True},
        "PolynomialAtom": {"max_degree": 2, "num_variables": 1, "max_coefficient": 8},
    },
    "WordProblemStructure": {
        "EquationAtom": {"degree": 1, "max_coefficient": 10, "is_integer_solution": True},
    },
    "BasicGeometryMeasurementStructure": {
        "PolygonAtom": {"polygon_type": "triangle", "max_side_length": 10},
        "CircleAtom": {"is_sector": False, "max_radius": 10},
        "PrismAtom": {"is_cube": False, "max_height": 10, "base_shape_type": "square"},
        "PyramidAtom": {"max_base_side": 6, "max_height": 6},
        "SphereAtom": {"max_radius": 6, "integer_radius": True},
    },
    "BasicDifferenceStructure": {
        "PrismAtom": {"is_cube": False, "max_height": 10},
        "PyramidAtom": {"max_base_side": 3, "max_height": 3, "hide_height": False},
    },
    "FunctionGeometryFusionStructure": {
        "LinearFuncAtom": {"max_slope": 5, "force_integer_slope": True},
        "QuadraticFuncAtom": {"max_a_value": 3, "is_pure_form": True},
    },
    "MovingPointStructure": {
        "PolygonAtom": {"polygon_type": "rectangle", "max_side_length": 10},
        "MovingPointAtom": {"num_points": 1, "path_type": "edge_traversal", "speed_range": (1, 3)},
    },
    "AngleCalculationStructure": {
        "LineAngleAtom": {"relation_type": "alternate", "angle_range": (30, 150)},
        "CircleAngleAtom": {},
        "PolygonAtom": {"polygon_type": "triangle"},
    },
    "ConstructionStructure": {
        "PointAtom": {"range_x": (-5, 5), "range_y": (-5, 5), "integer_only": True},
    },
    "ProofStructure": {
        "PolygonAtom": {"polygon_type": "triangle", "max_side_length": 10},
    },
    "DataProbabilityStructure": {
        "EventAtom": {"event_type": "dice", "num_trials": 1, "with_replacement": True},
        "DataSetAtom": {"data_size": 20, "value_range": (0, 100), "distribution_type": "uniform"},
        "SampleAtom": {"population_size": 1000, "sample_size": 50},
    },
    "SequencePatternStructure": {
        "SequenceAtom": {"pattern_type": "arithmetic", "min_terms_required": 3},
    },
}


VISUAL_BY_BLUEPRINT: Dict[str, str] = {
    "BasicCalculationStructure": "NullRenderer",
    "WordProblemStructure": "NullRenderer",
    "BasicGeometryMeasurementStructure": "2D_Geometry_Renderer",
    "BasicDifferenceStructure": "3D_Renderer",
    "FunctionGeometryFusionStructure": "Graph_Renderer",
    "MovingPointStructure": "2D_Geometry_Renderer",
    "AngleCalculationStructure": "2D_Geometry_Renderer",
    "ConstructionStructure": "2D_Geometry_Renderer",
    "ProofStructure": "2D_Geometry_Renderer",
    "DataProbabilityStructure": "Tree_Renderer",
    "SequencePatternStructure": "NullRenderer",
}


SUPPORTED_FORMS: Dict[str, List[str]] = {
    # calculation = 数値・式が全部与えられ計算するだけ
    # word_problem = 場面設定から式を立てる
    # proof = 論理的証明
    "BasicCalculationStructure": ["calculation"],
    "WordProblemStructure": ["word_problem"],
    "BasicGeometryMeasurementStructure": ["calculation", "word_problem"],
    "BasicDifferenceStructure": ["word_problem"],           # くり抜き文脈が必須
    "FunctionGeometryFusionStructure": ["calculation", "word_problem"],
    "MovingPointStructure": ["word_problem"],               # 動点の時間文脈が必須
    "AngleCalculationStructure": ["calculation"],           # 図が与えられ角度を求めるだけ
    "ConstructionStructure": ["calculation"],
    "ProofStructure": ["proof"],
    "DataProbabilityStructure": ["calculation", "word_problem"],
    "SequencePatternStructure": ["calculation", "word_problem"],
    "PythagoreanStructure": ["calculation", "word_problem"],
    "PythagoreanSpaceStructure": ["word_problem"],          # 空間図形の文脈が必須
}


def infer_blueprint(domain: str, large_unit: str, title: str) -> str:
    text = f"{large_unit} {title}"
    for pattern, blueprint_id in BLUEPRINT_RULES:
        if re.search(pattern, text):
            return blueprint_id
    # フォールバック: domain 別
    if domain == "数と式":
        return "BasicCalculationStructure"
    if domain == "関数":
        return "FunctionGeometryFusionStructure"
    if domain == "図形":
        return "BasicGeometryMeasurementStructure"
    if domain == "データの活用":
        return "DataProbabilityStructure"
    return "BasicCalculationStructure"


def infer_clean_config(title: str, blueprint_id: str) -> Dict[str, Any]:
    """lesson 内容に応じた is_clean_override（§35.5 細粒度設定）

    決定論モードでは Phase 5 のためにレギュレーション緩めで開始するが、
    実 LLM 接続時に運用品質を保つために細粒度値を用意する。
    """
    text = title
    # 平方根・有理化 lesson は分母 5 桁・根号中 10000 まで許容
    if re.search(r"平方根|有理化|根号", text):
        return {"max_denominator_digits": 5, "max_radicand": 10000}
    # 整数計算 lesson は分母 1 桁限定
    if re.search(r"正の数・負の数|加法|減法|乗法|除法|整数", text):
        return {"max_denominator_digits": 1, "max_radicand": 100}
    # 円周率を含む lesson は分母 3 桁
    if re.search(r"円|おうぎ|球|円周|弧", text):
        return {"max_denominator_digits": 3, "max_radicand": 1000}
    # 文字式・展開・因数分解 は中程度
    if re.search(r"多項式|展開|因数分解", text):
        return {"max_denominator_digits": 3, "max_radicand": 1000}
    # デフォルト
    return {"max_denominator_digits": 3, "max_radicand": 1000}


def infer_required_tags(title: str, large_unit: str, blueprint_id: str) -> List[str]:
    text = f"{large_unit} {title}"
    tags: List[str] = []
    for pattern, t in TAG_RULES:
        if re.search(pattern, text):
            for tag in t:
                if tag not in tags:
                    tags.append(tag)
    if not tags:
        # Blueprint 別の最小タグ
        if blueprint_id == "BasicCalculationStructure":
            tags = ["number"]
    return tags


def generate_mapping(strict: bool = False) -> Dict[str, Any]:
    """マッピング JSON を生成する

    strict=False（デフォルト）: 決定論モード（LLM モック）用に dedup/is_clean を無効化
    strict=True: 実 LLM 接続時の本番モード。lesson 別 is_clean_override + dedup 有効
    """
    curriculum = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    seed_raw = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    seed: Dict[str, Any] = {k: v for k, v in seed_raw.items() if not k.startswith("_") and isinstance(v, dict)}

    mapping: Dict[str, Any] = {}

    for grade_entry in curriculum:
        grade_label: str = grade_entry["grade"]
        grade_int: int = JHS_GRADE_FROM_LABEL[grade_label]
        for domain in grade_entry["domains"]:
            domain_name = domain["domain_name"]
            for lu in domain["large_units"]:
                lu_name = lu["large_unit_name"]
                # large_unit 内の small_units 総数を集計
                small_units_in_lu: List[Tuple[str, int, int]] = []
                for mu in lu["middle_units"]:
                    for su in mu["small_units"]:
                        small_units_in_lu.append((su["title"], su["lesson_number"], 0))
                total_in_lu = len(small_units_in_lu)

                order = 0
                for mu in lu["middle_units"]:
                    for su in mu["small_units"]:
                        order += 1
                        lesson_number: int = su["lesson_number"]
                        title: str = su["title"]
                        lesson_id = f"g{grade_int}_l{lesson_number}"

                        if lesson_id in seed:
                            entry = dict(seed[lesson_id])
                            # seed エントリに domain / large_unit が欠落していたら curriculum から補完
                            entry.setdefault("domain", domain_name)
                            entry.setdefault("large_unit", lu_name)
                            if strict:
                                entry.setdefault(
                                    "is_clean_override",
                                    infer_clean_config(entry.get("title", ""), entry.get("execute_blueprint", "")),
                                )
                                # dedup は strict モードで有効
                            else:
                                entry.setdefault("is_clean_override", {"disabled": True})
                                # dedup は有効のまま（時刻ベース seed で再生成が異なる問題を返す）
                            mapping[lesson_id] = entry
                            continue

                        blueprint_id = infer_blueprint(domain_name, lu_name, title)
                        y_base = compute_y_base(
                            grade=grade_label,
                            domain=domain_name,
                            title=title,
                            order_in_large_unit=order,
                            total_in_large_unit=total_in_lu,
                        )
                        required_tags = infer_required_tags(title, lu_name, blueprint_id)
                        atom_constraints = DEFAULT_CONSTRAINTS.get(blueprint_id, {})
                        visual = VISUAL_BY_BLUEPRINT.get(blueprint_id, "NullRenderer")
                        forms = SUPPORTED_FORMS.get(blueprint_id, ["calculation"])

                        entry = {
                            "title": title,
                            "grade": grade_int,
                            "lesson_number": lesson_number,
                            "domain": domain_name,
                            "large_unit": lu_name,
                            "execute_blueprint": blueprint_id,
                            "required_tags": required_tags,
                            "optional_tags": [],
                            "atom_constraints": atom_constraints,
                            "visual_component": visual,
                            "y_base": y_base,
                            "supported_forms": forms,
                        }
                        if strict:
                            entry["is_clean_override"] = infer_clean_config(title, blueprint_id)
                        else:
                            entry["is_clean_override"] = {"disabled": True}
                            # dedup は有効のまま
                        mapping[lesson_id] = entry

    return mapping


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict",
        action="store_true",
        help="実 LLM 接続時の本番モード（lesson 別 is_clean_override + dedup 有効）",
    )
    args = parser.parse_args()
    mapping = generate_mapping(strict=args.strict)
    OUTPUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    mode = "strict" if args.strict else "lenient"
    print(f"{len(mapping)} lessons written to {OUTPUT_PATH} (mode={mode})")


if __name__ == "__main__":
    main()
