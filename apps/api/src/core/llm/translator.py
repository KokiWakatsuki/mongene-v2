"""Gemini API 統合（§40）

テスト時は SKIP_LLM_IN_TESTS=true で `translate` 関数をモックする。
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from apps.api.src.core.exceptions import LLMRateLimitError, LLMTranslationFailedError
from apps.api.src.core.llm.fallback import template_fallback_text
from apps.api.src.core.llm.prompts import (
    EXPLANATION_TRANSLATION_PROMPT,
    PROBLEM_TRANSLATION_PROMPT,
)
from apps.api.src.core.representation.middle_representation import MiddleRepresentation

ModelTier = Literal["lite", "standard", "reasoning"]

MODEL_NAMES = {
    "lite": os.environ.get("GEMINI_MODEL_LITE", "gemini-3.1-flash-lite"),
    "standard": os.environ.get("GEMINI_MODEL_STANDARD", "gemini-3-flash"),
    "reasoning": os.environ.get("GEMINI_MODEL_REASONING", "gemini-3-flash"),
}

THINKING_BUDGETS = {
    "lite": 0,
    "standard": 4096,
    "reasoning": 16384,
}


def _is_skip_mode() -> bool:
    return os.environ.get("SKIP_LLM_IN_TESTS", "").lower() in ("1", "true", "yes")


def call_gemini(prompt: str, tier: ModelTier = "standard", retries: int = 3) -> str:
    """Gemini モデル呼び出し（実呼び出し、google-genai 新 SDK ベース）

    テストではモジュール属性として monkeypatch される想定。
    """
    if _is_skip_mode():
        return _fake_response(prompt)

    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as e:
        raise LLMTranslationFailedError(f"google-genai 未インストール: {e}")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise LLMTranslationFailedError("GEMINI_API_KEY が設定されていません")

    client = genai.Client(api_key=api_key)
    model_name = MODEL_NAMES[tier]
    # tier ごとに thinking_budget を変える（§8.4）
    # lite: 0（思考なし）/ standard: 4096（medium）/ reasoning: 16384（high）
    thinking_budget = THINKING_BUDGETS[tier]
    temperature = 0.7 if tier == "standard" else 0.3

    last_err: Optional[Exception] = None
    for attempt in range(retries):
        try:
            config = genai_types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=8192,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=thinking_budget),
            )
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            text = response.text
            if text is None or not text.strip():
                raise LLMTranslationFailedError(f"{model_name} が空応答を返した")
            return text
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "429" in msg or "rate" in msg or "exhausted" in msg or "quota" in msg or "resource_exhausted" in msg:
                if attempt < retries - 1:
                    time.sleep(2**attempt)
                    continue
                raise LLMRateLimitError(f"{model_name} の上限到達: {e}")
            if attempt < retries - 1:
                time.sleep(1)
                continue
            raise LLMTranslationFailedError(f"{model_name} 呼び出し失敗: {e}")

    raise LLMTranslationFailedError(f"{model_name} で最終的に失敗: {last_err}")


def _fake_response(prompt: str) -> str:
    """SKIP_LLM_IN_TESTS=true 時のスタブ応答"""
    if "problem_text" in prompt and "sub_question_texts" in prompt:
        return json.dumps(
            {
                "problem_text": "TEST 問題: 次の計算をしなさい。",
                "sub_question_texts": [{"label": "(1)", "text": "計算結果を求めなさい。"}],
            },
            ensure_ascii=False,
        )
    if "explanation_text" in prompt:
        return json.dumps(
            {
                "explanation_text": "TEST 解説: 順序に従って計算します。",
                "sub_question_explanations": [{"label": "(1)", "text": "TEST 中間説明"}],
            },
            ensure_ascii=False,
        )
    return "TEST 出力"


def _strip_json_fence(raw: str) -> str:
    """```json ... ``` のフェンスを剥がす"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class LLMTranslator:
    """§29 のプロンプトを使って翻訳する"""

    def __init__(self, few_shot_loader: Optional[Any] = None) -> None:
        self.few_shot_loader = few_shot_loader

    def translate(
        self,
        mr: MiddleRepresentation,
        story: Any = None,
        lesson_grade: int = 1,
        lesson_title: str = "",
        target_difficulty: int = 50,
    ) -> Tuple[str, List[Dict], Dict[str, str]]:
        """中間表現 → (問題文, 小問テキストリスト, サブ問題ごとの解説 dict)

        戻り値 3 番目は {"_all": "全体解説", "(1)": "...", "(2)": "..."} 形式の辞書。
        """
        from apps.api.src.core.evaluation.accuracy import verify_accuracy

        last_err: Optional[Exception] = None
        for tier in ("standard", "reasoning", "lite"):
            try:
                problem_text, sub_texts = self._translate_problem(
                    mr, story, lesson_grade, tier, lesson_title, target_difficulty  # type: ignore[arg-type]
                )
                if not self._verify_translation(problem_text, mr, sub_texts):
                    last_err = LLMTranslationFailedError("解答漏洩を検出")
                    continue
                explanation_map = self._translate_explanation(
                    mr, problem_text, lesson_grade, tier  # type: ignore[arg-type]
                )
                # Accuracy 検証: 解説内に SymPy 答えが含まれているかを確認（警告のみ、リジェクトしない）
                # ※ 厳格なリジェクトにすると rate limit 環境で全 tier 失敗 → fallback になるため
                for sq in mr.sub_questions:
                    if sq.answer.sympy_form is None:
                        continue
                    exp_text = explanation_map.get(sq.label) or explanation_map.get("_all", "")
                    if exp_text and not verify_accuracy(exp_text, sq.answer.sympy_form):
                        import logging
                        logging.getLogger(__name__).warning(
                            "Accuracy 不一致: %s の解説に答え %s が含まれていない可能性",
                            sq.label, sq.answer.sympy_form,
                        )
                return problem_text, sub_texts, explanation_map
            except LLMRateLimitError as e:
                last_err = e
                continue
            except LLMTranslationFailedError as e:
                last_err = e
                continue

        return self._fallback_template(mr)

    def _translate_problem(
        self,
        mr: MiddleRepresentation,
        story: Any,
        grade: int,
        tier: ModelTier,
        lesson_title: str = "",
        target_difficulty: int = 50,
    ) -> Tuple[str, List[Dict]]:
        prompt = PROBLEM_TRANSLATION_PROMPT.format(
            grade=grade,
            lesson_title=lesson_title or "（未指定）",
            target_difficulty=target_difficulty,
            few_shot_examples=self._load_few_shots(mr.blueprint_id),
            middle_representation_yaml=self._mr_to_yaml(mr),
            story_context_yaml=self._story_to_yaml(story) if story else "（なし）",
        )
        raw = call_gemini(prompt, tier=tier)
        parsed = self._parse_json_response(raw)
        return parsed["problem_text"], parsed.get("sub_question_texts", [])

    def _translate_explanation(
        self,
        mr: MiddleRepresentation,
        problem_text: str,
        grade: int,
        tier: ModelTier,
    ) -> Dict[str, str]:
        prompt = EXPLANATION_TRANSLATION_PROMPT.format(
            grade=grade,
            problem_text=problem_text,
            logic_steps_yaml=self._mr_logic_steps_yaml(mr),
            few_shot_examples=self._load_few_shots(mr.blueprint_id),
        )
        raw = call_gemini(prompt, tier=tier)
        parsed = self._parse_json_response(raw)
        result: Dict[str, str] = {"_all": parsed.get("explanation_text", "")}
        for item in parsed.get("sub_question_explanations", []):
            label = item.get("label", "")
            text = item.get("text", "")
            if label and text:
                result[label] = text
        return result

    def _verify_translation(
        self,
        problem_text: str,
        mr: MiddleRepresentation,
        sub_texts: Optional[List[Dict]] = None,
    ) -> bool:
        """LLM 出力テキストの解答漏洩を決定論ゲート（G1 と同一コア）で検査する。

        generate-then-verify 反転（HANDOFF §4）: オフライン評価ゲート G1 の共有コア
        `find_problem_answer_leak` を受理/棄却フィルタとして使う。正解値（LaTeX/分数/
        符号異体字を正規化）が問題文・小問プロンプトに漏れていれば False（棄却→次 tier）。
        入力オペランドと一致する曖昧ケースは棄却しない（誤棄却回避）。
        """
        try:
            from apps.api.src.core.evaluation.leakage import find_problem_answer_leak

            sub_prompt_texts = [
                (item.get("text", "") or "") for item in (sub_texts or [])
            ]
            leaked = find_problem_answer_leak(
                problem_text, sub_prompt_texts, mr, numeric_only=True
            )
            return not leaked
        except Exception:
            return True

    def _fallback_template(self, mr: MiddleRepresentation) -> Tuple[str, List[Dict], Dict[str, str]]:
        text = template_fallback_text(mr)
        return text, [], {"_all": ""}

    def _load_few_shots(self, blueprint_id: str) -> str:
        """§8.3: master_data/few_shot_seeds/ から Blueprint に対応する例を読み込む"""
        if self.few_shot_loader is not None:
            try:
                return self.few_shot_loader(blueprint_id)
            except Exception:
                pass
        # デフォルト: ファイルシステムから直接読み込む
        try:
            from pathlib import Path
            import yaml as _yaml
            seeds_dir = Path(__file__).resolve().parents[5] / "master_data" / "few_shot_seeds"
            examples: list[str] = []
            # blueprint_id にマッチするファイルを検索
            for f in sorted(seeds_dir.glob("*.yaml")):
                data = _yaml.safe_load(f.read_text(encoding="utf-8"))
                for ex in (data.get("examples") or []):
                    mr = ex.get("input_middle_representation", {})
                    if mr.get("problem_structure_type") == blueprint_id:
                        examples.append(
                            f"問題例:\n{ex.get('ideal_problem_text','').strip()}\n"
                            f"解説例:\n{ex.get('ideal_explanation_text','').strip()}"
                        )
            if examples:
                return "\n\n---\n\n".join(examples[:2])  # 最大 2 例
        except Exception:
            pass
        return "（Few-Shot 例なし）"

    def _mr_to_yaml(self, mr: MiddleRepresentation) -> str:
        import yaml

        data = {
            "problem_structure_type": mr.problem_structure_type,
            "selected_tags": mr.selected_tags,
            "difficulty_score": mr.difficulty_score,
            "problem_form": mr.problem_form,
            "sampled_atoms": mr.sampled_nouns_info,  # LLM が Atom 型を正しく呼ぶための情報
            "sub_questions": [
                {
                    "label": sq.label,
                    "prompt_hint": sq.prompt_hint,
                    "answer": {
                        "type": sq.answer.type,
                        "sympy_form": str(sq.answer.sympy_form),
                        "text_form": sq.answer.text_form,
                        **({"extras": sq.answer.extras} if sq.answer.extras else {}),
                    },
                }
                for sq in mr.sub_questions
            ],
        }
        # visual_dsl の要点を追加（render_type と主要 elements のラベルのみ）
        if mr.visual_dsl:
            data["visual_summary"] = {
                "render_type": mr.visual_dsl.render_type,
                "element_labels": [
                    e.get("label", e.get("type", str(i)))
                    for i, e in enumerate(mr.visual_dsl.elements or [])
                ],
            }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    def _mr_logic_steps_yaml(self, mr: MiddleRepresentation) -> str:
        import yaml

        data = []
        for sq in mr.sub_questions:
            data.append(
                {
                    "label": sq.label,
                    "steps": [
                        {
                            "operation_name": s.operation_name,
                            "operands": s.operands,
                            "sympy_expr": str(s.sympy_expr),
                            "narration_hint": s.narration_hint,
                        }
                        for s in sq.logic_steps
                    ],
                }
            )
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    def _story_to_yaml(self, story: Any) -> str:
        import yaml

        return yaml.safe_dump(story.__dict__, allow_unicode=True, sort_keys=False)

    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        text = _strip_json_fence(raw)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise LLMTranslationFailedError(f"JSON パース失敗: {e}; raw={text[:200]}")


def translate(prompt: str, model: str = "standard") -> str:
    """conftest.py の monkeypatch ターゲット。

    実環境では call_gemini を呼ぶが、テスト時は SKIP_LLM_IN_TESTS で _fake_response。
    """
    tier: ModelTier = "standard"
    if model in ("lite", "standard", "reasoning"):
        tier = model  # type: ignore[assignment]
    return call_gemini(prompt, tier=tier)
