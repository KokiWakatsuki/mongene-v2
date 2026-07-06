"""Phase 4: exam_l1〜exam_l7 を mapping.json に追加するスクリプト。

公立高校入試の頻出パターンから逆引きして定義した 7 つの入試対策レッスン。
既に exam_l* が存在する場合は上書きしない（--force で上書き可）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAPPING_PATH = Path(__file__).parent.parent / "master_data" / "mapping.json"

EXAM_LESSONS: dict = {
    "exam_l1": {
        "title": "一次関数と図形の融合（交点・三角形の面積）",
        "grade": 3,
        "lesson_number": 1,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["linear_function", "plane_geometry", "multi-unit"],
        "prerequisite_lessons": ["g2_l19", "g2_l21", "g2_l25", "g2_l27", "g2_l50"],
        "execute_blueprint": "FunctionGeometryFusionStructure",
        "atom_constraints": {
            "LinearFuncAtom": {"force_integer_slope": True, "max_slope": 5},
            "IntersectVerb": {},
            "TriangleAreaVerb": {},
        },
        "visual_component": "Graph_Renderer",
        "y_base": 35,
        "raw_y_base": 1750,
        "supported_forms": ["calculation", "word_problem"],
        "is_clean_override": {"disabled": True},
        "difficulty_levels": {
            "calculation": [
                {
                    "lv": 1,
                    "description": "2直線の交点座標と原点を含む三角形の面積（傾き小・整数座標）",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 2, "force_proportion": False}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "2直線の交点と座標軸切片で囲まれた三角形の面積（傾き中程度）",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 4, "max_intercept": 4}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "複数の直線で囲まれた図形の面積・面積が特定値になる条件",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 5, "max_intercept": 6}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
            "word_problem": [
                {
                    "lv": 1,
                    "description": "文章で表された2直線の交点を求め、囲まれる三角形の面積を計算",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 2}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "条件から直線の式を立て、交点座標と三角形の面積を求める応用問題",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 4, "max_intercept": 4}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "面積等分線・面積が特定値になる頂点の座標を求める発展問題",
                    "atom_constraints": {"LinearFuncAtom": {"max_slope": 5, "max_intercept": 6}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l2": {
        "title": "放物線と直線の融合（二次関数×一次関数）",
        "grade": 3,
        "lesson_number": 2,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["quadratic_function", "linear_function", "multi-unit"],
        "prerequisite_lessons": ["g3_l32", "g3_l33", "g3_l35", "g3_l37"],
        "execute_blueprint": "FunctionGeometryFusionStructure",
        "atom_constraints": {
            "QuadraticFuncAtom": {"is_pure_form": True, "max_a_value": 2},
            "LinearFuncAtom": {"force_integer_slope": True, "max_slope": 5},
            "IntersectVerb": {},
        },
        "visual_component": "Graph_Renderer",
        "y_base": 38,
        "raw_y_base": 1900,
        "supported_forms": ["calculation", "word_problem"],
        "is_clean_override": {"disabled": True},
        "difficulty_levels": {
            "calculation": [
                {
                    "lv": 1,
                    "description": "y=ax²と比例（y=mx）の交点座標と囲まれた三角形の面積",
                    "atom_constraints": {
                        "LinearFuncAtom": {"force_proportion": True, "max_slope": 2},
                        "QuadraticFuncAtom": {"max_a_value": 1},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "y=ax²と一次関数（y=mx+b）の交点座標と三角形の面積",
                    "atom_constraints": {
                        "LinearFuncAtom": {"force_proportion": False, "max_slope": 3, "max_intercept": 4},
                        "QuadraticFuncAtom": {"max_a_value": 2},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "放物線と直線の交点条件・面積が指定値になる係数を求める",
                    "atom_constraints": {
                        "LinearFuncAtom": {"max_slope": 5, "max_intercept": 6},
                        "QuadraticFuncAtom": {"max_a_value": 2},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
            "word_problem": [
                {
                    "lv": 1,
                    "description": "放物線と比例の交点から三角形の面積を求める（基本）",
                    "atom_constraints": {
                        "LinearFuncAtom": {"force_proportion": True, "max_slope": 2},
                        "QuadraticFuncAtom": {"max_a_value": 1},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "放物線と一次関数の交点から三角形の面積を求める応用問題",
                    "atom_constraints": {
                        "LinearFuncAtom": {"max_slope": 3, "max_intercept": 4},
                        "QuadraticFuncAtom": {"max_a_value": 2},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "面積等分・面積条件から直線の式を求める発展問題",
                    "atom_constraints": {
                        "LinearFuncAtom": {"max_slope": 5, "max_intercept": 6},
                        "QuadraticFuncAtom": {"max_a_value": 2},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l3": {
        "title": "動点と面積変化（一次関数・二次関数の利用）",
        "grade": 3,
        "lesson_number": 3,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["plane_geometry", "linear_function", "multi-unit"],
        "prerequisite_lessons": ["g2_l29", "g2_l19", "g2_l25", "g3_l38"],
        "execute_blueprint": "MovingPointStructure",
        "atom_constraints": {
            "PolygonAtom": {
                "n_sides": 4,
                "polygon_type": "rectangle",
                "max_side_length": 12,
                "min_side_length": 4,
            },
        },
        "visual_component": "2D_Geometry_Renderer",
        "y_base": 36,
        "raw_y_base": 1800,
        "supported_forms": ["word_problem"],
        "is_clean_override": {"disabled": True},
        "difficulty_levels": {
            "word_problem": [
                {
                    "lv": 1,
                    "description": "四角形の辺上を動く点Pが作る三角形の面積をtの一次式で表す",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 8}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "動点Pが複数の辺を移動する場合の面積変化式と最大値を求める",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 10}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "面積が指定値になる時刻tを求める（二次方程式の解が必要な場合を含む）",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 12}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l4": {
        "title": "三平方の定理と空間図形（対角線・高さ・最短距離）",
        "grade": 3,
        "lesson_number": 4,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["pythagorean", "space_geometry", "multi-unit"],
        "prerequisite_lessons": ["g3_l51", "g3_l52", "g3_l53", "g3_l55", "g3_l56"],
        "execute_blueprint": "PythagoreanSpaceStructure",
        "atom_constraints": {
            "PrismAtom": {
                "is_cube": False,
                "base_shape_type": "square",
                "max_dim": 12,
                "min_dim": 4,
            },
            "PyramidAtom": {
                "is_regular_pyramid": True,
                "base_shape": "square",
                "max_base_side": 8,
                "max_height": 10,
                "hide_height": True,
            },
        },
        "visual_component": "3D_Renderer",
        "y_base": 38,
        "raw_y_base": 1900,
        "supported_forms": ["word_problem"],
        "is_clean_override": {"disabled": True},
        "difficulty_levels": {
            "word_problem": [
                {
                    "lv": 1,
                    "description": "正四角錐の高さを三平方の定理で求め、体積を計算する",
                    "atom_constraints": {
                        "PyramidAtom": {"max_base_side": 6, "max_height": 8},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "直方体の空間対角線の長さを三次元三平方の定理で求める",
                    "atom_constraints": {
                        "PrismAtom": {"max_dim": 10},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "立体の表面上の最短距離を展開図を利用して求める",
                    "atom_constraints": {
                        "PrismAtom": {"max_dim": 12},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l5": {
        "title": "確率（複合事象・余事象）",
        "grade": 3,
        "lesson_number": 5,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["probability", "multi-unit"],
        "prerequisite_lessons": ["g2_l51", "g2_l52", "g2_l53", "g2_l54"],
        "execute_blueprint": "DataProbabilityStructure",
        "execute_blueprint_by_form": {
            "calculation": "DataProbabilityStructure",
            "word_problem": "DataProbabilityStructure",
        },
        "atom_constraints": {
            "EventAtom": {
                "event_type": "dice",
                "num_trials": 2,
                "with_replacement": True,
            },
            "CalculateProbabilityVerb": {"condition": "複合条件"},
        },
        "visual_component": "Tree_Renderer",
        "y_base": 32,
        "raw_y_base": 1600,
        "supported_forms": ["calculation", "word_problem"],
        "is_clean_override": {"disabled": True},
        "dedup_disabled": True,
        "difficulty_levels": {
            "calculation": [
                {
                    "lv": 1,
                    "description": "さいころ2個を同時に振り、和や積が特定値になる確率",
                    "atom_constraints": {"EventAtom": {"event_type": "dice", "num_trials": 2}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "カードや玉を取り出す（順序あり・なし）複合事象の確率",
                    "atom_constraints": {
                        "EventAtom": {"event_type": "card", "num_trials": 2, "with_replacement": False},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "余事象（少なくとも1つ）を利用した複合確率の計算",
                    "atom_constraints": {"EventAtom": {"event_type": "coin", "num_trials": 3}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
            "word_problem": [
                {
                    "lv": 1,
                    "description": "文章中の試行を樹形図にまとめ確率を求める（基本）",
                    "atom_constraints": {"EventAtom": {"event_type": "dice", "num_trials": 2}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "複数種類の取り出しを含む複合事象の確率（応用）",
                    "atom_constraints": {
                        "EventAtom": {"event_type": "card", "num_trials": 2, "with_replacement": False},
                    },
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "余事象を利用する確率・実生活場面での確率問題",
                    "atom_constraints": {"EventAtom": {"event_type": "coin", "num_trials": 3}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l6": {
        "title": "相似と面積比・体積比の融合",
        "grade": 3,
        "lesson_number": 6,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["similarity", "plane_geometry", "multi-unit"],
        "prerequisite_lessons": ["g3_l39", "g3_l40", "g3_l43", "g3_l45", "g3_l46"],
        "execute_blueprint": "BasicGeometryMeasurementStructure",
        "atom_constraints": {
            "PolygonAtom": {
                "polygon_type": "triangle",
                "max_side_length": 15,
            },
        },
        "visual_component": "2D_Geometry_Renderer",
        "y_base": 36,
        "raw_y_base": 1800,
        "supported_forms": ["word_problem"],
        "is_clean_override": {"disabled": True},
        "difficulty_levels": {
            "word_problem": [
                {
                    "lv": 1,
                    "description": "相似比から面積比を計算し、片方の面積を求める（基本）",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 10}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "平行線と線分の比を利用して分割された図形の面積比を求める",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 12}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "三平方の定理と相似を組み合わせた辺の長さ・面積の計算（複合）",
                    "atom_constraints": {"PolygonAtom": {"max_side_length": 15}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
    "exam_l7": {
        "title": "データの活用（箱ひげ図・標本調査）",
        "grade": 3,
        "lesson_number": 7,
        "large_unit": "入試対策",
        "domain": "入試対策",
        "required_tags": ["data_analysis", "probability", "multi-unit"],
        "prerequisite_lessons": ["g1_l54", "g1_l57", "g2_l55", "g2_l56", "g3_l57", "g3_l60"],
        "execute_blueprint": "DescriptiveStatsStructure",
        "execute_blueprint_by_form": {
            "calculation": "DescriptiveStatsStructure",
            "word_problem": "SampleSurveyStructure",
        },
        "atom_constraints": {
            "DataSetAtom": {
                "n_values": 10,
                "value_range_min": 0,
                "value_range_max": 100,
            },
            "SampleAtom": {
                "population_size": 1000,
                "sample_size": 50,
            },
        },
        "visual_component": "NullRenderer",
        "y_base": 28,
        "raw_y_base": 1400,
        "supported_forms": ["calculation", "word_problem"],
        "is_clean_override": {"disabled": True},
        "dedup_disabled": True,
        "difficulty_levels": {
            "calculation": [
                {
                    "lv": 1,
                    "description": "10個のデータから四分位数・四分位範囲を計算する",
                    "atom_constraints": {"DataSetAtom": {"n_values": 10}},
                    "blueprint_params": {"metric": "iqr"},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "2組のデータの四分位数を求め、箱ひげ図を読み取り比較する",
                    "atom_constraints": {"DataSetAtom": {"n_values": 12}},
                    "blueprint_params": {"metric": "median"},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "複数の統計量（中央値・四分位範囲・外れ値）を総合的に分析する",
                    "atom_constraints": {"DataSetAtom": {"n_values": 15}},
                    "blueprint_params": {"metric": "q3"},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
            "word_problem": [
                {
                    "lv": 1,
                    "description": "標本から母集団の総数を推定する基本問題",
                    "atom_constraints": {"SampleAtom": {"population_size": 500, "sample_size": 25}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 2,
                    "description": "標本調査の結果から母集団の特定の量を推定する応用問題",
                    "atom_constraints": {"SampleAtom": {"population_size": 1000, "sample_size": 50}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
                {
                    "lv": 3,
                    "description": "複数の標本調査を比較・推定の信頼性を評価する発展問題",
                    "atom_constraints": {"SampleAtom": {"population_size": 2000, "sample_size": 100}},
                    "blueprint_params": {},
                    "verb_config": {},
                    "implementable": True,
                    "implementation_note": "",
                },
            ],
        },
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Add exam_l1〜exam_l7 to mapping.json")
    parser.add_argument("--force", action="store_true", help="Overwrite existing exam_l* entries")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be added without writing")
    args = parser.parse_args()

    with open(MAPPING_PATH, encoding="utf-8") as f:
        mapping: dict = json.load(f)

    added = 0
    skipped = 0
    for lesson_id, lesson_data in EXAM_LESSONS.items():
        if lesson_id in mapping and not args.force:
            print(f"  SKIP  {lesson_id} (already exists, use --force to overwrite)")
            skipped += 1
            continue
        if args.dry_run:
            forms = lesson_data["supported_forms"]
            levels_count = sum(len(v) for v in lesson_data["difficulty_levels"].values())
            print(f"  DRY   {lesson_id}: {lesson_data['title']} forms={forms} levels={levels_count}")
        else:
            mapping[lesson_id] = lesson_data
            print(f"  ADD   {lesson_id}: {lesson_data['title']}")
        added += 1

    if args.dry_run:
        print(f"\n[dry-run] {added} would be added, {skipped} skipped")
        return

    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"\n完了: {added} 件追加, {skipped} 件スキップ")
    print(f"mapping.json に exam_l1〜exam_l7 を追加しました")


if __name__ == "__main__":
    main()
