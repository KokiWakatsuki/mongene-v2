"""セル制作ツール（実装設計 §10・§8.3・Task7）— spec preview / check / approve。

`engine.tools` は core/packs/curriculum を「読むだけ」（curriculum/families は
generate() の既定ディレクトリ読み込みに委ねる。families を直接ロードするのは
preview の全レベル列挙のためのみ）。本ファイルは engine/core・engine/packs・
engine/curriculum のいずれも変更しない（読み取り専用の利用者）。

サブコマンド:
  spec preview <family> [--seeds N] [--out PATH]
  spec check <family>
  spec approve <family> [--golden-dir DIR] [--diff]

すべて `bootstrap()` を先頭で呼んでから `engine.core.pipeline.generate()` を
呼ぶ（pack 登録 + 品質ゲート install が済んだ状態でないと generate は使えない）。
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from engine.bootstrap import bootstrap
from engine.core.contracts import GenerateRequest, Problem, SpecFamily, Unsupported
from engine.core.pipeline import generate
from engine.core.spec.lint import LintError, lint_family
from engine.core.spec.loader import load_family_dir

# **パッケージからの相対で決める（CWD に依存させない）。**
# 前は `Path("engine/curriculum/math/families")` で、リポジトリの根から
# 実行することが暗黙の前提だった。エンジンを別のリポジトリへ持ち出したり、
# 別のディレクトリから呼んだ瞬間に「family が1つも見つからない」で止まる。
_ENGINE_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FAMILIES_DIR = _ENGINE_ROOT / "curriculum" / "math" / "families"

# golden は**パッケージの外**（テストと一緒）に置く。エンジンだけを持ち出したときは
# ここが無い。承認は開発用の道具なので、無ければ `--golden-dir` で渡す。
_DEFAULT_GOLDEN_DIR = _ENGINE_ROOT.parent / "tests" / "golden"

# ---------------------------------------------------------------------------
# 共通ヘルパ
# ---------------------------------------------------------------------------


def _load_target_family(family_name: str, families_dir: Path = _DEFAULT_FAMILIES_DIR) -> SpecFamily | None:
    """指定 family 名の SpecFamily を families_dir から読む。無ければ None。"""
    families = load_family_dir(families_dir)
    return families.get(family_name)


def _sorted_levels(spec: SpecFamily) -> list[tuple[str, int]]:
    """levels を level 番号昇順で (level_key, level) にして返す。"""
    items = [(key, lvl.level) for key, lvl in spec.levels.items()]
    return sorted(items, key=lambda kv: kv[1])


def _unit_from_family(family_name: str) -> str:
    """"math.<unit>.<form>" -> "<unit>"。"""
    parts = family_name.split(".", 2)
    if len(parts) != 3:
        raise ValueError(f"family 名の形式が不正（math.<unit>.<form> を期待）: {family_name!r}")
    return parts[1]


# ---------------------------------------------------------------------------
# spec preview
# ---------------------------------------------------------------------------


def _run_preview(family_name: str, seeds: int, out: Path, families_dir: Path = _DEFAULT_FAMILIES_DIR) -> int:
    bootstrap()
    spec = _load_target_family(family_name, families_dir)
    if spec is None:
        print(json.dumps({"error": f"family 未検出: {family_name!r}"}, ensure_ascii=False))
        return 1

    unit = _unit_from_family(family_name)
    html_doc = _render_preview_html(spec, unit, seeds)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    print(json.dumps({"wrote": str(out), "family": family_name, "seeds": seeds}, ensure_ascii=False))
    return 0


def _render_preview_html(spec: SpecFamily, unit: str, seeds: int) -> str:
    parts: list[str] = []
    parts.append("<!doctype html><html><head><meta charset=\"utf-8\">")
    parts.append(f"<title>preview: {html_lib.escape(spec.family)}</title>")
    parts.append(_PREVIEW_CSS)
    parts.append("</head><body>")
    parts.append(f"<h1>{html_lib.escape(spec.family)}</h1>")
    parts.append(f"<p class=\"form\">form: {html_lib.escape(spec.form)}</p>")

    for level_key, level_num in _sorted_levels(spec):
        spec_level = spec.levels[level_key]
        parts.append("<section class=\"level\">")
        parts.append(f"<h2>Level {level_num} <span class=\"sig\">signature={html_lib.escape(spec_level.signature)}</span></h2>")
        parts.append("<div class=\"source-desc\"><strong>source_desc:</strong><pre>"
                      f"{html_lib.escape(spec.source_desc)}</pre></div>")

        for seed in range(1, seeds + 1):
            req = GenerateRequest(subject="math", unit=unit, form=spec.form, level=level_num, seed=seed)
            result = generate(req)
            parts.append(_render_cell_html(seed, result))

        parts.append("</section>")

    parts.append("</body></html>")
    return "\n".join(parts)


def _render_cell_html(seed: int, result: Problem | Unsupported) -> str:
    if isinstance(result, Unsupported):
        return (
            "<div class=\"cell error\">"
            f"<div class=\"seed\">seed={seed}</div>"
            f"<div class=\"unsupported\">Unsupported: {html_lib.escape(result.code)} — "
            f"{html_lib.escape(result.detail)}</div>"
            "</div>"
        )

    svg_block = ""
    if result.visual_svg:
        svg_block = f"<div class=\"visual\">{result.visual_svg}</div>"

    sub_blocks: list[str] = []
    for sq in result.sub_questions:
        answer_display = getattr(sq.answer, "display", None) or getattr(sq.answer, "correct", "")
        hints_html = "".join(f"<li>{html_lib.escape(h)}</li>" for h in sq.hints)
        sub_blocks.append(
            "<div class=\"subq\">"
            f"<div class=\"label\">{html_lib.escape(sq.label)}</div>"
            f"<div class=\"prompt\">{html_lib.escape(sq.prompt_text)}</div>"
            f"<div class=\"answer\">answer: {html_lib.escape(str(answer_display))}</div>"
            f"<div class=\"explanation\">{html_lib.escape(sq.explanation)}</div>"
            f"<ul class=\"hints\">{hints_html}</ul>"
            f"<div class=\"tags\">concept_tags: {html_lib.escape(', '.join(sq.concept_tags))}</div>"
            "</div>"
        )

    meta = result.meta
    meta_html = (
        f"signature={html_lib.escape(meta.signature)} seed={meta.seed} "
        f"concept_tags={html_lib.escape(', '.join(meta.concept_tags))}"
    )

    return (
        "<div class=\"cell ok\">"
        f"<div class=\"seed\">seed={seed}</div>"
        f"<div class=\"problem-text\">{html_lib.escape(result.problem_text)}</div>"
        f"{svg_block}"
        f"{''.join(sub_blocks)}"
        f"<div class=\"meta\">{meta_html}</div>"
        "</div>"
    )


_PREVIEW_CSS = """
<style>
body { font-family: sans-serif; margin: 2rem; background: #fafafa; color: #222; }
h1 { margin-bottom: 0; }
.form { color: #666; margin-top: 0.2rem; }
.level { border: 1px solid #ccc; border-radius: 8px; padding: 1rem; margin: 1.5rem 0; background: #fff; }
.level h2 { margin-top: 0; }
.sig { font-size: 0.8rem; color: #888; font-weight: normal; }
.source-desc pre { white-space: pre-wrap; background: #f0f0f0; padding: 0.5rem; border-radius: 4px; }
.cell { border-top: 1px dashed #ddd; padding: 0.75rem 0; }
.cell.error { color: #b00020; background: #fff0f0; padding: 0.75rem; border-radius: 6px; }
.unsupported { font-weight: bold; }
.seed { font-size: 0.8rem; color: #888; }
.problem-text { font-size: 1.05rem; margin: 0.3rem 0; }
.subq { margin-left: 1rem; padding: 0.4rem 0; }
.answer { color: #0a6b0a; }
.explanation { color: #444; }
.hints { color: #555; }
.tags { font-size: 0.8rem; color: #888; }
.meta { font-size: 0.75rem; color: #999; margin-top: 0.3rem; }
.visual { margin: 0.5rem 0; }
</style>
"""


# ---------------------------------------------------------------------------
# spec check
# ---------------------------------------------------------------------------

_DUP_RATE_WARN_THRESHOLD = 0.20  # M0 は警告止まり（§8.3 D-1 仮値）


@dataclass
class CheckReport:
    family: str
    lint_errors: list[dict[str, Any]] = field(default_factory=list)
    smoke_failures: list[dict[str, Any]] = field(default_factory=list)
    dup_rates: dict[str, float] = field(default_factory=dict)
    dup_rate_warnings: list[str] = field(default_factory=list)
    ok: bool = True

    def to_json(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "lint_errors": self.lint_errors,
            "smoke_failures": self.smoke_failures,
            "dup_rates": self.dup_rates,
            "dup_rate_warnings": self.dup_rate_warnings,
            "ok": self.ok,
        }


def _run_check(family_name: str, families_dir: Path = _DEFAULT_FAMILIES_DIR) -> tuple[int, CheckReport]:
    bootstrap()
    report = CheckReport(family=family_name)

    spec = _load_target_family(family_name, families_dir)
    if spec is None:
        report.ok = False
        report.lint_errors.append({"rule": "R0", "message": f"family 未検出: {family_name!r}", "level_key": None})
        return 1, report

    # --- spec_lint ---
    from engine.core.curriculum import load_curriculum
    from engine.core.registry import REGISTRY

    curriculum = load_curriculum()
    frames = {
        form: REGISTRY.frame(form)
        for form in ("calculation", "knowledge", "find_value", "graph_table", "word_problem", "proof", "construction")
        if REGISTRY.has_frame(form)
    }
    lint_errors: list[LintError] = lint_family(
        spec,
        registry=REGISTRY,
        concepts=curriculum.concept_ids(),
        causes=curriculum.cause_ids(),
        frames=frames,
    )
    report.lint_errors = [
        {"rule": e.rule, "message": e.message, "level_key": e.level_key} for e in lint_errors
    ]
    if lint_errors:
        report.ok = False

    unit = _unit_from_family(family_name)

    # --- smoke: 全 level x 20 seed ---
    for level_key, level_num in _sorted_levels(spec):
        failures_for_level = 0
        for seed in range(1, 21):
            req = GenerateRequest(subject="math", unit=unit, form=spec.form, level=level_num, seed=seed)
            result = generate(req)
            if isinstance(result, Unsupported):
                failures_for_level += 1
                report.smoke_failures.append(
                    {"level": level_num, "seed": seed, "code": result.code, "detail": result.detail}
                )
        if failures_for_level:
            report.ok = False

    # --- 簡易 dup_rate（problem_ref ベース。設計上の代替: 下記コメント参照）---
    # Problem からは MR/dup_key（core.signature.dup_key）が見えない。dup_key は
    # signature + 正規化 params から算出されるが、Problem は params を運ばない
    # （テンプレートから answer/params を書けない設計＝ Q5 対策と表裏）。そのため
    # M0 のツール層では problem_ref（Problem の一意キー = provenance+seed+render_keys+fp の
    # ハッシュ）の重複率で代替する。これは MR の意味的重複（dup_key 一致）とは定義が異なり
    # 「同じ seed から同じ Problem が出るか」に近い指標だが、M0 では警告止まりの簡易検査として
    # 割り切る（本格的な dup_rate は eval/dup_rate.py が MR に直接アクセスして測る。§8.3）。
    for level_key, level_num in _sorted_levels(spec):
        refs: list[str] = []
        for seed in range(1, 101):
            req = GenerateRequest(subject="math", unit=unit, form=spec.form, level=level_num, seed=seed)
            result = generate(req)
            if isinstance(result, Problem):
                refs.append(result.problem_ref)
        if not refs:
            continue
        counts = Counter(refs)
        dup_count = sum(c - 1 for c in counts.values() if c > 1)
        dup_rate = dup_count / len(refs)
        report.dup_rates[str(level_num)] = dup_rate
        if dup_rate > _DUP_RATE_WARN_THRESHOLD:
            report.dup_rate_warnings.append(
                f"level={level_num}: dup_rate={dup_rate:.2f} > {_DUP_RATE_WARN_THRESHOLD} (problem_ref ベース簡易測定)"
            )

    exit_code = 0 if report.ok else 1
    return exit_code, report


# ---------------------------------------------------------------------------
# spec approve
# ---------------------------------------------------------------------------


def _run_approve(
    family_name: str,
    golden_dir: Path,
    diff: bool,
    families_dir: Path = _DEFAULT_FAMILIES_DIR,
) -> int:
    bootstrap()
    spec = _load_target_family(family_name, families_dir)
    if spec is None:
        print(json.dumps({"error": f"family 未検出: {family_name!r}"}, ensure_ascii=False))
        return 1

    unit = _unit_from_family(family_name)
    family_dir = golden_dir / family_name
    family_dir.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    diffs: list[dict[str, Any]] = []
    hash_material: list[str] = []

    for level_key, level_num in _sorted_levels(spec):
        for seed in (1, 2, 3):
            req = GenerateRequest(subject="math", unit=unit, form=spec.form, level=level_num, seed=seed)
            result = generate(req)
            file_name = f"{family_name}_lv{level_num}_seed{seed}.yaml"
            file_path = family_dir / file_name

            if isinstance(result, Unsupported):
                # 承認不能セルはスキップして報告に残す（握り潰さない）。
                diffs.append(
                    {
                        "level": level_num, "seed": seed, "file": file_name,
                        "status": "unsupported", "code": result.code, "detail": result.detail,
                    }
                )
                continue

            new_dump = result.model_dump(mode="json")

            if diff and file_path.exists():
                old_dump = yaml.safe_load(file_path.read_text(encoding="utf-8"))
                if old_dump != new_dump:
                    diffs.append(
                        {"level": level_num, "seed": seed, "file": file_name, "status": "changed"}
                    )
                else:
                    diffs.append(
                        {"level": level_num, "seed": seed, "file": file_name, "status": "unchanged"}
                    )

            file_path.write_text(
                yaml.safe_dump(new_dump, allow_unicode=True, sort_keys=True, width=200),
                encoding="utf-8",
            )
            written.append(str(file_path))
            hash_material.append(json.dumps(new_dump, ensure_ascii=False, sort_keys=True, default=str))

    content_hash = hashlib.sha256("".join(hash_material).encode()).hexdigest()

    approval = {
        "family": family_name,
        "approver": os.environ.get("USER", "unknown"),
        "approved_at": datetime.now().isoformat(),
        "content_sha256": content_hash,
        "files": written,
    }
    approval_path = family_dir / "approval.yaml"
    approval_path.write_text(
        yaml.safe_dump(approval, allow_unicode=True, sort_keys=True, width=200), encoding="utf-8"
    )

    report: dict[str, Any] = {
        "family": family_name,
        "golden_dir": str(family_dir),
        "written": written,
        "approval": str(approval_path),
    }
    if diff:
        report["diff"] = diffs

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# argparse エントリポイント
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec_cli", description="セル制作ツール（preview / check / approve）")
    sub = parser.add_subparsers(dest="command", required=True)

    p_preview = sub.add_parser("preview", help="全レベル x seed の生成結果を1枚の HTML に描画")
    p_preview.add_argument("family", help='family名（例: math.g2_l25.find_value）')
    p_preview.add_argument("--seeds", type=int, default=5)
    p_preview.add_argument("--out", type=Path, default=None)
    p_preview.add_argument("--families-dir", type=Path, default=_DEFAULT_FAMILIES_DIR)

    p_check = sub.add_parser("check", help="spec_lint + smoke + 簡易dup_rate")
    p_check.add_argument("family")
    p_check.add_argument("--families-dir", type=Path, default=_DEFAULT_FAMILIES_DIR)

    p_approve = sub.add_parser("approve", help="golden(seed1-3)を承認保存")
    p_approve.add_argument("family")
    p_approve.add_argument("--golden-dir", type=Path, default=_DEFAULT_GOLDEN_DIR)
    p_approve.add_argument("--diff", action="store_true")
    p_approve.add_argument("--families-dir", type=Path, default=_DEFAULT_FAMILIES_DIR)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "preview":
        out = args.out if args.out is not None else Path(f"preview_{args.family}.html")
        return _run_preview(args.family, args.seeds, out, families_dir=args.families_dir)

    if args.command == "check":
        exit_code, report = _run_check(args.family, families_dir=args.families_dir)
        print(json.dumps(report.to_json(), ensure_ascii=False, indent=2))
        return exit_code

    if args.command == "approve":
        return _run_approve(args.family, args.golden_dir, args.diff, families_dir=args.families_dir)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
