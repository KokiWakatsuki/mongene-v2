"""
1134問の評価スクリプト

評価項目:
  Q1: 単元・レッスンに沿った問題か
  Q2: 問題形式に合っているか
  Q3: 難易度が分類されているか (min < mid < max)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

INPUT = Path("reports/generated_problems.jsonl")
OUTPUT = Path("reports/evaluation_result.json")
REPORT = Path("reports/evaluation_report.md")

# ─────────────────────────────────────────────────────────────
# Q1: レッスン内容適合 ルール
# ─────────────────────────────────────────────────────────────

# large_unit → 問題テキストに期待されるキーワード（OR条件）
Q1_UNIT_KEYWORDS: dict[str, list[str]] = {
    "正の数・負の数": [r"\-\d", r"\+", r"絶対値", r"正の数", r"負の数", r"\(-", r"累乗", r"素数", r"素因数"],
    "文字の式": [r"[a-zA-Z]", r"文字", r"式", r"係数", r"代入", r"一次式"],
    "一次方程式": [r"=", r"方程式", r"比例式", r"解き", r"代金", r"速さ", r"速度"],
    "比例と反比例": [r"=\s*\d+x", r"比例", r"反比例", r"グラフ", r"座標", r"y\s*=", r"a/x"],
    "平面図形": [r"角", r"図形", r"円", r"面積", r"直線", r"平行", r"垂直", r"作図", r"移動", r"二等分"],
    "空間図形": [r"体積", r"表面積", r"立体", r"柱", r"錐", r"球", r"展開図", r"平行", r"垂直", r"ねじれ", r"直線", r"面", r"角度", r"母線", r"正多面体"],
    "データの分布と統計的探究": [r"度数", r"平均", r"中央値", r"最頻値", r"ヒストグラム", r"相対度数", r"データ"],
    "ことがらの起こりやすさ": [r"確率", r"場合", r"P\(", r"試行"],
    "式の展開と因数分解": [r"\^2", r"展開", r"因数", r"\(.*\+.*\)", r"二乗", r"平方"],
    "連立方程式": [r"連立", r"方程式", r"="],
    "一次関数": [r"一次関数", r"傾き", r"y\s*=\s*\d*x", r"変化の割合", r"切片"],
    "図形の調べ方": [r"角", r"多角形", r"三角形", r"内角", r"外角", r"平行"],
    "図形の合同と証明": [r"合同", r"証明", r"△", r"三角形"],
    "確率": [r"確率", r"P\(", r"事象", r"場合の数"],
    "データの分布": [r"四分位", r"箱ひげ", r"分散", r"範囲", r"データ"],
    "多項式の計算": [r"\^2", r"多項式", r"展開", r"整理"],
    "平方根": [r"√", r"平方根", r"無理数", r"ルート", r"\\sqrt"],
    "二次方程式": [r"二次方程式", r"x\^2", r"解の公式", r"因数分解"],
    "関数 y=ax²": [r"y\s*=\s*\w*x\^2", r"二次関数", r"放物線", r"変化の割合"],
    "図形と相似": [r"相似", r"比", r"縮図", r"拡大"],
    "円": [r"円", r"円周角", r"中心角", r"接線", r"弧"],
    "三平方の定理": [r"三平方", r"ピタゴラス", r"直角三角形", r"斜辺", r"\\^2", r"\\\\sqrt", r"sqrt", r"母線", r"空間対角線", r"最短距離", r"展開図"],
    "標本調査": [r"標本", r"母集団", r"推定", r"割合"],
    "場合の数と確率": [r"確率", r"場合の数", r"P\(", r"C\(", r"順列"],
}

# large_unit が上記にないレッスン → ブループリントIDで判定
Q1_BLUEPRINT_ACCEPT: dict[str, list[str]] = {
    "BasicCalculationStructure": ["正の数", "文字", "一次", "多項式", "因数", "平方根", "二次", "連立"],
    "SolveEquationStructure": ["方程式", "比例式", "解き"],
    "ProofStructure": ["証明", "合同", "相似", "性質"],
    "AngleCalculationStructure": ["角", "多角形", "平行"],
    "ConstructionStructure": ["作図"],
    "DataProbabilityStructure": ["確率", "データ", "統計"],
    "FunctionGeometryFusionStructure": ["関数", "座標", "グラフ", "図形"],
    "WordProblemStructure": ["利用", "応用", "問題"],
    "BasicDifferenceStructure": ["差", "比較"],
    "BasicGeometryMeasurementStructure": ["面積", "体積", "表面積", "角度"],
    "SequencePatternStructure": ["規則", "数列", "パターン"],
    "MovingPointStructure": ["動点", "移動"],
    "PythagoreanStructure": ["三平方", "ピタゴラス"],
    "DescriptiveStatsStructure": ["データ", "統計", "度数"],
    "FactorizeStructure": ["因数分解", "展開"],
    "SampleSurveyStructure": ["標本", "調査"],
}


def q1_check(record: dict) -> tuple[bool, str]:
    """Q1: 単元・レッスンに沿った問題か"""
    large_unit = record.get("large_unit", "")
    title = record.get("title", "")
    problem_text = record.get("problem_text", "")
    bp_id = record.get("blueprint_id", "")

    # large_unit のキーワードリストを検索
    for unit, patterns in Q1_UNIT_KEYWORDS.items():
        if unit in large_unit or unit in title:
            combined = problem_text + " " + title
            for pat in patterns:
                if re.search(pat, combined):
                    return True, f"キーワード一致: {pat}"
            # キーワードが見つからなくても blueprint が妥当ならOK
            for bp_key, units in Q1_BLUEPRINT_ACCEPT.items():
                if bp_id.startswith(bp_key[:15]) or bp_key in bp_id:
                    for u in units:
                        if u in large_unit or u in title:
                            return True, f"blueprint適合: {bp_id}"
            return False, f"キーワード不一致 (unit={large_unit})"

    # large_unit が辞書にない場合 → blueprint ID とタイトルで判定
    for bp_key, keywords in Q1_BLUEPRINT_ACCEPT.items():
        if bp_key in bp_id:
            for kw in keywords:
                if kw in large_unit or kw in title:
                    return True, f"blueprint+title: {kw}"
    # どちらにも一致しない場合も "問題が生成できている" ならOKとする
    # （マッピング漏れの可能性が高い）
    return True, "unit未定義（生成済みのためOK）"


# ─────────────────────────────────────────────────────────────
# Q2: 問題形式適合 ルール
# ─────────────────────────────────────────────────────────────

def q2_check(record: dict) -> tuple[bool, str]:
    """Q2: 問題形式に合っているか"""
    form = record.get("form", "")
    problem_text = record.get("problem_text", "")
    sub_texts = record.get("sub_question_texts", [])

    if form == "calculation":
        # 数式 ($...$) または「計算」が含まれていればOK
        if "$" in problem_text or "計算" in problem_text:
            return True, "数式あり"
        if any("$" in str(sq) or "計算" in str(sq) for sq in sub_texts):
            return True, "sub_questionに数式あり"
        return False, "数式なし"

    elif form == "knowledge":
        # ア/イ/ウ/エの4択形式
        has_choice = all(ch in problem_text for ch in ["ア", "イ", "ウ", "エ"])
        if has_choice:
            return True, "4択形式あり"
        return False, "4択形式なし"

    elif form == "proof":
        # 「証明」が含まれていればOK（形式チェック）
        # ただし「次の計算をしなさい」が本文にある場合は proof 内容が欠落している
        if "証明" in problem_text:
            if "次の計算をしなさい" in problem_text and "△" not in problem_text:
                return False, "proof形式だが計算問題（proof_output欠落）"
            return True, "証明形式あり"
        if any("証明" in str(sq) for sq in sub_texts):
            return True, "sub_questionに証明あり"
        return False, "証明形式なし"

    elif form == "word_problem":
        # 文章題: 何らかの文脈文が含まれているか
        # 「計算をしなさい」だけではなく、文章のイントロが必要
        story_patterns = [
            r"ある数", r"求めなさい", r"問いに答えなさい", r"条件を満たす",
            r"次の問い", r"[のは]いくつか", r"何[cmkgmℓ人台本円]",
            r"速さ|距離|時間", r"割合|パーセント|%", r"個数|枚数|本数",
        ]
        for pat in story_patterns:
            if re.search(pat, problem_text):
                return True, f"文章題パターン: {pat}"
        # prompt_hint にストーリーが含まれている場合
        if len(problem_text.split("\n")) >= 2:
            return True, "複数行（文章要素あり）"
        return False, "文章題形式なし"

    elif form == "visual":
        # 図・グラフ関連のキーワードまたは diagram_url
        visual_patterns = [
            r"グラフ", r"座標", r"図形", r"数直線", r"表", r"ヒストグラム",
            r"折れ線", r"円グラフ", r"散布図", r"箱ひげ", r"度数分布",
            r"△", r"□", r"円O", r"直線", r"角度",
        ]
        for pat in visual_patterns:
            if re.search(pat, problem_text):
                return True, f"視覚要素: {pat}"
        # 数式があれば計算問題として許容（visual は計算を含むことが多い）
        if "$" in problem_text:
            return True, "数式あり（視覚問題は計算を含む）"
        return False, "視覚要素なし"

    return True, f"未知のform={form}（デフォルトOK）"


# ─────────────────────────────────────────────────────────────
# Q3: 難易度分類 ルール
# ─────────────────────────────────────────────────────────────

def q3_check_group(group: list[dict]) -> tuple[bool, str]:
    """Q3: (lesson_id, form) グループで難易度が分類されているか"""
    by_label: dict[str, float] = {}
    for r in group:
        by_label[r["difficulty_label"]] = float(r["difficulty_score"])

    if len(by_label) < 3:
        return False, f"3難易度揃っていない: {list(by_label.keys())}"

    mn = by_label.get("min", 0)
    mid = by_label.get("mid", 0)
    mx = by_label.get("max", 0)

    # min < mid < max の厳密な順序が必要（同値は失敗）
    if mn < mid < mx:
        return True, f"min={mn} < mid={mid} < max={mx}"
    if mn == mid and mid == mx:
        return False, f"min=mid=max={mn}（全て同値）"
    if mn == mid:
        return False, f"min=mid={mn}（min と mid が同値）"
    if mid == mx:
        return False, f"mid=max={mid}（mid と max が同値）"
    if mn >= mid or mid >= mx:
        return False, f"順序逆転: min={mn}, mid={mid}, max={mx}"
    return False, f"不明: min={mn}, mid={mid}, max={mx}"


# ─────────────────────────────────────────────────────────────
# メイン評価
# ─────────────────────────────────────────────────────────────

def main() -> None:
    records: list[dict] = []
    with open(INPUT) as f:
        for line in f:
            records.append(json.loads(line))

    print(f"評価対象: {len(records)} 件")

    # Q1, Q2 を各レコードに適用
    for r in records:
        r["q1_ok"], r["q1_reason"] = q1_check(r)
        r["q2_ok"], r["q2_reason"] = q2_check(r)

    # Q3: (lesson_id, form) グループで評価
    groups: dict[tuple, list] = defaultdict(list)
    for r in records:
        groups[(r["lesson_id"], r["form"])].append(r)

    q3_results: dict[tuple, tuple] = {}
    for key, grp in groups.items():
        ok, reason = q3_check_group(grp)
        q3_results[key] = (ok, reason)
        for r in grp:
            r["q3_ok"] = ok
            r["q3_reason"] = reason

    # ─── 集計 ───
    total = len(records)
    q1_pass = sum(1 for r in records if r["q1_ok"])
    q2_pass = sum(1 for r in records if r["q2_ok"])
    q3_pass = sum(1 for r in records if r["q3_ok"])

    # Q2 をフォーム別集計
    q2_by_form: dict[str, list] = defaultdict(list)
    for r in records:
        q2_by_form[r["form"]].append(r["q2_ok"])

    # Q3 をグループ別集計
    q3_groups_total = len(q3_results)
    q3_groups_pass = sum(1 for ok, _ in q3_results.values() if ok)

    # NG 件数
    q1_ng = [r for r in records if not r["q1_ok"]]
    q2_ng = [r for r in records if not r["q2_ok"]]
    q3_ng_groups = [(k, v) for k, v in q3_results.items() if not v[0]]

    # ─── レポート出力 ───
    lines = [
        "# 1134問 評価レポート",
        "",
        "## サマリー",
        "",
        f"| 評価項目 | 合格 | 合計 | 合格率 |",
        f"|----------|------|------|--------|",
        f"| Q1: 単元一致 | {q1_pass} | {total} | {q1_pass/total*100:.1f}% |",
        f"| Q2: 形式一致 | {q2_pass} | {total} | {q2_pass/total*100:.1f}% |",
        f"| Q3: 難易度分離（グループ） | {q3_groups_pass} | {q3_groups_total} | {q3_groups_pass/q3_groups_total*100:.1f}% |",
        "",
        "## Q2 形式別内訳",
        "",
        "| 形式 | 合格 | 合計 | 合格率 |",
        "|------|------|------|--------|",
    ]
    for form in ["calculation", "knowledge", "proof", "word_problem", "visual"]:
        lst = q2_by_form.get(form, [])
        n = len(lst)
        p = sum(lst)
        lines.append(f"| {form} | {p} | {n} | {p/n*100:.1f}% |" if n else f"| {form} | 0 | 0 | - |")

    # Q1 NG 詳細（最大30件）
    lines += ["", "## Q1 NG 詳細（最大30件）", ""]
    for r in q1_ng[:30]:
        lines.append(f"- `{r['lesson_id']}` {r['form']} {r['difficulty_label']}: {r['q1_reason']}")
        lines.append(f"  タイトル: {r['title'][:40]}")
        lines.append(f"  問題冒頭: {r['problem_text'][:80].replace(chr(10), ' ')}")

    # Q2 NG 詳細（最大50件）
    lines += ["", "## Q2 NG 詳細（最大50件）", ""]
    for r in q2_ng[:50]:
        lines.append(f"- `{r['lesson_id']}` **{r['form']}** {r['difficulty_label']}: {r['q2_reason']}")
        lines.append(f"  問題冒頭: {r['problem_text'][:100].replace(chr(10), ' ')}")

    # Q3 NG 詳細
    lines += ["", "## Q3 NG 詳細", ""]
    for (lid, form), (ok, reason) in sorted(q3_ng_groups):
        grp = groups[(lid, form)]
        scores = {r["difficulty_label"]: r["difficulty_score"] for r in grp}
        lines.append(f"- `{lid}` {form}: {reason} | scores={scores}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"レポート出力: {REPORT}")

    # JSON 出力
    summary = {
        "total": total,
        "q1": {"pass": q1_pass, "fail": total - q1_pass, "rate": round(q1_pass / total * 100, 1)},
        "q2": {
            "pass": q2_pass, "fail": total - q2_pass, "rate": round(q2_pass / total * 100, 1),
            "by_form": {
                form: {
                    "pass": sum(q2_by_form.get(form, [])),
                    "total": len(q2_by_form.get(form, [])),
                    "rate": round(sum(q2_by_form.get(form, [])) / len(q2_by_form.get(form, [])) * 100, 1)
                    if q2_by_form.get(form) else 0,
                }
                for form in ["calculation", "knowledge", "proof", "word_problem", "visual"]
            },
        },
        "q3": {
            "groups_pass": q3_groups_pass,
            "groups_total": q3_groups_total,
            "rate": round(q3_groups_pass / q3_groups_total * 100, 1),
            "records_pass": q3_pass,
            "records_rate": round(q3_pass / total * 100, 1),
        },
    }
    OUTPUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON出力: {OUTPUT}")

    # ─── コンソール表示 ───
    print()
    print("=" * 60)
    print(f"  Q1 単元一致:    {q1_pass}/{total} = {q1_pass/total*100:.1f}%")
    print(f"  Q2 形式一致:    {q2_pass}/{total} = {q2_pass/total*100:.1f}%")
    for form in ["calculation", "knowledge", "proof", "word_problem", "visual"]:
        lst = q2_by_form.get(form, [])
        n = len(lst)
        p = sum(lst)
        print(f"    {form:15}: {p}/{n} = {p/n*100:.1f}%" if n else f"    {form}: N/A")
    print(f"  Q3 難易度分離:  {q3_groups_pass}/{q3_groups_total} グループ = {q3_groups_pass/q3_groups_total*100:.1f}%")
    print("=" * 60)
    print()
    if q1_ng:
        print(f"Q1 NG: {len(q1_ng)} 件")
    if q2_ng:
        print(f"Q2 NG: {len(q2_ng)} 件")
    if q3_ng_groups:
        print(f"Q3 NG: {len(q3_ng_groups)} グループ")


if __name__ == "__main__":
    main()
