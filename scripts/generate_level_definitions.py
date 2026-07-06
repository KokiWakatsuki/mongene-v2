#!/usr/bin/env python3
"""Phase 3: LLM で (lesson_id, form) ごとのレベル定義を生成し mapping.json に追加

使い方:
  # ドライラン（プロンプト確認）
  python scripts/generate_level_definitions.py --dry-run --lesson g1_l3 --form calculation

  # 全件生成（中断再開対応）
  python scripts/generate_level_definitions.py

  # 特定レッスン・form だけ
  python scripts/generate_level_definitions.py --lesson g1_l3

  # 件数制限
  python scripts/generate_level_definitions.py --limit 10

  # 下書きを mapping.json にマージ（人間レビュー後）
  python scripts/generate_level_definitions.py --merge

  # implementable=false 件数を確認
  python scripts/generate_level_definitions.py --report
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE = Path(__file__).resolve().parent.parent
DRAFT_PATH = BASE / "reports" / "level_definitions_draft.json"
MAPPING_PATH = BASE / "master_data" / "mapping.json"
SPEC_PATH = BASE / "docs" / "atom_verb_spec.json"


def load_data() -> tuple[Dict, Dict]:
    with open(MAPPING_PATH) as f:
        mapping = json.load(f)
    with open(SPEC_PATH) as f:
        spec = json.load(f)
    return mapping, spec


def get_blueprint_for_form(lesson: Dict, form: str) -> Optional[str]:
    if "execute_blueprint_by_form" in lesson:
        return lesson["execute_blueprint_by_form"].get(form)
    blueprints_list = lesson.get("execute_blueprints")
    if blueprints_list and isinstance(blueprints_list, list):
        return blueprints_list[0]
    return lesson.get("execute_blueprint")


def build_prompt(lesson_id: str, form: str, lesson: Dict, spec: Dict) -> str:
    blueprint_id = get_blueprint_for_form(lesson, form)
    blueprint_spec = spec["blueprints"].get(blueprint_id, {}) if blueprint_id else {}

    # 関連 Atom を level_knobs から抽出
    level_knobs = blueprint_spec.get("level_knobs", [])
    relevant_atoms: set[str] = set()
    for knob in level_knobs:
        atom_name = knob.split(".")[0]
        relevant_atoms.add(atom_name)

    atom_specs = {
        name: spec["atoms"][name]
        for name in sorted(relevant_atoms)
        if name in spec["atoms"]
    }

    base_constraints = lesson.get("atom_constraints", {})

    # Blueprint サマリー（LLM に渡す必要最小限の情報）
    bp_summary: Dict[str, Any] = {"blueprint_id": blueprint_id}
    if blueprint_spec:
        bp_summary["level_knobs"] = level_knobs
        bp_summary["blueprint_params_available"] = blueprint_spec.get("blueprint_params", {})
        bp_summary["usage_note"] = blueprint_spec.get("usage_note", "")
        bp_summary["supported_forms"] = blueprint_spec.get("supported_forms", [])

    form_guidance = {
        "calculation": "計算問題: 数値の大きさ・演算の種類・項数などで難易度を変える",
        "word_problem": "文章問題: 文脈の複雑さ・数値の扱いにくさ・手順の数で難易度を変える",
        "knowledge": "知識問題: 概念の認識→定義の理解→応用・判断の順に難易度を上げる",
        "visual": "図形・視覚問題: 図形の種類・複合度・計算量で難易度を変える",
        "proof": "証明問題: 使う定理の数・補助線・間接証明などで難易度を変える",
    }
    form_hint = form_guidance.get(form, "")

    return f"""あなたは中学数学の教材設計者です。以下の（レッスン, 問題形式）の組み合わせに対して、難易度レベル定義（Lv1〜LvN）をJSONで生成してください。

## レッスン情報
- lesson_id: {lesson_id}
- タイトル: {lesson.get("title", "")}
- 学年: 中学{lesson.get("grade", "")}年
- 大単元: {lesson.get("large_unit", "")}
- ドメイン: {lesson.get("domain", "")}

## 問題形式: {form}
{form_hint}

## 使用 Blueprint
{json.dumps(bp_summary, ensure_ascii=False, indent=2)}

## 制御可能な Atom パラメータ
{json.dumps(atom_specs, ensure_ascii=False, indent=2)}

## ベース atom_constraints（mapping.json の現在値、差分の参照用）
{json.dumps(base_constraints, ensure_ascii=False, indent=2)}

## 生成ルール
1. Lv1（最易）〜LvN（最難）で **3〜5 レベル** を定義すること
2. 各レベルは**必ず異なる問題が生成される**よう、パラメータで明確に差別化すること
3. `atom_constraints` はベース設定への**差分（patch）**のみ記述すること（変更しないキーは省略）
4. `blueprint_params` は Blueprint の `blueprint_params_available` に定義されているキーのみ使用すること
5. この form の特性に合った難易度変化にすること（他 form の要素を混入させないこと）
6. 現在のシステムで実装不可能な場合は `implementable: false` を設定し `implementation_note` に理由を記述すること

