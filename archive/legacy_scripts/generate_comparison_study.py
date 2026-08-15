#!/usr/bin/env python3
"""
比較調査レポート生成スクリプト
reports/inspect_results.json → reports/comparison_study.md
"""
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent

def load():
    d = json.load(open(ROOT / "reports/inspect_results.json"))
    return d["results"]

def build_groups(results):
    g = defaultdict(dict)
    for r in results:
        key = (r["lesson_id"], r["form"])
        g[key][r["level"]] = r
    return g

def get_field(levels, field, default="?"):
    for lv in ["min", "mid", "max"]:
        if lv in levels:
            return levels[lv].get(field, default)
    return default

def get_blueprint(levels):
    for lv in ["min", "mid", "max"]:
        if lv in levels:
            return levels[lv]["blueprint"]
    return "?"

def get_first_q(levels):
    for lv in ["min", "mid", "max"]:
        if lv in levels:
            sq = levels[lv]["sub_questions"]
            return sq[0]["prompt_hint"] if sq else "N/A"
    return "N/A"

def get_answers(levels):
    ans = []
    for lv in ["min", "mid", "max"]:
        if lv in levels:
            sq = levels[lv]["sub_questions"]
            ans.append(sq[0]["answer"]["text_form"] if sq else "N/A")
    return ans

def get_first_answer(levels):
    ans = get_answers(levels)
    return ans[0] if ans else "N/A"

def always_same(levels):
    ans = get_answers(levels)
    return len(ans) >= 2 and len(set(ans)) == 1

def get_diff_range(levels):
    lo = levels["min"]["diff"] if "min" in levels else "?"
    hi = levels["max"]["diff"] if "max" in levels else "?"
    return lo, hi

# ===== 評価ルール =====

# 単元と無関係な内容
UNRELATED_CONTENT = {
    ("g1_l54", "knowledge"): "度数分布表・ヒストグラム単元なのに整数の足し算",
    ("g1_l60", "knowledge"): "誤差・近似値単元なのに整数の足し算",
    ("g3_l24", "knowledge"): "2次方程式の意味単元なのに整数の足し算",
    ("g1_l37", "knowledge"): "直線・線分・角の単元なのに面積計算問題",
    ("g1_l37", "visual"):    "直線・線分・角の単元なのに面積計算問題",
    ("g1_l38", "knowledge"): "平行移動単元なのに面積計算問題",
    ("g1_l38", "visual"):    "平行移動単元なのに面積計算問題",
    ("g1_l39", "knowledge"): "回転移動単元なのに面積計算問題",
    ("g1_l39", "visual"):    "回転移動単元なのに面積計算問題",
    ("g1_l40", "knowledge"): "対称移動単元なのに面積計算問題",
    ("g1_l40", "visual"):    "対称移動単元なのに面積計算問題",
    ("g2_l56", "calculation"): "箱ひげ図単元なのに確率問題",
    ("g2_l56", "knowledge"):   "箱ひげ図単元なのに確率問題",
    ("g2_l56", "visual"):      "箱ひげ図単元なのに確率問題",
    ("g1_l58", "calculation"):  "データの比較・探究単元なのに確率問題",
    ("g1_l58", "knowledge"):    "データの比較・探究単元なのに確率問題",
    ("g1_l58", "visual"):       "データの比較・探究単元なのに確率問題",
    ("g1_l58", "word_problem"): "データの比較・探究単元なのに確率問題",
    ("g3_l45", "calculation"):  "相似な面積比単元なのに証明問題（全form）",
    ("g3_l45", "knowledge"):    "相似な面積比単元なのに証明問題",
    ("g3_l45", "visual"):       "相似な面積比単元なのに証明問題",
    ("g3_l45", "word_problem"): "相似な面積比単元なのに証明問題",
    ("g1_l28", "calculation"):  "変数・関数・変域単元なのに交点座標問題（変域未対応）",
    ("g1_l28", "knowledge"):    "変数・関数・変域単元なのに交点座標問題（変域未対応）",
    ("g1_l30", "knowledge"):    "座標の概念（点の取り方）単元なのに交点座標問題",
    ("g1_l30", "visual"):       "座標の概念（点の取り方）単元なのに交点座標問題",
}

