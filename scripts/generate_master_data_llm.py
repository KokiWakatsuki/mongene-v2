"""§21.1〜21.4 + §25.4 のプロンプトを実 LLM (Gemini Flash-Lite) で実行し、
master_data 一式を再生成する。

使い方:
    PYTHONPATH=. SKIP_LLM_IN_TESTS=false python scripts/generate_master_data_llm.py [--what mapping|prereq|scenarios|forbidden|few_shot|all]

無料枠 (gemini-flash-lite-latest 1000 RPD/15 RPM) 内で完結するように作っている。
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv

load_dotenv()

from apps.api.src.core.llm.translator import call_gemini  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER = REPO_ROOT / "master_data"

# ============================================================================
# §21.4: 禁止語彙リスト生成（1 リクエストで完結）
# ============================================================================

FORBIDDEN_WORDS_PROMPT = """あなたは中学校教材の編集者として、教育上不適切なため自動生成される問題文に含めるべきでない語彙のリストを作成してください。

# カテゴリと例
- 暴力・武器関連: 殺す、撃つ、爆発、銃、ナイフ、刃物...
- 差別語: 教材編集ガイドラインに準拠
- 性的表現: 中学生対象として不適切な語彙
- ギャンブル: パチンコ、賭博...
- 危険行為の助長: 飲酒、薬物、自殺...

# 出力形式（プレーンテキスト、1 行 1 語、200-500 語、コメントや解説は一切無し）
殺す
撃つ
...

# 注意
- 数学問題に出てくる「割合」「平均」等の中立的な統計用語は除外
- 「歴史上の戦争」のような教育的文脈で必要な語は別途許可リストで管理"""


def generate_forbidden_words() -> None:
    print("[forbidden_words] generating ...")
    text = call_gemini(FORBIDDEN_WORDS_PROMPT, tier="lite")
    words_raw = [w.strip() for w in text.splitlines() if w.strip() and not w.startswith("#")]
    words_raw = [w for w in words_raw if 1 <= len(w) <= 20]
    # 重複除去（順序維持）
    seen = set()
    words: List[str] = []
    for w in words_raw:
        if w not in seen:
            seen.add(w)
            words.append(w)
    out = MASTER / "forbidden_words.txt"
    out.write_text("\n".join(words) + "\n", encoding="utf-8")
    print(f"  {len(words)} words -> {out}")


# ============================================================================
# §25.4: シナリオバンク生成（1 リクエストで完結）
# ============================================================================

SCENARIO_GENERATION_PROMPT = """中学校数学の文章題で使用するシナリオを 15 個生成してください。

# カテゴリ別
- 速さ・道のり: 3 個
- 濃度・割合: 3 個
- 代金・個数: 3 個
- 仕事算・効率: 2 個
- 過不足: 2 個
- 図形・面積（実物に紐付く）: 2 個

# 出力形式（YAML のみ、説明文不要）
scenarios:
  - id: speed_walking_to_school
    category: speed
    setting: 通学路の移動
    characters: [太郎, 花子, Aさん, Bさん]
    locations: [家, 学校, 駅, 公園]
    units:
      distance: [km, m]
      time: [分, 時間]
    narrative_templates:
      - "{character_a}は{loc_a}から{loc_b}まで歩いて行きます。"
    applicable_lesson_ids: [g1_l27, g2_l17]
  ..."""


def generate_scenarios() -> None:
    print("[scenarios] generating ...")
    text = call_gemini(SCENARIO_GENERATION_PROMPT, tier="lite")
    # YAML 抽出
    text = re.sub(r"^```ya?ml\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        data = yaml.safe_load(text)
        assert "scenarios" in data and len(data["scenarios"]) >= 5
    except Exception as e:
        print(f"  YAML parse failed: {e}. Skipping.")
        return
    out = MASTER / "scenarios.yaml"
    out.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"  {len(data['scenarios'])} scenarios -> {out}")


# ============================================================================
# §21.3: Few-Shot 種コーパス生成（代表 lesson × form × 1 例）
# ============================================================================

FEW_SHOT_PROMPT = """あなたは中学校数学の塾講師として、LLM 翻訳の Few-Shot 例となる中間表現と理想的な問題文・解説のペアを作成してください。

# 入力
対象 lesson_id: {lesson_id}
対象 Blueprint: {blueprint}
問題形式: {form}
タイトル: {title}

