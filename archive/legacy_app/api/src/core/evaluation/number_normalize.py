"""数値正規化コア（LLMフリー・純粋な文字列処理）。

フェーズ2の評価ゲート（`scripts/eval_gates/common.py`）で作った正規化ロジックを
**app 層に置き**、オフライン評価（evaluator）とランタイム翻訳器（verifier）の両方から
同一実装を再利用できるようにする＝「evaluator = verifier」昇格の基盤（HANDOFF §4）。

- 全角/半角、`−`/`-`、`1/2` と `\\dfrac{1}{2}`、`\\left(` 等の LaTeX 装飾を正規化してから比較。
- LLM は一切使わない。

`scripts/eval_gates/common.py` はこのモジュールから re-export するので、既存ゲートの
import パス（`scripts.eval_gates.common`）は不変。
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction
from typing import Iterable, Optional

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


# 単項マイナスが括弧付きトークンと空白で分離しているケース（`- (1/3)` や `-(1/3)`）を
# 1トークンとして拾う分岐を先に試し、それ以外は従来通り整数・小数・分数 a/b を拾う。
# 例: "(- (1/3)) + (8/7)" -> ["- (1/3)", "8/7"]
_NUMBER_RE = re.compile(r"-\s*\([^()]*\)|-?\d+(?:\.\d+)?(?:/\d+)?")


def extract_numbers(text: str) -> list[str]:
    """正規化済みテキストから数値トークン（整数・小数・分数 a/b）を抽出する。"""
    normalized = normalize_math_text(text)
    return _NUMBER_RE.findall(normalized)


_LEADING_MINUS_PAREN_RE = re.compile(r"^-\s*\((?P<inner>.*)\)$")


def _to_fraction(token: str) -> Optional[Fraction]:
    token = token.strip()
    negate = False
    # "(1/2)" の外側丸括弧、および "- (1/3)" / "-(1/3)" の分離した単項マイナスを
    # 交互に剥がしていく（例: "(- (1/2))" -> "- (1/2)" -> "(1/2)" -> "1/2"）。
    changed = True
    while changed:
        changed = False
        m = _LEADING_MINUS_PAREN_RE.match(token)
        if m:
            token = m.group("inner").strip()
            negate = not negate
            changed = True
            continue
        if token.startswith("(") and token.endswith(")"):
            inner = token[1:-1].strip()
            if inner:
                token = inner
                changed = True
    if not token:
        return None
    try:
        if "/" in token:
            num_str, den_str = token.split("/", 1)
            result = Fraction(num_str) / Fraction(den_str)
        else:
            result = Fraction(token)
    except (ValueError, ZeroDivisionError):
        return None
    return -result if negate else result


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
