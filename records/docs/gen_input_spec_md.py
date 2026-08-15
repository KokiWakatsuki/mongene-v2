#!/usr/bin/env python3
"""input_spec_2026-07-08.md を .json から生成する（JSON が唯一の正）。

使い方: .venv/bin/python docs/gen_input_spec_md.py
- lessons は JSON の並び順（=教育的な単元順）でそのまま出力。
- section が変わるところで `### <section>` を挿す。
- 各 level は desc に加え、任意で example / market_ref を 2 行で描画。
- §2/§3 の分布は JSON から自動集計（手打ちしない）。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
JSON = os.path.join(BASE, "input_spec_2026-07-08.json")
OUT = os.path.join(BASE, "input_spec_2026-07-08.md")

FORM_JP = {
    "knowledge": "知識",
    "calculation": "計算",
    "find_value": "求値",
    "construction": "作図",
    "graph_table": "図・グラフ・表",
    "proof": "証明・説明",
    "word_problem": "文章題",
}
FORM_ORDER = ["knowledge", "calculation", "find_value", "construction",
              "graph_table", "proof", "word_problem"]
BAND_ABBR = {"基礎": "基", "標準": "標", "応用": "応", "発展": "発"}
BAND_LV = {"基礎": 1, "標準": 2, "応用": 3, "発展": 4}


def collect_stats(d):
    """§2/§3 用の集計。"""
    seg_hist = {1: 0, 2: 0, 3: 0, 4: 0}   # 段数（=level 個数）分布
    start_hist = {1: 0, 2: 0, 3: 0, 4: 0}  # 開始 Lv 分布
    form_primary = {f: 0 for f in FORM_ORDER}  # 主要形式（先頭 form）
    form_cells = 0
    gap_cells = 0
    for L in d["lessons"]:
        for i, f in enumerate(L["forms"]):
            form_cells += 1
            if i == 0:
                form_primary[f["form"]] += 1
            levels = f["levels"]
            seg_hist[len(levels)] = seg_hist.get(len(levels), 0) + 1
            start_hist[levels[0]["level"]] = start_hist.get(levels[0]["level"], 0) + 1
            seq = [lv["level"] for lv in levels]
            if any(b - a > 1 for a, b in zip(seq, seq[1:])):
                gap_cells += 1
    return dict(seg_hist=seg_hist, start_hist=start_hist,
                form_primary=form_primary, form_cells=form_cells, gap_cells=gap_cells)


def preamble(d, s):
    seg = s["seg_hist"]
    st = s["start_hist"]
    fp = s["form_primary"]
    fc = s["form_cells"]
    seg_txt = " ／ ".join(f"{k}段 {seg.get(k,0)}" for k in (1, 2, 3, 4))
    start_txt = " ／ ".join(f"Lv{k}開始 {st.get(k,0)}" for k in (1, 2, 3) if st.get(k, 0))
    form_cols = " | ".join(FORM_JP[f] for f in FORM_ORDER)
    form_vals = " | ".join(str(fp[f]) for f in FORM_ORDER)
    return f"""# 入力層 確定仕様 v3.3（単元 × 問題形式7型 × 構造的な難易度段）— 2026-07-08

mongene-v2＝「問題が確定していない問題集」＝生徒が **単元→問題形式→難易度段** を選ぶと無限に問題が湧くシステム。この文書はその**生徒操作メニュー**の確定仕様。既存 mapping.json は根拠にしない。フェーズ①の成果物。物差し詳細は `input_spec_framework_2026-07-08.md`。
**この .md は `input_spec_2026-07-08.json` から `docs/gen_input_spec_md.py` で生成される（JSONが唯一の正・手編集しない）。**
v3.1: 3視点レビュー(教育的妥当性/分類厳密性/生徒UX)で是正済み。
v3.2: **Lv番号を band 絶対値に固定**（基礎=Lv1／標準=Lv2／応用=Lv3／発展=Lv4）。全セルLv1開始を廃止し、そのセルに実在する段の band が示すLvを付す（応用しかなければLv3から始まる）。段の中身は不変・番号のみ再割当。
v3.3: 各Lvに **例（自作の具体例）** と **市販（市販問題ではこのくらいの位置づけ、という緩い目安）** を付与。desc の抽象を「こういう問題」に接地。