# 出力形式（YAML 1 ファイル）
examples:
  - input_middle_representation:
      problem_structure_type: "{blueprint}"
      selected_tags: [...]
      difficulty_score: NN
      problem_form: "{form}"
      sub_questions:
        - label: ""
          prompt_hint: ...
          answer:
            type: numeric
            sympy_form: "..."
            text_form: "..."
    ideal_problem_text: |
      ...
    ideal_explanation_text: |
      ..."""


def generate_few_shot_seeds(max_lessons: int = 10) -> None:
    print(f"[few_shot_seeds] generating up to {max_lessons} ...")
    mapping = json.loads((MASTER / "mapping.json").read_text(encoding="utf-8"))
    # 代表 lesson を選ぶ: 各 Blueprint から 1 つずつ
    by_bp: Dict[str, str] = {}
    for lid, m in mapping.items():
        bp = m["execute_blueprint"]
        if bp not in by_bp:
            by_bp[bp] = lid
    selected = list(by_bp.values())[:max_lessons]

    seeds_dir = MASTER / "few_shot_seeds"
    seeds_dir.mkdir(exist_ok=True)
    for i, lid in enumerate(selected):
        m = mapping[lid]
        form = m["supported_forms"][0]
        prompt = FEW_SHOT_PROMPT.format(
            lesson_id=lid,
            blueprint=m["execute_blueprint"],
            form=form,
            title=m["title"],
        )
        try:
            text = call_gemini(prompt, tier="lite")
            text = re.sub(r"^```ya?ml\s*", "", text.strip(), flags=re.MULTILINE)
            text = re.sub(r"\s*```$", "", text.strip())
            try:
                yaml.safe_load(text)
            except Exception:
                print(f"  {lid}: invalid YAML, skipping")
                continue
            out = seeds_dir / f"{lid}_{form}.yaml"
            out.write_text(text, encoding="utf-8")
            print(f"  {i + 1}/{len(selected)}: {out.name}")
            time.sleep(4)  # RPM=15 を守るため余裕を持って
        except Exception as e:
            print(f"  {lid}: {type(e).__name__}: {e}")
            time.sleep(8)


# ============================================================================
# §21.1: マッピング JSON 生成（全 177 lesson、所要 約 12 分 @ RPM=15）
# ============================================================================

MAPPING_PROMPT = """あなたは中学校数学教育の専門家として、学習指導要領の小単元と本システムの Blueprint/Atom を対応付けるマッピング JSON を作成してください。

# 入力データ
学年: {grade}
領域: {domain}
大単元: {large_unit}
小単元: lesson_{lesson_number}「{title}」

# 利用可能な Blueprint（11 個から 1 つを選択）
1. BasicCalculationStructure - 四則・方程式・式の計算
2. WordProblemStructure - 文章題・立式
3. BasicGeometryMeasurementStructure - 図形の面積・体積・表面積
4. BasicDifferenceStructure - くり抜き・回転体・切断
5. FunctionGeometryFusionStructure - 関数と図形の融合
6. MovingPointStructure - 動点・時間関数
7. AngleCalculationStructure - 角度・円周角・接弦角
8. ConstructionStructure - 作図・軌跡
9. ProofStructure - 合同・相似・代数証明
10. DataProbabilityStructure - 確率・統計・標本調査
11. SequencePatternStructure - 規則性・数列

