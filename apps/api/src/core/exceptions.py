"""例外クラス定義（§30）"""
from __future__ import annotations


class MongeneError(Exception):
    """基底例外"""


class NoCompatibleBlueprintError(MongeneError):
    """指定 lesson + form + difficulty で適合する Blueprint がない"""


class UnsupportedFormError(MongeneError):
    """その lesson が指定 problem_form をサポートしていない"""


class NoCompatibleAtomError(MongeneError):
    """Blueprint のスロットに適合する Atom がない"""


class CleanSolutionExhaustedError(MongeneError):
    """規定リトライ回数内に綺麗な解が得られなかった"""


class VerbValidationError(MongeneError):
    """Verb の validate が False を返した"""

    def __init__(self, verb_name: str, reason: str | None = None) -> None:
        super().__init__(f"{verb_name}: {reason}")
        self.verb_name = verb_name
        self.reason = reason


class LLMTranslationFailedError(MongeneError):
    """LLM 翻訳が 3 回失敗"""


class LLMRateLimitError(MongeneError):
    """全モデルの RPD 上限到達"""


class NoScenarioFoundError(MongeneError):
    """WordProblemStructure で該当シナリオなし"""


class StandardsViolationError(MongeneError):
    """生成問題が学年範囲外の単元を含む"""


class DuplicationLoopError(MongeneError):
    """重複排除のリトライが上限に達した"""