# 単元より難易度が上（⚠️）
CONTENT_TOO_HARD = {}
for _lid in ["g1_l29", "g1_l31", "g1_l32", "g1_l33", "g1_l34", "g1_l35"]:
    for _form in ["calculation", "knowledge", "visual", "word_problem"]:
        CONTENT_TOO_HARD[(_lid, _form)] = "1年生比例・反比例単元だが2関数交点座標問題（2年以降の内容）"


def evaluate(lid, form, levels):
    """
    Returns dict with keys: structural, form_valid, difficulty, math_correct, issues
    Each key: '✅' | '⚠️' | '❌'
    issues: list of str
    """
    bp = get_blueprint(levels)
    q = get_first_q(levels)
    ans = get_answers(levels)
    first_ans = get_first_answer(levels)
    same = always_same(levels)
    key = (lid, form)
    issues = []

    # ---- 構造の妥当性 ----
    if key in UNRELATED_CONTENT:
        structural = "❌"
        issues.append(f"構造❌: {UNRELATED_CONTENT[key]}")
    elif key in CONTENT_TOO_HARD:
        structural = "⚠️"
        issues.append(f"構造⚠️: {CONTENT_TOO_HARD[key]}")
    elif form in ("knowledge", "visual") and bp not in ("ConstructionStructure",):
        structural = "⚠️"
        issues.append(f"構造⚠️: knowledge/visual formは専用Blueprintなし。{bp}で代替（既知問題）")
    else:
        structural = "✅"

    # ---- 形式の妥当性 ----
    if form == "proof":
        if bp == "AngleCalculationStructure":
            form_valid = "❌"
            issues.append(f"形式❌: proof formだが角度計算問題が出る（証明でない）")
        elif bp == "PythagoreanStructure" and "三平方" in q:
            form_valid = "⚠️"
            issues.append(f"形式⚠️: proof formだが三平方の計算問題が出る")
        elif "証明しなさい" in q or bp == "ProofStructure":
            form_valid = "✅"
        else:
            form_valid = "⚠️"
            issues.append(f"形式⚠️: proof formだが証明問題でない可能性")
    elif form in ("calculation", "visual", "word_problem") and "証明しなさい" in q:
        form_valid = "❌"
        issues.append(f"形式❌: {form} formだが証明問題が出る")
    elif form in ("knowledge", "visual"):
        form_valid = "⚠️"
    else:
        form_valid = "✅"

    # ---- 難易度変化 ----
    if same:
        difficulty = "❌"
        issues.append(f"難易度❌: min/mid/maxの答えが全て「{first_ans[:30]}」で変化なし")
    else:
        lo, hi = get_diff_range(levels)
        difficulty = "✅"

    # ---- 数学的正確性 ----
    if bp == "ConstructionStructure" and ans and "True" in ans[0]:
        math_correct = "❌"
        issues.append("数学❌: 答えが$\\text{True}$（数学的な値でなくboolフラグ）")
    elif lid == "g2_l35" and ans and "120" in ans[0]:
        math_correct = "❌"
        issues.append("数学❌: 多角形の外角の和の答えが120（正解は360）")
    elif bp == "BasicGeometryMeasurementStructure" and same and first_ans == "0":
        math_correct = "❌"
        issues.append("数学❌: 図形の面積が常に0（計算エラー）")
    elif bp == "MovingPointStructure" and same and first_ans == "0":
        math_correct = "❌"
        issues.append("数学❌: 動点問題の答えが常に0（計算エラー）")
    else:
        math_correct = "✅"

    return {
        "structural": structural,
        "form_valid": form_valid,
        "difficulty": difficulty,
        "math_correct": math_correct,
        "issues": issues,
        "blueprint": bp,
        "first_q": q[:60],
        "first_ans": first_ans[:40],
    }


