"""product コーパス構築スクリプト（form品質軸測定用）。

`tests/fixtures/reference_corpus/ground_truth/{lesson}_{form}_{level}.json`
（`build_ground_truth_corpus.py` が生成した GT。各ファイルに `_pinned_seed` を持つ）を
入力に、同一キー・同一 base_seed で product（`/problems/generate` 相当の翻訳済み問題）を
生成し `tests/fixtures/reference_corpus/product/{engine}/{lesson}_{form}_{level}.json` に
保存する。`scripts/run_gates.py --product-dir` がこのディレクトリを直接読める。

**LLM 実行について**:
- `--engine gemini`: 実際に Gemini へ翻訳リクエストを送る（GEMINI_API_KEY が必要）。
  SKIP_LLM_IN_TESTS=true を明示的に立てればモック翻訳になり、配線確認のスモークができる。
- `--engine claude`: 2フェーズ。
  - `--dump`: 各 GT キーについて、Gemini に送るのと同一の翻訳プロンプト（問題文プロンプト＋
    解説プロンプト）を `product/claude/_staging/{key}.prompt.txt` に書き出す。
    MR の要点（answer 等の照合用データ）を `product/claude/_staging/{key}.mr.json` に残す。
  - `--ingest`: `product/claude/_responses/{key}.json`（人手/Claude が翻訳結果を書き戻した
    ファイル）を読み、product JSON 形状に組み立てて `product/claude/{key}.json` に保存する。
    answer は GT（SymPy）の値を使う（LLM は答えを変えない）。

**フレッシュな runner**: `/problems/inspect` と同じ流儀で、呼び出しごとに
BlueprintRunner を tmp dedup db・new DiversityRotation で newする。
これにより dedup/diversity の状態が呼び出しをまたいで交絡しない
（同一 base_seed を注入すれば同一 MR が再現される前提を守る）。

使い方:
    # gemini engine（実LLM。GEMINI_API_KEY 必須）
    .venv/bin/python scripts/build_product_corpus.py --engine gemini --lesson g1_l1

    # gemini engine をモック翻訳でスモーク（実LLMを呼ばない）
    SKIP_LLM_IN_TESTS=true .venv/bin/python scripts/build_product_corpus.py --engine gemini --lesson g1_l1

    # claude engine: プロンプトを書き出す
    .venv/bin/python scripts/build_product_corpus.py --engine claude --dump --lesson g1_l1

    # (staging の prompt.txt を Claude に渡して翻訳させ、
    #  product/claude/_responses/{key}.json に応答を保存する。人手で行う)

    # claude engine: 応答を取り込んで product JSON を組み立てる
    .venv/bin/python scripts/build_product_corpus.py --engine claude --ingest --lesson g1_l1
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus_seed import pinned_seed  # noqa: E402

GROUND_TRUTH_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "ground_truth"
PRODUCT_DIR = REPO_ROOT / "tests" / "fixtures" / "reference_corpus" / "product"
DIAGRAM_CACHE_DIR = REPO_ROOT / "master_data" / "cache" / "diagrams"

_GT_FILENAME_RE = re.compile(
    r"^(?P<lesson>.+)_(?P<form>word_problem|calculation|proof|knowledge|visual)_(?P<level>min|mid|max)\.json$"
)


# ---------------------------------------------------------------------------
# GT コーパスの読み込み
# ---------------------------------------------------------------------------


def load_gt_keys(
    gt_dir: Path = GROUND_TRUTH_DIR,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
) -> list[dict[str, Any]]:
    """GT ディレクトリを走査し、各ファイルから必要フィールドを抜き出す。

    戻り値は各要素が
    {"key", "lesson_id", "form", "level_label", "target_level", "pinned_seed", "gt_path", "gt_data"}
    の dict のリスト。
    """
    entries: list[dict[str, Any]] = []
    if not gt_dir.exists():
        return entries
    for path in sorted(gt_dir.glob("*.json")):
        m = _GT_FILENAME_RE.match(path.name)
        if not m:
            continue  # ground_truth_build_failures.json 等は無視
        lesson_id = m.group("lesson")
        form = m.group("form")
        level_label = m.group("level")
        if lesson_filter and lesson_id != lesson_filter:
            continue
        if form_filter and form != form_filter:
            continue
        gt_data = json.loads(path.read_text(encoding="utf-8"))
        target_level = gt_data.get("_target_level")
        seed = gt_data.get("_pinned_seed")
        if seed is None:
            # 後方互換: _pinned_seed が無い旧GTは、キーから同じ式で再計算する
            seed = pinned_seed(lesson_id, form, level_label)
        entries.append(
            {
                "key": f"{lesson_id}_{form}_{level_label}",
                "lesson_id": lesson_id,
                "form": form,
                "level_label": level_label,
                "target_level": target_level,
                "pinned_seed": seed,
                "gt_path": path,
                "gt_data": gt_data,
            }
        )
    return entries


def _load_mapping() -> dict[str, Any]:
    mapping_path = REPO_ROOT / "master_data" / "mapping.json"
    return json.loads(mapping_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# フレッシュな runner での生成（/problems/inspect と同じ流儀）
# ---------------------------------------------------------------------------


def _ensure_atoms_verbs_registered() -> None:
    """Atom/Verb はモジュール import の副作用でレジストリに登録される。

    `apps.api.main`（ひいては `apps.api.src.domains.problems.router`）を経由しない限り
    レジストリが空のままになり `NoCompatibleAtomError` になるため、明示的に import する。
    """
    import apps.api.main  # noqa: F401


def _fresh_runner(translator: Any, max_retries: int = 50):
    """/problems/inspect と同型: tmp dedup db・new DiversityRotation で都度 new する。"""
    _ensure_atoms_verbs_registered()
    from apps.api.src.blueprints.registry import load_blueprint
    from apps.api.src.core.dedup.diversity_rotation import DiversityRotation
    from apps.api.src.core.dedup.hash_cache import DuplicationGuard
    from apps.api.src.core.runner.atom_selector import AtomSelector
    from apps.api.src.core.runner.blueprint_runner import BlueprintRunner

    tmp_db = tempfile.mktemp(suffix=".db")
    runner = BlueprintRunner(
        dedup=DuplicationGuard(db_path=tmp_db),
        diversity=DiversityRotation(),
        translator=translator,
        atom_selector=AtomSelector(),
        blueprint_loader=load_blueprint,
        max_retries=max_retries,
    )
    return runner, tmp_db


def _run_generation(entry: dict[str, Any], mapping: dict[str, Any], translator: Any):
    """entry (GT由来のキー情報) から GenerationRequest を組み立て、フレッシュな runner で生成する。

    戻り値: BlueprintRunner.run() の GeneratedProblem。
    """
    from apps.api.src.core.runner.blueprint_runner import GenerationRequest

    runner, tmp_db = _fresh_runner(translator)
    try:
        gen_request = GenerationRequest(
            problem_form=entry["form"],
            lesson_id=entry["lesson_id"],
            target_level=entry["target_level"],
            seed=entry["pinned_seed"],
        )
        lesson_mapping = mapping[entry["lesson_id"]]
        return runner.run(gen_request, lesson_mapping)
    finally:
        try:
            Path(tmp_db).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GeneratedProblem -> product JSON 形状への変換（gemini engine）
# ---------------------------------------------------------------------------


def _resolve_diagram_svg(diagram_url: Optional[str]) -> Optional[str]:
    """diagram_url が `/diagrams/{seed}.svg` 形式なら、対応する SVG ファイルの本文を返す。

    G7 が整形式 XML として検査できるよう、URL パスの代わりに SVG 本文そのものを
    problem_diagram_url に格納するための変換。読めない場合は None を返す
    （呼び出し側で url のままにフォールバックする）。
    """
    if not diagram_url:
        return None
    m = re.match(r"^/diagrams/(?P<name>[^/]+\.svg)$", diagram_url)
    if not m:
        return None
    svg_path = DIAGRAM_CACHE_DIR / m.group("name")
    if not svg_path.exists():
        return None
    try:
        return svg_path.read_text(encoding="utf-8")
    except Exception:
        return None


def generated_problem_to_product(result: Any, problem_form: str) -> dict[str, Any]:
    """GeneratedProblem を product JSON 形状（ProblemGenerationResponse 相当）に変換する。

    visual 対策: diagram_url が読めれば SVG 本文を problem_diagram_url に格納する。
    """
    mr = result.middle_representation
    sub_texts_by_label: dict[str, str] = {
        sq.get("label", ""): sq.get("text", "") for sq in (result.sub_question_texts or [])
    }
    exp_raw = result.explanation_text
    exp_map: dict[str, str] = exp_raw if isinstance(exp_raw, dict) else {"_all": exp_raw or ""}

    svg_body = _resolve_diagram_svg(result.diagram_url)
    problem_diagram_url = svg_body if svg_body is not None else result.diagram_url

    sub_questions = []
    for i, sq in enumerate(mr.sub_questions):
        sub_questions.append(
            {
                "label": sq.label,
                "prompt_text": sub_texts_by_label.get(sq.label, sq.prompt_hint),
                "answer": {
                    "type": sq.answer.type,
                    "sympy_form": str(sq.answer.sympy_form) if sq.answer.sympy_form is not None else None,
                    "text_form": sq.answer.text_form,
                    "extras": sq.answer.extras or {},
                },
                "explanation_text": exp_map.get(sq.label) or (exp_map.get("_all") if i == 0 else None),
            }
        )

    return {
        "content_problem_text": result.problem_text,
        "sub_questions": sub_questions,
        "visuals": {
            "problem_diagram_url": problem_diagram_url,
            "explanation_diagram_url": None,
        },
        "metadata": {
            "base_difficulty": 0,
            "adjustment_delta": 0,
            "used_atoms": sorted(mr.selected_tags or []),
            "seed": mr.seed,
            "blueprint_id": mr.blueprint_id,
            "blueprint_version": mr.blueprint_version,
            "problem_form": problem_form,
        },
    }


# ---------------------------------------------------------------------------
# engine=gemini: 実 LLMTranslator (SKIP_LLM を強制しない) で翻訳
# ---------------------------------------------------------------------------


def build_gemini_product(entry: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    from apps.api.src.core.llm.translator import LLMTranslator

    translator = LLMTranslator()
    result = _run_generation(entry, mapping, translator)
    return generated_problem_to_product(result, entry["form"])


# ---------------------------------------------------------------------------
# engine=claude: --dump / --ingest
# ---------------------------------------------------------------------------


def _build_dump_prompts(entry: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    """entry から MR を生成し、Gemini translator が組むのと同一のプロンプト文字列を作る。

    EXPLANATION_TRANSLATION_PROMPT は problem_text に依存するため、dump 時点ではまだ
    存在しない。ここでは1回のClaude呼び出しで両方（問題文＋解説）を作らせるため、
    問題文プロンプトと解説プロンプトの骨格（logic_steps_yaml 部分)を両方 staging に渡し、
    Claude 側に「まず problem_text を作り、それを用いて解説を作る」ことを明示した
    合成プロンプトを1本にまとめて書き出す。

    これは translator.LLMTranslator._translate_problem / _translate_explanation の
    プロンプト文字列を忠実に再現しつつ、2段階呼び出しをClaudeの1回の応答で完結させるための
    実務上の適応である（Opus設計メモに残す: 本来の Gemini フローは
    「問題文生成 -> 検証 -> 解説生成」の2回のLLM呼び出しだが、Claudeによる人手/半自動翻訳では
    1回の応答で両方を作らせる方が運用上シンプルなため）。
    """
    from apps.api.src.core.llm.translator import LLMTranslator
    from apps.api.src.core.llm.prompts import EXPLANATION_TRANSLATION_PROMPT, PROBLEM_TRANSLATION_PROMPT

    # LLM を呼ばずに MR だけ得るため、SKIP_LLM_IN_TESTS を一時的に立てて生成する
    prev = os.environ.get("SKIP_LLM_IN_TESTS")
    os.environ["SKIP_LLM_IN_TESTS"] = "true"
    try:
        translator = LLMTranslator()
        result = _run_generation(entry, mapping, translator)
    finally:
        if prev is None:
            os.environ.pop("SKIP_LLM_IN_TESTS", None)
        else:
            os.environ["SKIP_LLM_IN_TESTS"] = prev

    mr = result.middle_representation
    lesson_mapping = mapping[entry["lesson_id"]]

    # translator の内部関数を再利用してプロンプト構築を忠実に再現する
    problem_prompt = PROBLEM_TRANSLATION_PROMPT.format(
        grade=int(lesson_mapping.get("grade", 1)),
        lesson_title=str(lesson_mapping.get("title", "")) or "（未指定）",
        target_difficulty=int(mr.difficulty_score),
        few_shot_examples=translator._load_few_shots(mr.blueprint_id),
        middle_representation_yaml=translator._mr_to_yaml(mr),
        story_context_yaml="（なし）",
    )
    explanation_prompt_template = EXPLANATION_TRANSLATION_PROMPT.format(
        grade=int(lesson_mapping.get("grade", 1)),
        problem_text="（上記の問題文生成ステップで作った problem_text をここに使う）",
        logic_steps_yaml=translator._mr_logic_steps_yaml(mr),
        few_shot_examples=translator._load_few_shots(mr.blueprint_id),
    )

    combined_prompt = (
        "# ステップ1: 問題文生成\n\n"
        + problem_prompt
        + "\n\n---\n\n"
        + "# ステップ2: 解説生成\n\n"
        + "ステップ1で作った problem_text を用いて、以下のプロンプトに従い解説を作成してください。\n\n"
        + explanation_prompt_template
        + "\n\n---\n\n"
        + "# 最終出力形式（JSON のみ、上記2ステップの結果を1つのJSONにまとめる）\n"
        + json.dumps(
            {
                "content_problem_text": "（ステップ1の problem_text）",
                "sub_questions": [
                    {
                        "label": "(1)",
                        "prompt_text": "（ステップ1の sub_question_texts[0].text）",
                        "explanation_text": "（ステップ2の該当小問の解説）",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )

    mr_summary = {
        "key": entry["key"],
        "lesson_id": entry["lesson_id"],
        "form": entry["form"],
        "level_label": entry["level_label"],
        "target_level": entry["target_level"],
        "pinned_seed": entry["pinned_seed"],
        "blueprint_id": mr.blueprint_id,
        "blueprint_version": mr.blueprint_version,
        "seed": mr.seed,
        "selected_tags": mr.selected_tags,
        "difficulty_score": mr.difficulty_score,
        "diagram_url": result.diagram_url,
        "sub_questions": [
            {
                "label": sq.label,
                "prompt_hint": sq.prompt_hint,
                "answer": {
                    "type": sq.answer.type,
                    "sympy_form": str(sq.answer.sympy_form) if sq.answer.sympy_form is not None else None,
                    "text_form": sq.answer.text_form,
                    "extras": sq.answer.extras or {},
                },
            }
            for sq in mr.sub_questions
        ],
    }

    return {"prompt": combined_prompt, "mr_summary": mr_summary}


def dump_claude_prompts(
    gt_dir: Path = GROUND_TRUTH_DIR,
    out_dir: Path = PRODUCT_DIR,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
) -> dict[str, Any]:
    """claude engine の --dump: staging に prompt.txt と mr.json を書き出す。"""
    mapping = _load_mapping()
    entries = load_gt_keys(gt_dir, lesson_filter, form_filter)

    staging_dir = out_dir / "claude" / "_staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    dumped: list[str] = []
    failed: list[dict[str, Any]] = []

    for entry in entries:
        key = entry["key"]
        try:
            built = _build_dump_prompts(entry, mapping)
            (staging_dir / f"{key}.prompt.txt").write_text(built["prompt"], encoding="utf-8")
            (staging_dir / f"{key}.mr.json").write_text(
                json.dumps(built["mr_summary"], ensure_ascii=False, indent=2), encoding="utf-8"
            )
            dumped.append(key)
        except Exception as exc:  # noqa: BLE001
            failed.append({"key": key, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})

    return {"dumped": dumped, "failed": failed, "staging_dir": str(staging_dir)}


def _extract_answer_from_gt(gt_data: dict[str, Any], label: str) -> dict[str, Any]:
    """GT の sub_questions から label に対応する answer を取り出す（LLM は答えを変えない）。"""
    for sq in gt_data.get("sub_questions", []) or []:
        if sq.get("label") == label:
            answer = sq.get("answer") or {}
            return {
                "type": answer.get("type", "numeric"),
                "sympy_form": answer.get("sympy_form"),
                "text_form": answer.get("text_form", ""),
                "extras": answer.get("extras", {}) or {},
            }
    return {"type": "numeric", "sympy_form": None, "text_form": "", "extras": {}}


def parse_claude_response(response_data: dict[str, Any], gt_data: dict[str, Any], problem_form: str) -> dict[str, Any]:
    """Claude が書き戻した応答 JSON を product JSON 形状に組み立てる。

    translator と同じ「answer は GT(SymPy) の値を使う」方針: response の sub_questions には
    prompt_text/explanation_text のみを期待し、answer は常に gt_data から取る。
    図がある場合は response 側の svg フィールドをそのまま problem_diagram_url に使う。
    """
    content_problem_text = response_data.get("content_problem_text", "")
    resp_sub_questions = response_data.get("sub_questions", []) or []

    gt_labels = [sq.get("label", "") for sq in gt_data.get("sub_questions", []) or []]

    sub_questions = []
    for i, gt_label in enumerate(gt_labels):
        resp_sq = resp_sub_questions[i] if i < len(resp_sub_questions) else {}
        # label が response 側に無ければ GT のラベルを使う（response は基本 GT と同じ順序を想定）
        resp_label = resp_sq.get("label") or gt_label
        sub_questions.append(
            {
                "label": resp_label or gt_label,
                "prompt_text": resp_sq.get("prompt_text", ""),
                "answer": _extract_answer_from_gt(gt_data, gt_label),
                "explanation_text": resp_sq.get("explanation_text"),
            }
        )

    diagram_url = response_data.get("problem_diagram_url") or response_data.get("svg")
    visuals = response_data.get("visuals") or {}
    if not diagram_url:
        diagram_url = visuals.get("problem_diagram_url")

    return {
        "content_problem_text": content_problem_text,
        "sub_questions": sub_questions,
        "visuals": {
            "problem_diagram_url": diagram_url,
            "explanation_diagram_url": visuals.get("explanation_diagram_url"),
        },
        "metadata": {
            "base_difficulty": 0,
            "adjustment_delta": 0,
            "used_atoms": sorted(gt_data.get("selected_tags", []) or []),
            "seed": gt_data.get("seed"),
            "blueprint_id": gt_data.get("blueprint_id", ""),
            "blueprint_version": gt_data.get("blueprint_version", "1.0"),
            "problem_form": problem_form,
        },
    }


def ingest_claude_responses(
    gt_dir: Path = GROUND_TRUTH_DIR,
    out_dir: Path = PRODUCT_DIR,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
) -> dict[str, Any]:
    """claude engine の --ingest: _responses/{key}.json を読み product/{key}.json を書く。"""
    entries = load_gt_keys(gt_dir, lesson_filter, form_filter)

    responses_dir = out_dir / "claude" / "_responses"
    claude_out_dir = out_dir / "claude"
    claude_out_dir.mkdir(parents=True, exist_ok=True)

    ingested: list[str] = []
    missing: list[str] = []
    failed: list[dict[str, Any]] = []

    for entry in entries:
        key = entry["key"]
        response_path = responses_dir / f"{key}.json"
        if not response_path.exists():
            missing.append(key)
            continue
        try:
            response_data = json.loads(response_path.read_text(encoding="utf-8"))
            product = parse_claude_response(response_data, entry["gt_data"], entry["form"])
            out_path = claude_out_dir / f"{key}.json"
            out_path.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
            ingested.append(key)
        except Exception as exc:  # noqa: BLE001
            failed.append({"key": key, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})

    return {"ingested": ingested, "missing": missing, "failed": failed}


# ---------------------------------------------------------------------------
# engine=gemini の一括実行
# ---------------------------------------------------------------------------


def build_gemini_corpus(
    gt_dir: Path = GROUND_TRUTH_DIR,
    out_dir: Path = PRODUCT_DIR,
    lesson_filter: Optional[str] = None,
    form_filter: Optional[str] = None,
) -> dict[str, Any]:
    mapping = _load_mapping()
    entries = load_gt_keys(gt_dir, lesson_filter, form_filter)

    gemini_out_dir = out_dir / "gemini"
    gemini_out_dir.mkdir(parents=True, exist_ok=True)

    generated: list[str] = []
    failed: list[dict[str, Any]] = []

    for entry in entries:
        key = entry["key"]
        try:
            product = build_gemini_product(entry, mapping)
            out_path = gemini_out_dir / f"{key}.json"
            out_path.write_text(json.dumps(product, ensure_ascii=False, indent=2), encoding="utf-8")
            generated.append(key)
        except Exception as exc:  # noqa: BLE001
            failed.append({"key": key, "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc()})

    return {"generated": generated, "failed": failed}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", choices=["gemini", "claude"], required=True)
    parser.add_argument("--dump", action="store_true", help="claude engine: プロンプトを staging に書き出す")
    parser.add_argument("--ingest", action="store_true", help="claude engine: _responses を取り込んで product を作る")
    parser.add_argument("--lesson", default=None, help="この lesson_id だけ処理する（デバッグ用）")
    parser.add_argument("--form", default=None, help="この problem_form だけ処理する（デバッグ用）")
    parser.add_argument("--gt-dir", default=str(GROUND_TRUTH_DIR))
    parser.add_argument("--out-dir", default=str(PRODUCT_DIR))
    args = parser.parse_args()

    gt_dir = Path(args.gt_dir)
    out_dir = Path(args.out_dir)

    if args.engine == "gemini":
        summary = build_gemini_corpus(gt_dir, out_dir, args.lesson, args.form)
        print(f"生成成功: {len(summary['generated'])} / 失敗: {len(summary['failed'])}")
        for f in summary["failed"]:
            print(f"  {f['key']}: {f['error']}")
    else:  # claude
        if args.dump and args.ingest:
            print("--dump と --ingest は同時指定できません", file=sys.stderr)
            sys.exit(1)
        if not args.dump and not args.ingest:
            print("claude engine には --dump または --ingest が必要です", file=sys.stderr)
            sys.exit(1)
        if args.dump:
            summary = dump_claude_prompts(gt_dir, out_dir, args.lesson, args.form)
            print(f"dump成功: {len(summary['dumped'])} / 失敗: {len(summary['failed'])}")
            print(f"staging: {summary['staging_dir']}")
            for f in summary["failed"]:
                print(f"  {f['key']}: {f['error']}")
        else:
            summary = ingest_claude_responses(gt_dir, out_dir, args.lesson, args.form)
            print(
                f"ingest成功: {len(summary['ingested'])} / "
                f"response無し: {len(summary['missing'])} / 失敗: {len(summary['failed'])}"
            )
            for f in summary["failed"]:
                print(f"  {f['key']}: {f['error']}")


if __name__ == "__main__":
    main()
