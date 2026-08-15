#!/usr/bin/env python3
"""性能評価 LLM評価スクリプト

reports/perf_eval/groups.json を読み込み、Claude Code CLI で A〜D の4軸評価を行う。
評価結果を reports/perf_eval/eval_result.json に保存する。

評価軸:
  A: そのレッスンの問題として適しているか（単元の概念・計算を使っているか）
  B: その問題形式として適しているか（calculation/word_problem/visual/proof/knowledge）
  C: 同一レッスン・同一形式で Lv1 < Lv2 < ... と難易度が上がっているか
  D: Lv1 が「基礎・入門」として適切か

  + E: 2問が重複していないか（同一 lesson × form × level で 2問を比較）

使い方:
    python scripts/evaluate_perf_problems_llm.py [--limit N] [--resume]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# .env を読み込む
_env_path = ROOT / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip("\"'"))

GROUPS_PATH = ROOT / "reports" / "perf_eval" / "groups.json"
OUTPUT_PATH = ROOT / "reports" / "perf_eval" / "eval_result.json"
REPORT_PATH = ROOT / "reports" / "perf_eval" / "eval_report_llm.md"

FORM_JA = {
    "calculation": "計算問題",
    "word_problem": "文章題",
    "visual": "図・グラフを使う問題",
    "proof": "証明問題",
    "knowledge": "知識問題（概念・用語の確認）",
}


def build_prompt(group: dict) -> str:
    """1グループ分の評価プロンプトを生成する。"""
    lid = group["lesson_id"]
    form = group["form"]
    title = group["title"]
    grade = group["grade"]
    large_unit = group["large_unit"]
    levels = group["levels"]
    form_ja = FORM_JA.get(form, form)

    lines = [
        "あなたは中学数学の専門家です。以下の問題セットを評価してください。",
        "",
        f"## レッスン情報",
        f"- レッスンID: {lid}",
        f"- タイトル: {title}",
        f"- 学年: 中学{grade}年",
        f"- 単元: {large_unit}",
        f"- 問題形式: {form_ja}（{form}）",
        "",
        "## 生成された問題",
        "",
    ]

    for lv_data in levels:
        level = lv_data["level"]
        desc = lv_data["description"]
        problems = lv_data["problems"]
        errors = lv_data.get("generation_errors", [])

        lines.append(f"### Lv{level}: {desc}")
        if errors:
            lines.append(f"  ⚠️ 生成エラー: {errors[0][:100]}")
        for i, prob in enumerate(problems, 1):
            lines.append(f"  **問題{i}** (blueprint: {prob.get('blueprint_id', '')})")
            lines.append(f"  tags: {', '.join(prob.get('selected_tags', []))}")
            for sq in prob.get("sub_questions", []):
                lines.append(f"  [小問{sq.get('label', '')}]")
                hint = sq.get("prompt_hint", "").replace("\n", " ")
                lines.append(f"    問い: {hint[:150]}")
                ans = sq.get("answer", {})
                lines.append(f"    答え: {ans.get('text_form', '')} (型: {ans.get('type', '')})")
        lines.append("")

    lines += [
        "## 評価指示",
        "",
        "以下の評価を JSON 形式で返してください。",
        "",
        "```json",
        "{",
        '  "a_ok": true または false,',
        '  "a_reason": "評価理由（1〜2文）",',
        '  "b_ok": true または false,',
        '  "b_reason": "評価理由（1〜2文）",',
        '  "c_ok": true または false,',
        '  "c_reason": "評価理由（1〜2文）",',
        '  "d_ok": true または false,',
        '  "d_reason": "評価理由（1〜2文）",',
        '  "e_ok": true または false,',
        '  "e_reason": "評価理由（1〜2文）"',
        "}",
        "```",
        "",
        "各評価基準:",
        f"A（単元適合）: {large_unit} の問題として適しているか。",
        "  その単元固有の概念・計算（例: 三平方の定理なら√や直角三角形）が使われているか。",
        "  基礎的な四則演算のみで解ける問題は NG。",
        "",
        f"B（形式適合）: 問題形式「{form_ja}」として適しているか。",
        "  - calculation: 数式・計算式が明示されているか",
        "  - word_problem: 具体的な文章・状況が含まれているか（数式だけでなく）",
        "  - visual: 図・グラフ・座標・図形を扱う内容か",
        "  - proof: 証明の形式（条件→結論）になっているか",
        "  - knowledge: 概念・用語の確認問題か（穴埋め・選択的な問い）",
        "",
        "C（難易度順序）: Lv1 < Lv2 < Lv3 ... の順に難しくなっているか。",
        "  問いの複雑さ・数値の大きさ・ステップ数などで判断する。",
        "  レベル数が 1 のみの場合は true とする。",
        "  エラーで生成されなかったレベルは比較から除外する。",
        "",
        "D（Lv1基礎適合）: Lv1 が「基礎・入門」として適切か。",
        "  - 概念を初めて学ぶ生徒が取り組める難易度か",
        "  - 単純すぎる（自明すぎる）場合も NG",
        "  - Lv1 が生成エラーの場合は false とする",
        "",
        "E（重複なし）: 同じ level の問題1・問題2が異なる問題になっているか。",
        "  答えが完全に同じ場合は NG。計算式や数値が異なれば OK。",
        "  問題が 1 問しか生成されていないレベルは比較不要（true）。",
    ]

    return "\n".join(lines)


def call_claude_code_for_eval(prompt: str, max_retries: int = 3) -> dict:
    """Claude Code CLI を subprocess で呼んで評価結果を返す。"""
    import subprocess

    text = ""
    for attempt in range(max_retries):
        try:
            result = subprocess.run(
                [
                    "claude",
                    "-p", prompt,
                    "--model", "haiku",
                    "--output-format", "json",
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                err = result.stderr.strip()[:200]
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                return {"error": err}

            # --output-format json の出力: {"type":"result","result":"...テキスト..."}
            outer = json.loads(result.stdout)
            text = outer.get("result", result.stdout).strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            return {"error": f"JSON parse error: {e}", "raw": text[:200]}
        except subprocess.TimeoutExpired:
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return {"error": "timeout"}
        except Exception as e:
            return {"error": str(e)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="評価グループ数の上限（テスト用）")
    parser.add_argument("--resume", action="store_true", help="既存の評価結果を読み込んで途中から再開")
    args = parser.parse_args()

    groups = json.loads(GROUPS_PATH.read_text(encoding="utf-8"))
    print(f"評価対象グループ数: {len(groups)}")

    # resume 処理
    existing: dict[str, dict] = {}
    if args.resume and OUTPUT_PATH.exists():
        prev = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        for r in prev.get("results", []):
            if "error" not in r:  # エラーは再評価する
                key = f"{r['lesson_id']}_{r['form']}"
                existing[key] = r
        print(f"既存評価: {len(existing)} グループ（スキップ）")

    if args.limit:
        groups = groups[: args.limit]

    results = []
    ok_count = err_count = skip_count = 0
    t0 = time.time()

    for i, group in enumerate(groups):
        key = f"{group['lesson_id']}_{group['form']}"
        if key in existing:
            results.append(existing[key])
            skip_count += 1
            continue

        prompt = build_prompt(group)
        eval_result = call_claude_code_for_eval(prompt)

        record = {
            "lesson_id": group["lesson_id"],
            "form": group["form"],
            "title": group["title"],
            "grade": group["grade"],
            "large_unit": group["large_unit"],
            **eval_result,
        }
        results.append(record)

        if "error" in eval_result:
            err_count += 1
        else:
            ok_count += 1

        elapsed = time.time() - t0
        rate = (i + 1 - skip_count) / elapsed if elapsed > 0 else 1
        remaining = len(groups) - i - 1
        eta = remaining / rate if rate > 0 else 0
        print(
            f"\r  [{i+1}/{len(groups)}] ✅{ok_count} ❌{err_count} ⏭{skip_count}"
            f"  {elapsed:.0f}s  ETA {eta:.0f}s",
            end="",
            flush=True,
        )

        # Claude Code CLI のセッション間隔（短い待機でも問題なし）
        time.sleep(0.5)

        # 10グループごとに中間保存
        if (i + 1) % 10 == 0:
            _save(results, OUTPUT_PATH)

    print()
    _save(results, OUTPUT_PATH)
    _write_report(results, REPORT_PATH)
    print(f"\n完了: ✅{ok_count} ❌{err_count} ⏭{skip_count} → {OUTPUT_PATH}")


def _save(results: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # 集計
    valid = [r for r in results if "error" not in r]
    total = len(valid)
    if total == 0:
        return
    summary = {
        "total_groups": total,
        "A": {
            "pass": sum(1 for r in valid if r.get("a_ok")),
            "rate": round(sum(1 for r in valid if r.get("a_ok")) / total * 100, 1),
        },
        "B": {
            "pass": sum(1 for r in valid if r.get("b_ok")),
            "rate": round(sum(1 for r in valid if r.get("b_ok")) / total * 100, 1),
        },
        "C": {
            "pass": sum(1 for r in valid if r.get("c_ok")),
            "rate": round(sum(1 for r in valid if r.get("c_ok")) / total * 100, 1),
        },
        "D": {
            "pass": sum(1 for r in valid if r.get("d_ok")),
            "rate": round(sum(1 for r in valid if r.get("d_ok")) / total * 100, 1),
        },
        "E": {
            "pass": sum(1 for r in valid if r.get("e_ok")),
            "rate": round(sum(1 for r in valid if r.get("e_ok")) / total * 100, 1),
        },
    }
    path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_report(results: list[dict], path: Path) -> None:
    valid = [r for r in results if "error" not in r]
    total = len(valid)
    if total == 0:
        return

    def pct(key: str) -> str:
        n = sum(1 for r in valid if r.get(key))
        return f"{n}/{total} ({n/total*100:.1f}%)"

    lines = [
        "# 性能評価レポート（LLM評価）",
        "",
        "## サマリー",
        "",
        "| 評価軸 | 内容 | 合格 |",
        "|--------|------|------|",
        f"| A | レッスン単元適合 | {pct('a_ok')} |",
        f"| B | 問題形式適合 | {pct('b_ok')} |",
        f"| C | 難易度順序 (Lv1<Lv2<...) | {pct('c_ok')} |",
        f"| D | Lv1 基礎・入門適合 | {pct('d_ok')} |",
        f"| E | 重複なし（2問が異なる） | {pct('e_ok')} |",
        "",
    ]

    # B フォーム別内訳
    from collections import defaultdict
    by_form: dict = defaultdict(list)
    for r in valid:
        by_form[r["form"]].append(r)

    lines += [
        "## B 問題形式別内訳",
        "",
        "| 形式 | 合格 | 合計 | 合格率 |",
        "|------|------|------|--------|",
    ]
    for form in ["calculation", "word_problem", "visual", "proof", "knowledge"]:
        lst = by_form.get(form, [])
        n = len(lst)
        p = sum(1 for r in lst if r.get("b_ok"))
        lines.append(f"| {form} | {p} | {n} | {p/n*100:.1f}% |" if n else f"| {form} | - | 0 | - |")

    # NG 詳細
    for key, label in [("a_ok", "A"), ("b_ok", "B"), ("c_ok", "C"), ("d_ok", "D"), ("e_ok", "E")]:
        ng = [r for r in valid if not r.get(key)]
        if not ng:
            continue
        lines += ["", f"## {label} NG 詳細（最大20件）", ""]
        for r in ng[:20]:
            reason_key = key.replace("_ok", "_reason")
            lines.append(
                f"- `{r['lesson_id']}` {r['form']} / {r.get('large_unit', '')}:"
                f" {r.get(reason_key, '')}"
            )

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"レポート出力: {path}")


if __name__ == "__main__":
    main()