## 出力形式（JSONのみ、前後の説明文は不要）
{{
  "lesson_id": "{lesson_id}",
  "form": "{form}",
  "levels": [
    {{
      "lv": 1,
      "description": "（日本語で15字以内）",
      "rationale": "（なぜこれが Lv1 か。レビュー用）",
      "atom_constraints": {{}},
      "blueprint_params": {{}},
      "verb_config": {{}},
      "implementable": true,
      "implementation_note": ""
    }}
  ],
  "unimplementable_reason": ""
}}"""


def _load_dotenv() -> None:
    """プロジェクトルートの .env から環境変数を読み込む（python-dotenv 不要）"""
    env_path = BASE / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()


def call_gemini(prompt: str, model: str = "gemini-flash-lite-latest", retries: int = 3) -> str:
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as e:
        print(f"google-genai 未インストール: {e}", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY が設定されていません", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    last_err: Optional[Exception] = None

    for attempt in range(retries):
        try:
            config = genai_types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=2048),
            )
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
            text = response.text
            if not text or not text.strip():
                raise ValueError(f"{model} が空応答を返した")
            return text
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "quota" in msg or "resource_exhausted" in msg:
                wait = 2 ** attempt * 5
                print(f"  レート制限 (attempt {attempt+1}): {wait}s 待機...")
                time.sleep(wait)
                continue
            if attempt < retries - 1:
                time.sleep(2)
                continue
            break

    raise RuntimeError(f"Gemini 呼び出し失敗: {last_err}")


def parse_json(raw: str) -> Dict:
    import re
    text = raw.strip()
    # ```json ... ``` を除去
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 最外 { } だけ抽出して再試行
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def generate_one(lesson_id: str, form: str, lesson: Dict, spec: Dict, model: str) -> Dict:
    prompt = build_prompt(lesson_id, form, lesson, spec)
    raw = call_gemini(prompt, model=model)
    result = parse_json(raw)
    return result


def load_drafts() -> tuple[List[Dict], set[tuple[str, str]]]:
    if DRAFT_PATH.exists():
        with open(DRAFT_PATH) as f:
            drafts = json.load(f)
        keys = {(d["lesson_id"], d["form"]) for d in drafts}
        return drafts, keys
    return [], set()


def save_drafts(drafts: List[Dict]) -> None:
    with open(DRAFT_PATH, "w") as f:
        json.dump(drafts, f, ensure_ascii=False, indent=2)


def cmd_merge(args: argparse.Namespace) -> None:
    if not DRAFT_PATH.exists():
        print(f"下書きファイルが存在しません: {DRAFT_PATH}")
        sys.exit(1)

    with open(DRAFT_PATH) as f:
        drafts = json.load(f)

    with open(MAPPING_PATH) as f:
        mapping = json.load(f)

    merged = 0
    skipped_error = 0
    skipped_unimplementable = 0

    for item in drafts:
        lid = item.get("lesson_id")
        form = item.get("form")
        if not lid or not form:
            continue
        if "error" in item:
            skipped_error += 1
            continue
        if lid not in mapping:
            continue

        levels = item.get("levels", [])
        # rationale を除去してマージ（内部メモなのでmapping.jsonには不要）
        clean_levels = []
        for lv in levels:
            clean_lv = {k: v for k, v in lv.items() if k != "rationale"}
            clean_levels.append(clean_lv)

        # implementable=false のみのケースはスキップ（システム拡張が必要）
        if args.implementable_only:
            all_impl = all(lv.get("implementable", True) for lv in clean_levels)
            if not all_impl:
                skipped_unimplementable += 1
                continue

        if "difficulty_levels" not in mapping[lid]:
            mapping[lid]["difficulty_levels"] = {}
        mapping[lid]["difficulty_levels"][form] = clean_levels
        merged += 1

    with open(MAPPING_PATH, "w") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f"マージ完了: {merged} 件")
    if skipped_error:
        print(f"スキップ（エラー）: {skipped_error} 件")
    if skipped_unimplementable:
        print(f"スキップ（実装不可）: {skipped_unimplementable} 件")


def cmd_report(args: argparse.Namespace) -> None:
    if not DRAFT_PATH.exists():
        print("下書きファイルが存在しません")
        sys.exit(1)

    with open(DRAFT_PATH) as f:
        drafts = json.load(f)

    total = len(drafts)
    errors = [d for d in drafts if "error" in d]
    ok = [d for d in drafts if "error" not in d]
    unimpl = [
        d for d in ok
        if any(not lv.get("implementable", True) for lv in d.get("levels", []))
    ]

    print(f"総件数: {total} / 378")
    print(f"  ✅ 成功: {len(ok)}")
    print(f"  ❌ エラー: {len(errors)}")
    print(f"  ⚠️  実装不可レベルあり: {len(unimpl)}")

    if args.verbose and unimpl:
        print("\n--- 実装不可 詳細 ---")
        for d in unimpl:
            lid = d["lesson_id"]
            form = d["form"]
            for lv in d["levels"]:
                if not lv.get("implementable", True):
                    note = lv.get("implementation_note", "")
                    print(f"  {lid} × {form} Lv{lv['lv']}: {note[:80]}")

    if errors:
        print("\n--- エラー ---")
        for d in errors[:10]:
            print(f"  {d['lesson_id']} × {d['form']}: {str(d.get('error', ''))[:80]}")


def cmd_generate(args: argparse.Namespace) -> None:
    mapping, spec = load_data()

    # 対象ペアを収集
    pairs: List[tuple[str, str, Dict]] = []
    for lid, lesson in mapping.items():
        for form in lesson.get("supported_forms", []):
            if args.lesson and lid != args.lesson:
                continue
            if args.form and form != args.form:
                continue
            pairs.append((lid, form, lesson))

    if args.limit:
        pairs = pairs[: args.limit]

    # 既存下書きを読み込み
    drafts, existing_keys = load_drafts()

    # 未処理のみ対象
    pending = [(lid, f, l) for lid, f, l in pairs if (lid, f) not in existing_keys]

    print(f"対象: {len(pairs)} ペア / 未処理: {len(pending)} ペア")

    if args.dry_run:
        if pending:
            lid, f, lesson = pending[0]
            print(f"\n=== プロンプトプレビュー: {lid} × {f} ===\n")
            print(build_prompt(lid, f, lesson, spec))
        else:
            print("未処理のペアがありません")
        return

    if not pending:
        print("処理するペアがありません（全件完了済み）")
        return

    model = args.model
    print(f"モデル: {model}")

    for i, (lid, f, lesson) in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}] {lid} × {f}: 生成中...", end="", flush=True)
        try:
            result = generate_one(lid, f, lesson, spec, model)
            n_lv = len(result.get("levels", []))
            has_unimpl = any(not lv.get("implementable", True) for lv in result.get("levels", []))
            status = "⚠️" if has_unimpl else "✅"
            print(f" {status} Lv1〜Lv{n_lv}")
            drafts.append(result)
        except Exception as e:
            print(f" ❌ {e}")
            drafts.append({"lesson_id": lid, "form": f, "error": str(e), "levels": []})

        # 逐次保存（中断しても途中から再開可能）
        save_drafts(drafts)

        # レート制限対策
        if i < len(pending):
            time.sleep(0.3)

    print(f"\n完了: {DRAFT_PATH}")
    n_ok = sum(1 for d in drafts if "error" not in d)
    n_err = sum(1 for d in drafts if "error" in d)
    print(f"成功: {n_ok}, エラー: {n_err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3: レベル定義を LLM で生成")
    sub = parser.add_subparsers(dest="cmd")

    # generate（デフォルト）
    gen = sub.add_parser("generate", help="レベル定義を生成（デフォルト動作）")
    gen.add_argument("--lesson", help="特定レッスンのみ (e.g. g1_l3)")
    gen.add_argument("--form", help="特定 form のみ (e.g. calculation)")
    gen.add_argument("--limit", type=int, help="処理件数の上限")
    gen.add_argument("--dry-run", action="store_true", help="プロンプトを表示するだけ（API 呼び出しなし）")
    gen.add_argument("--model", default="gemini-flash-lite-latest", help="使用モデル")

    # merge
    mrg = sub.add_parser("merge", help="下書きを mapping.json にマージ")
    mrg.add_argument("--implementable-only", action="store_true", help="implementable=false をスキップ")

    # report
    rep = sub.add_parser("report", help="下書きの統計を表示")
    rep.add_argument("--verbose", action="store_true", help="実装不可の詳細を表示")

    # 後方互換：サブコマンドなしで直接フラグを受け付ける
    parser.add_argument("--lesson", help="特定レッスンのみ")
    parser.add_argument("--form", help="特定 form のみ")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--model", default="gemini-flash-lite-latest")
    parser.add_argument("--merge", action="store_true", help="下書きを mapping.json にマージ")
    parser.add_argument("--implementable-only", action="store_true")
    parser.add_argument("--report", action="store_true", help="下書きの統計を表示")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    # サブコマンドなしの場合は --merge / --report フラグで分岐
    if args.cmd is None:
        if args.merge:
            cmd_merge(args)
        elif args.report:
            cmd_report(args)
        else:
            cmd_generate(args)
    elif args.cmd == "generate":
        cmd_generate(args)
    elif args.cmd == "merge":
        cmd_merge(args)
    elif args.cmd == "report":
        cmd_report(args)


if __name__ == "__main__":
    main()
