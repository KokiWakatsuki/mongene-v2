"""評価ゲート共通ユーティリティ（数値正規化・GateResult 定義）。

フェーズ2仕様書 `docs/phase2_eval_gates_spec.md` §3 冒頭:
「数値の照合は正規化して行う（全角/半角、`−`/`-`、`1/2` と `\\dfrac{1}{2}`、
`\\left(` 等の LaTeX 装飾を除去してから比較）」を実装する。

LLM は一切使わない。純粋な文字列処理のみ。
"""
from __future__ import annotations

import functools
import re
import unicodedata
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Literal, Optional

import yaml

Verdict = Literal["PASS", "FAIL", "WARN", "N/A"]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LEXICON_PATH = REPO_ROOT / "master_data" / "eval_lexicons.yaml"
DEFAULT_FORBIDDEN_WORDS_PATH = REPO_ROOT / "master_data" / "forbidden_words.txt"
DEFAULT_PREREQUISITE_GRAPH_PATH = REPO_ROOT / "master_data" / "prerequisite_graph.yaml"


@functools.lru_cache(maxsize=8)
def _load_yaml_cached(path_str: str) -> dict[str, Any]:
    path = Path(path_str)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_lexicons(path: Optional[Path] = None) -> dict[str, Any]:
    """`master_data/eval_lexicons.yaml` を読み込む（キャッシュ付き）。"""
    p = path or DEFAULT_LEXICON_PATH
    return _load_yaml_cached(str(p))


@functools.lru_cache(maxsize=8)
def load_forbidden_words(path: Optional[str] = None) -> tuple[str, ...]:
    p = Path(path) if path else DEFAULT_FORBIDDEN_WORDS_PATH
    if not p.exists():
        return tuple()
    words = []
    for line in p.read_text(encoding="utf-8").splitlines():
        w = line.strip()
        if w and not w.startswith("#"):
            words.append(w)
    return tuple(words)


@functools.lru_cache(maxsize=8)
def load_prerequisite_graph(path: Optional[str] = None) -> dict[str, dict[str, Any]]:
    """`prerequisite_graph.yaml` を lesson_id -> {title, grade, requires} の dict に変換。"""
    p = Path(path) if path else DEFAULT_PREREQUISITE_GRAPH_PATH
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    nodes = data.get("nodes", [])
    return {node["id"]: node for node in nodes if "id" in node}


@dataclass
class GateResult:
    """1ゲートの判定結果。

    `run_gates.py` から呼ぶときも、単体テストから呼ぶときも同じ形。
    """

    gate_id: str
    verdict: Verdict
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "verdict": self.verdict,
            "reason": self.reason,
            "details": self.details,
        }


# ---------------------------------------------------------------------------
# LaTeX 装飾除去・全角半角正規化
# ---------------------------------------------------------------------------

# \left( \right) \left[ \right] \left\{ \right\} 等の装飾コマンドを剥がす
_LATEX_LEFT_RIGHT_RE = re.compile(r"\\(?:left|right)\s*([(){}\[\]|.]|\\\{|\\\})")

# \dfrac{a}{b}, \frac{a}{b}, \tfrac{a}{b} → a/b に変換（ネストは非対応で十分）
_LATEX_FRAC_RE = re.compile(r"\\(?:dfrac|tfrac|frac)\s*\{([^{}]*)\}\s*\{([^{}]*)\}")

# マイナス記号の異体字: U+2212 (−), 全角マイナス (－) など
_MINUS_VARIANTS = {
    "−": "-",  # MINUS SIGN
    "－": "-",  # FULLWIDTH HYPHEN-MINUS
    "‐": "-",  # HYPHEN
    "–": "-",  # EN DASH
    "—": "-",  # EM DASH
}

# LaTeX の空白・装飾コマンドで数値抽出の邪魔になるもの
_LATEX_STRIP_COMMANDS = re.compile(
    r"\\(?:mathrm|mathbf|text|displaystyle|,|;|!|quad|qquad)\b"
)


def normalize_math_text(text: str) -> str:
    """数値比較のための正規化。全角→半角、マイナス異体字統一、LaTeX装飾除去。

    比較専用の正規化であり、表示用ではない。
    """
    if text is None:
        return ""
    s = str(text)

    # 全角英数記号 → 半角（NFKC）。ただし先にマイナス異体字を統一しておく
    for variant, ascii_minus in _MINUS_VARIANTS.items():
        s = s.replace(variant, ascii_minus)
    s = unicodedata.normalize("NFKC", s)
    # NFKC 後に再度マイナス異体字を統一（NFKCで復活するケースの保険）
    for variant, ascii_minus in _MINUS_VARIANTS.items():
        s = s.replace(variant, ascii_minus)

    # \dfrac{1}{2} 等 → (1/2) に。ネストしている場合は複数回適用
    prev = None
    while prev != s:
        prev = s
        s = _LATEX_FRAC_RE.sub(lambda m: f"({m.group(1)}/{m.group(2)})", s)

    # \left( \right) 等の装飾を除去（括弧文字自体は残す）
    s = _LATEX_LEFT_RIGHT_RE.sub(lambda m: m.group(1) if m.group(1) not in (r"\{", r"\}") else ("{" if m.group(1) == r"\{" else "}"), s)

    # その他装飾コマンド除去
    s = _LATEX_STRIP_COMMANDS.sub(" ", s)

    # $ や \( \) \[ \] のようなデリミタは比較には不要なので除去
    s = s.replace("$$", "").replace("$", "")
    s = s.replace(r"\(", "").replace(r"\)", "")
    s = s.replace(r"\[", "").replace(r"\]", "")

    # 連続空白を1つに
    s = re.sub(r"\s+", " ", s).strip()
    return s


_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:/\d+)?")


def extract_numbers(text: str) -> list[str]:
    """正規化済みテキストから数値トークン（整数・小数・分数 a/b）を抽出する。"""
    normalized = normalize_math_text(text)
    return _NUMBER_RE.findall(normalized)


def _to_fraction(token: str) -> Optional[Fraction]:
    token = token.strip()
    # (1/2) のように外側を丸括弧で包まれているケース（\dfrac 正規化後など）を剥がす
    while token.startswith("(") and token.endswith(")"):
        inner = token[1:-1]
        if not inner:
            break
        token = inner
    if not token:
        return None
    try:
        if "/" in token:
            num_str, den_str = token.split("/", 1)
            return Fraction(num_str) / Fraction(den_str)
        return Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None


def numbers_equal(a: str, b: str, tol: float = 1e-9) -> bool:
    """正規化した数値トークン同士が等価か（整数/小数/分数を横断して比較）。"""
    fa = _to_fraction(normalize_math_text(a))
    fb = _to_fraction(normalize_math_text(b))
    if fa is None or fb is None:
        return normalize_math_text(a) == normalize_math_text(b)
    return abs(float(fa - fb)) <= tol


def contains_number(text: str, value: str) -> bool:
    """`text` 中に（正規化後の）数値 `value` が出現するか。"""
    target = _to_fraction(normalize_math_text(value))
    if target is None:
        return normalize_math_text(value) in normalize_math_text(text)
    for tok in extract_numbers(text):
        cand = _to_fraction(tok)
        if cand is not None and abs(float(cand - target)) <= 1e-9:
            return True
    return False


def dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