## 1. 問題形式 = 7型

知識／計算／求値／作図／図・グラフ・表／証明・説明／文章題。**2階層**: 1〜6は原子的タイプ、7 文章題は複合(大枠＋小問, 小問は求値等を内包)。
計算=式が与えられ立式なし／求値=図・点・条件から自分で立式(変化の割合・変域・図形計量・関数式決定・確率の数え上げ)／文章題=設定を読み解き何を求めるか構成。
**図・グラフ・表**=グラフ/表/図をかく・読むが目的そのもの(移動/投影図/回転体含む)。証明・求値の途中で図を読むだけは独立フォームにしない。

## 2. 難易度 = 構造的な段（数字の大小でなく構造が変わる・段数可変）

各(単元×形式)に構造的に区別できる段だけ列挙。段数分布（全{fc} form-cell）: {seg_txt}。
**Lv番号は band 絶対値**（基礎=1／標準=2／応用=3／発展=4）＝そのセルに実在する段の band が示すLvを付す（Lv1固定開始しない）。開始Lv分布（全{fc} form-cell）: {start_txt}。実在する段だけ載せるため Lv1,3 や Lv2,4 のように番号が飛ぶセルもある（該当セル{s['gap_cells']}件・中間 band が構造的に存在しない）。

## 3. 主要形式分布
| {form_cols} |
|{'|'.join(['---']*7)}|
| {form_vals} |

## 4. 単元監査
- 大単元・小単元は学習指導要領4領域＋標準配当に一致し妥当。入試対策7件＝融合セクション。
- レビュー是正で単元注釈: g3_l53分割・g2_l29/g3_l38タイトル明示・g2_l15→l14統合（unit_flagとnotesに記録・phase③でmapping反映）。

## 5. 全レッスン確定仕様
凡例: 形式は主要度順。各Lv = **Lv番号(基/標/応/発) 構造的記述**、続けて **例**（自作の具体例）と **市販**（市販問題での位置づけの目安）。**Lv番号=band絶対値**(基=1/標=2/応=3/発=4)。⚑=単元注釈。
"""


def lesson_block(L):
    lines = []
    flag = ""
    if L.get("unit_flag") and L["unit_flag"] != "ok":
        flag = f" ⚑{L['unit_flag']}"
    lines.append(f"**{L['lesson_id']} {L['title']}**{flag}")
    for f in L["forms"]:
        lines.append(f"- {FORM_JP[f['form']]}")
        for lv in f["levels"]:
            b = BAND_ABBR[lv["band"]]
            lines.append(f"  - Lv{lv['level']}({b}) {lv['desc']}")
            if lv.get("example"):
                lines.append(f"    - 例: {lv['example']}")
            if lv.get("market_ref"):
                lines.append(f"    - 市販: {lv['market_ref']}")
    note = (L.get("notes") or "").strip()
    if note:
        lines.append(f"  <sub>※{note}</sub>")
    return "\n".join(lines)


def main():
    d = json.loads(open(JSON, encoding="utf-8").read())
    s = collect_stats(d)
    out = [preamble(d, s)]
    cur_section = None
    for L in d["lessons"]:
        if L["section"] != cur_section:
            cur_section = L["section"]
            out.append("")
            out.append(f"### {cur_section}")
        out.append("")
        out.append(lesson_block(L))
    text = "\n".join(out) + "\n"
    open(OUT, "w", encoding="utf-8").write(text)
    print(f"generated {OUT}: {len(d['lessons'])} lessons, {len(s['form_primary'])} forms, {s['form_cells']} form-cells")


if __name__ == "__main__":
    main()