# 出力形式（JSON のみ、説明文不要）
{{
  "execute_blueprint": "（上記から 1 個選択）",
  "required_tags": [...],
  "optional_tags": [],
  "atom_constraints": {{...}},
  "visual_component": "（NullRenderer/2D_Geometry_Renderer/3D_Renderer/Graph_Renderer/Tree_Renderer/Table_&_Chart_Renderer から選択）",
  "y_base": （整数 1-100）,
  "supported_forms": [...]
}}"""


GRADE_LABEL = {1: "中学1年", 2: "中学2年", 3: "中学3年"}


def generate_mapping_llm() -> None:
    print("[mapping] LLM 版マッピング生成 ...")
    curriculum = json.loads((MASTER / "curriculum_math.json").read_text(encoding="utf-8"))
    seed_raw = json.loads((MASTER / "mapping_seed.json").read_text(encoding="utf-8"))
    seed = {k: v for k, v in seed_raw.items() if not k.startswith("_") and isinstance(v, dict)}

    out_path = MASTER / "mapping_llm.json"
    mapping: Dict[str, Any] = {}
    if out_path.exists():
        mapping = json.loads(out_path.read_text(encoding="utf-8"))  # 途中再開対応

    grade_map = {"中学1年": 1, "中学2年": 2, "中学3年": 3}
    total = sum(
        len(su)
        for g in curriculum
        for d in g["domains"]
        for lu in d["large_units"]
        for mu in lu["middle_units"]
        for su in [mu["small_units"]]
    )
    done = 0
    for grade_entry in curriculum:
        g_label = grade_entry["grade"]
        g_int = grade_map[g_label]
        for d in grade_entry["domains"]:
            for lu in d["large_units"]:
                for mu in lu["middle_units"]:
                    for su in mu["small_units"]:
                        lid = f"g{g_int}_l{su['lesson_number']}"
                        done += 1
                        if lid in seed:
                            mapping[lid] = seed[lid]
                            continue
                        if lid in mapping:
                            continue
                        prompt = MAPPING_PROMPT.format(
                            grade=g_label,
                            domain=d["domain_name"],
                            large_unit=lu["large_unit_name"],
                            lesson_number=su["lesson_number"],
                            title=su["title"],
                        )
                        try:
                            text = call_gemini(prompt, tier="lite")
                            text = re.sub(r"^```json\s*", "", text.strip(), flags=re.MULTILINE)
                            text = re.sub(r"\s*```$", "", text.strip())
                            m_obj = re.search(r"\{.*\}", text, re.DOTALL)
                            if not m_obj:
                                print(f"  {lid} ({done}/{total}): no JSON found, skipping")
                                continue
                            data = json.loads(m_obj.group(0))
                            data.update({
                                "title": su["title"],
                                "grade": g_int,
                                "lesson_number": su["lesson_number"],
                                "domain": d["domain_name"],
                                "large_unit": lu["large_unit_name"],
                            })
                            mapping[lid] = data
                            print(f"  {lid} ({done}/{total}): {data.get('execute_blueprint')}")
                        except Exception as e:
                            print(f"  {lid} ({done}/{total}): {type(e).__name__}: {str(e)[:80]}")
                            time.sleep(10)
                            continue
                        # 都度保存（途中再開対応）
                        out_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
                        time.sleep(4.5)  # RPM=15 ≒ 4 秒/req

    print(f"\nTotal: {len(mapping)} -> {out_path}")


# ============================================================================
# §21.2: 前提グラフ生成（1 リクエスト）
# ============================================================================

PREREQ_PROMPT = """あなたは中学校数学カリキュラムの専門家として、各小単元の前提となる単元（学習が必要な前段階単元）を判定してください。

# 入力データ
全 177 小単元のリスト（lesson_id, 学年, タイトル付き）:
{all_lessons}

# 出力形式（YAML のみ、コメント不要）
nodes:
  - id: g1_l22
    title: "移項による方程式の解き方"
    requires:
      - g1_l21
      - g1_l19
  - id: g3_l55
    title: "空間図形への利用"
    requires:
      - g3_l51
      - g1_l47
  ..."""


def generate_prereq_llm() -> None:
    print("[prereq] LLM 版前提グラフ生成 ...")
    mapping = json.loads((MASTER / "mapping.json").read_text(encoding="utf-8"))
    all_lessons = "\n".join(
        f"- {lid}: 中{m['grade']} {m['title']}"
        for lid, m in sorted(mapping.items(), key=lambda kv: (kv[1]["grade"], kv[1]["lesson_number"]))
    )
    prompt = PREREQ_PROMPT.format(all_lessons=all_lessons)
    text = call_gemini(prompt, tier="lite")
    text = re.sub(r"^```ya?ml\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip())
    try:
        data = yaml.safe_load(text)
        assert "nodes" in data
    except Exception as e:
        print(f"  YAML parse failed: {e}. Skipping.")
        return
    out = MASTER / "prerequisite_graph_llm.yaml"
    out.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"  {len(data['nodes'])} nodes -> {out}")


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--what",
        choices=["mapping", "prereq", "scenarios", "forbidden", "few_shot", "all"],
        default="all",
    )
    args = p.parse_args()

    if args.what in ("forbidden", "all"):
        generate_forbidden_words()
    if args.what in ("scenarios", "all"):
        generate_scenarios()
    if args.what in ("few_shot", "all"):
        generate_few_shot_seeds(max_lessons=10)
    if args.what in ("prereq", "all"):
        generate_prereq_llm()
    if args.what == "mapping":
        # mapping は 177 リクエストで重いので明示指定時のみ
        generate_mapping_llm()


if __name__ == "__main__":
    main()