def severity_order(e):
    """❌が多いほど先に出す"""
    counts = {"❌": 2, "⚠️": 1, "✅": 0}
    score = sum(counts.get(e[k], 0) for k in ["structural", "form_valid", "difficulty", "math_correct"])
    return -score


def format_issue_badge(e):
    badges = []
    for key, label in [("structural", "構造"), ("form_valid", "形式"), ("difficulty", "難易度"), ("math_correct", "数学")]:
        badges.append(f"{e[key]}{label}")
    return " / ".join(badges)


def generate_report(groups):
    results_list = sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1]))

    eval_map = {}
    for (lid, form), levels in results_list:
        eval_map[(lid, form)] = evaluate(lid, form, levels)

    # ---- 集計 ----
    total = len(eval_map)
    crit = sum(1 for e in eval_map.values() if any(e[k] == "❌" for k in ["structural", "form_valid", "difficulty", "math_correct"]))
    warn = sum(1 for e in eval_map.values() if any(e[k] == "⚠️" for k in ["structural", "form_valid", "difficulty", "math_correct"]) and
               not any(e[k] == "❌" for k in ["structural", "form_valid", "difficulty", "math_correct"]))
    ok = total - crit - warn

    lines = []
    lines.append("# 比較調査レポート — mongene-v2 生成問題 vs 実教材")
    lines.append("")
    lines.append(f"> **調査日**: 2026-06-22  ")
    lines.append(f"> **対象**: 全 {total} ペア（177単元 × supported_forms）× 難易度3段階 = 1,134件  ")
    lines.append(f"> **手法**: `/problems/inspect` エンドポイントの構造情報を実教材と比較（LLM不使用）")
    lines.append("")

    # ---- エグゼクティブサマリー ----
    lines.append("## エグゼクティブサマリー")
    lines.append("")
    lines.append("| 判定 | ペア数 | 割合 |")
    lines.append("|:---|---:|---:|")
    lines.append(f"| ✅ 問題なし | {ok} | {ok/total*100:.0f}% |")
    lines.append(f"| ⚠️ 軽微な問題あり | {warn} | {warn/total*100:.0f}% |")
    lines.append(f"| ❌ 重大な問題あり | {crit} | {crit/total*100:.0f}% |")
    lines.append(f"| **合計** | **{total}** | **100%** |")
    lines.append("")

    lines.append("### 主要な問題カテゴリー")
    lines.append("")

    # カテゴリー別集計
    no_diff = sum(1 for e in eval_map.values() if e["difficulty"] == "❌")
    bad_struct = sum(1 for e in eval_map.values() if e["structural"] == "❌")
    bad_form = sum(1 for e in eval_map.values() if e["form_valid"] == "❌")
    bad_math = sum(1 for e in eval_map.values() if e["math_correct"] == "❌")
    warn_struct = sum(1 for e in eval_map.values() if e["structural"] == "⚠️")

    lines.append(f"1. **難易度変化なし** — {no_diff} ペア: min/mid/maxで答えが同一（Blueprint固定値バグ）")
    lines.append(f"2. **単元と無関係な内容** — {bad_struct} ペア: Blueprint が単元の数学内容と一致しない")
    lines.append(f"3. **form と問題の不一致** — {bad_form} ペア: calculation/visual なのに証明問題、またはその逆")
    lines.append(f"4. **数学的正確性** — {bad_math} ペア: 答えが常に0・True・誤値")
    lines.append(f"5. **knowledge/visual 代替実装** — {warn_struct} ペア: 専用Blueprint未実装のため他Blueprintで代替（既知）")
    lines.append("")

    # ---- 重大な問題一覧 ----
    lines.append("## ❌ 重大な問題一覧")
    lines.append("")

    # サブカテゴリー別に整理
    lines.append("### I. 難易度変化なし（min/mid/max の答えが同一）")
    lines.append("")
    lines.append("Blueprint が固定値を返すバグ。難易度パラメータが実際の問題生成に反映されていない。")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | Blueprint | 固定答え |")
    lines.append("|:---|:---|:---|:---|:---|")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: kv[0]):
        if e["difficulty"] == "❌":
            levels = groups[(lid, form)]
            title = get_field(levels, "title")
            ans = e["first_ans"][:35]
            lines.append(f"| {lid} | {title[:35]} | {form} | {e['blueprint'][:35]} | `{ans}` |")
    lines.append("")

    lines.append("### II. 単元と無関係な内容")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | Blueprint | 問題文 | 問題点 |")
    lines.append("|:---|:---|:---|:---|:---|:---|")
    for (lid, form), reason in sorted(UNRELATED_CONTENT.items()):
        if (lid, form) in eval_map:
            e = eval_map[(lid, form)]
            levels = groups[(lid, form)]
            title = get_field(levels, "title")[:30]
            q = e["first_q"][:40].replace("\n", " ")
            lines.append(f"| {lid} | {title} | {form} | {e['blueprint'][:30]} | {q} | {reason} |")
    lines.append("")

    lines.append("### III. form と問題内容の不一致")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | Blueprint | 問題文 | 問題点 |")
    lines.append("|:---|:---|:---|:---|:---|:---|")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: kv[0]):
        if e["form_valid"] == "❌":
            levels = groups[(lid, form)]
            title = get_field(levels, "title")[:30]
            q = e["first_q"][:40].replace("\n", " ")
            issue = [i for i in e["issues"] if "形式❌" in i]
            reason = issue[0].replace("形式❌: ", "") if issue else ""
            lines.append(f"| {lid} | {title} | {form} | {e['blueprint'][:30]} | {q} | {reason} |")
    lines.append("")

    lines.append("### IV. 数学的正確性の問題")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | Blueprint | 答え | 問題点 |")
    lines.append("|:---|:---|:---|:---|:---|:---|")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: kv[0]):
        if e["math_correct"] == "❌":
            levels = groups[(lid, form)]
            title = get_field(levels, "title")[:30]
            ans = e["first_ans"][:30]
            issue = [i for i in e["issues"] if "数学❌" in i]
            reason = issue[0].replace("数学❌: ", "") if issue else ""
            lines.append(f"| {lid} | {title} | {form} | {e['blueprint'][:30]} | `{ans}` | {reason} |")
    lines.append("")

    # ---- 軽微な問題一覧 ----
    lines.append("## ⚠️ 軽微な問題一覧")
    lines.append("")
    lines.append("### V. 単元より難易度が上の問題（1年生比例→交点座標）")
    lines.append("")
    lines.append("1年生時点では「2つの関数の交点座標」を学習しない。")
    lines.append("比例・反比例単元は `FunctionGeometryFusionStructure` が選ばれるが、")
    lines.append("同Blueprintが生成する問題（交点座標）は2年生以降の内容。")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | 問題文 |")
    lines.append("|:---|:---|:---|:---|")
    for (lid, form), reason in sorted(CONTENT_TOO_HARD.items()):
        if (lid, form) in eval_map:
            e = eval_map[(lid, form)]
            levels = groups[(lid, form)]
            title = get_field(levels, "title")[:35]
            q = e["first_q"][:40].replace("\n", " ")
            lines.append(f"| {lid} | {title} | {form} | {q} |")
    lines.append("")

    lines.append("### VI. knowledge/visual form の代替実装（既知問題）")
    lines.append("")
    lines.append("knowledge/visual form 専用の Blueprint が未実装のため、")
    lines.append("同単元の calculation form 用 Blueprint で代替生成される。")
    lines.append("例: `g1_l11（素数・素因数分解）` knowledge → BasicCalculationStructure で整数の足し算。")
    lines.append("")
    lines.append("⚠️ 形式妥当性はすべて ⚠️ として処理（構造の妥当性は単元内容に依存）。")
    lines.append("")

    # ---- 全体サマリーテーブル ----
    lines.append("## 全ペア評価サマリー")
    lines.append("")
    lines.append("| lesson_id | タイトル | form | 構造 | 形式 | 難易度 | 数学 | Blueprint |")
    lines.append("|:---|:---|:---|:---:|:---:|:---:|:---:|:---|")

    # Grade 1
    lines.append("| **Grade 1** | | | | | | | |")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: (kv[0][0], int(kv[0][0][1:kv[0][0].index('_l')].split('_l')[0][1:] + kv[0][0].split('_l')[1]), kv[0][1])):
        grade = groups[(lid, form)]["min"]["grade"] if "min" in groups[(lid, form)] else get_field(groups[(lid, form)], "grade")
        if grade != 1:
            continue
        levels = groups[(lid, form)]
        title = get_field(levels, "title")[:35]
        bp = e["blueprint"][:35]
        lines.append(f"| {lid} | {title} | {form} | {e['structural']} | {e['form_valid']} | {e['difficulty']} | {e['math_correct']} | {bp} |")

    lines.append("| **Grade 2** | | | | | | | |")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: (kv[0][0], int(kv[0][0].split('_l')[1]), kv[0][1])):
        grade = get_field(groups[(lid, form)], "grade")
        if grade != 2:
            continue
        levels = groups[(lid, form)]
        title = get_field(levels, "title")[:35]
        bp = e["blueprint"][:35]
        lines.append(f"| {lid} | {title} | {form} | {e['structural']} | {e['form_valid']} | {e['difficulty']} | {e['math_correct']} | {bp} |")

    lines.append("| **Grade 3** | | | | | | | |")
    for (lid, form), e in sorted(eval_map.items(), key=lambda kv: (kv[0][0], int(kv[0][0].split('_l')[1]), kv[0][1])):
        grade = get_field(groups[(lid, form)], "grade")
        if grade != 3:
            continue
        levels = groups[(lid, form)]
        title = get_field(levels, "title")[:35]
        bp = e["blueprint"][:35]
        lines.append(f"| {lid} | {title} | {form} | {e['structural']} | {e['form_valid']} | {e['difficulty']} | {e['math_correct']} | {bp} |")

    # ---- 修正提案 ----
    lines.append("")
    lines.append("## 修正提案")
    lines.append("")
    lines.append("### 優先度 High（❌が複数）")
    lines.append("")
    lines.append("| 問題ID | 影響ペア数 | 修正内容 |")
    lines.append("|:---|---:|:---|")
    lines.append("| P-1 | 132 | 難易度変化なしのBlueprintを修正（固定値を返さないようにする） |")
    lines.append("| P-2 | 26 | 単元と無関係なBlueprintの割当を修正（g1_l54/l58/l60/l37-40/g2_l56/g3_l24/g3_l45） |")
    lines.append("| P-3 | 36 | proof/non-proof formの問題内容不一致を修正 |")
    lines.append("| P-4 | 34 | 数学的正確性の問題（0・True・外角360→120）を修正 |")
    lines.append("")
    lines.append("### 優先度 Medium（⚠️）")
    lines.append("")
    lines.append("| 問題ID | 影響ペア数 | 修正内容 |")
    lines.append("|:---|---:|:---|")
    lines.append("| P-5 | 17 | 1年生比例・反比例単元のBlueprintを交点座標以外の問題に変更 |")
    lines.append("| P-6 | 85 | knowledge/visual form 専用Blueprintの実装（長期課題） |")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    results = load()
    groups = build_groups(results)
    report = generate_report(groups)
    out = ROOT / "reports/comparison_study.md"
    out.write_text(report, encoding="utf-8")
    print(f"✅ レポート生成完了: {out}")
    print(f"   行数: {len(report.splitlines())}")
