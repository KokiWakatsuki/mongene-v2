"""実装カバレッジ台帳を 1 枚の HTML ページに書き出す CLI。

`goal_progress` が C1〜C16 グループの数字を出すのに対し、本ツールは同じ実測値
（分母＝`units.generated.yaml` の全セル・分子＝`capabilities()`）を
**学年 → 単元群（章）→ 単元 → セル**の粒度まで展開して人が読める表にする。
どのセルが空いているかを一目で掴み、次に投資する capability を決めるための道具。

`engine.tools` は core/packs/curriculum を「読むだけ」の利用者（実装設計 §3 の依存規律）。

出力は `<title>` + `<style>` + 本文だけの自己完結ページ（外部リソース参照なし・doctype や
`<html>`/`<body>` を含まない）。ブラウザでそのまま開けるうえ、共有用にそのまま貼れる。

使い方:
  python -m engine.tools.coverage_page                 # docs/coverage.html を更新
  python -m engine.tools.coverage_page --out /tmp/x.html
"""
from __future__ import annotations

import argparse
import collections
import html
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from engine.bootstrap import bootstrap
from engine.core.pipeline import capabilities
from engine.tools.goal_progress import _UNITS_PATH, _grade

_DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "coverage.html"

# 未着手の形式（form ごと frame/solver/checker が無い）＝T1 の分母から外して読む。
# word_problem は当初ここに入れていたが、family が `text: {tier: T1, ...}` で実装され
# 64/100 まで進んだ時点で「送り」の前提が失効したため T1 側に戻した。
_DEFERRED_FORMS = frozenset({"proof", "construction"})

# 形式の表示名と、セルチップに使う 1 文字
_FORM_LABELS: dict[str, tuple[str, str]] = {
    "calculation": ("計算", "計"),
    "find_value": ("求値", "求"),
    "graph_table": ("表・グラフ", "図"),
    "knowledge": ("知識", "知"),
    "word_problem": ("文章題", "文"),
    "proof": ("証明", "証"),
    "construction": ("作図", "作"),
}
_FORM_ORDER = list(_FORM_LABELS)

_GRADE_LABELS: dict[str, str] = {
    "g1": "中学1年", "g2": "中学2年", "g3": "中学3年", "exam": "入試対策",
}
_GRADE_ORDER = list(_GRADE_LABELS)

_BAND_LABELS: dict[int, str] = {1: "基礎", 2: "標準", 3: "応用", 4: "発展"}


# ---------------------------------------------------------------------------
# 実測（読み取りのみ）
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Cell:
    form: str
    level: int
    covered: bool

    @property
    def deferred(self) -> bool:
        return self.form in _DEFERRED_FORMS


@dataclass(frozen=True)
class Unit:
    unit: str
    grade: str
    section: str
    title: str
    cells: tuple[Cell, ...]

    @property
    def covered(self) -> int:
        return sum(1 for c in self.cells if c.covered)

    @property
    def total(self) -> int:
        """単元の全セル数。

        以前はここが `not c.deferred`（word_problem/proof/construction を除外）だった
        が、分子 `covered` は全セルを数えているため分子>分母が起き、実測で
        g3_l29=3/1・g3_l30=4/2 のような分数が出ていた。さらに完成判定を
        `covered == t1_total` でしていたため、完成済みの単元が「部分実装」、
        文章題だけ残った単元が「完成」と逆に表示されていた。
        word_problem は 64/100 まで実装済みで「分母外」の前提自体が失効している。
        単元行は goal_progress の 429/630 と同じ分母（＝全セル）で読む。
        """
        return len(self.cells)

    @property
    def chapter(self) -> str:
        """単元群（章）名＝section の末尾セグメント（例: "正の数・負の数"）。"""
        parts = [p.strip() for p in self.section.split("／")]
        return parts[-1] if parts else self.section

    @property
    def field(self) -> str:
        """領域名＝section の中間セグメント（例: "数と式"）。無ければ空。"""
        parts = [p.strip() for p in self.section.split("／")]
        return parts[1] if len(parts) > 2 else ""


def measure() -> list[Unit]:
    """units.generated.yaml（分母）× capabilities()（分子）を単元粒度で突き合わせる。"""
    units_doc: dict[str, Any] = yaml.safe_load(_UNITS_PATH.read_text(encoding="utf-8"))
    bootstrap()
    covered = {(c.unit, c.form, c.level) for c in capabilities()}

    out: list[Unit] = []
    for unit_id, unit in units_doc["units"].items():
        cells: list[Cell] = []
        for form, form_def in (unit.get("forms") or {}).items():
            for level_key in form_def.get("levels") or {}:
                level = int(level_key)
                cells.append(Cell(form, level, (unit_id, form, level) in covered))
        if not cells:
            continue
        out.append(Unit(
            unit=unit_id,
            grade=_grade(unit_id),
            section=str(unit.get("section", "")),
            title=str(unit.get("title", "")),
            cells=tuple(sorted(cells, key=lambda c: (_FORM_ORDER.index(c.form), c.level))),
        ))
    return out


# ---------------------------------------------------------------------------
# HTML 組み立て
# ---------------------------------------------------------------------------
def _esc(s: str) -> str:
    return html.escape(str(s))


def _pct(c: int, t: int) -> float:
    return (c / t * 100) if t else 0.0


def _bar(c: int, t: int, kind: str = "t1") -> str:
    return (
        f'<span class="bar" role="img" aria-label="{c}/{t}">'
        f'<span class="bar-fill {kind}" style="width:{_pct(c, t):.1f}%"></span></span>'
    )


def _num(c: int, t: int) -> str:
    return (
        f'<span class="frac"><b>{c}</b><span class="slash">/</span>{t}</span>'
        f'<span class="pc">{_pct(c, t):.0f}%</span>'
    )


def _tally(units: list[Unit], *, grade: str | None = None, form: str | None = None,
           deferred: bool | None = None, level: int | None = None) -> tuple[int, int]:
    c = t = 0
    for u in units:
        if grade is not None and u.grade != grade:
            continue
        for cell in u.cells:
            if form is not None and cell.form != form:
                continue
            if deferred is not None and cell.deferred is not deferred:
                continue
            if level is not None and cell.level != level:
                continue
            t += 1
            c += cell.covered
    return c, t


def _stat_cards(units: list[Unit]) -> str:
    total_c, total_t = _tally(units)
    t1_c, t1_t = _tally(units, deferred=False)
    df_c, df_t = _tally(units, deferred=True)
    cards = [
        ("台帳全体", total_c, total_t, "t1", "630セル＝単元×形式×難易度の疎な有効組み合わせ"),
        ("T1（自動生成の実装対象）", t1_c, t1_t, "t1", "計算・求値・表グラフ・知識・文章題の5形式"),
        ("証明・作図", df_c, df_t, "def", "form ごと未着手（frame/solver/checker が無い）"),
    ]
    out: list[str] = []
    for label, c, t, kind, note in cards:
        out.append(
            f'<article class="card"><h3>{_esc(label)}</h3>'
            f'<p class="big"><b>{c}</b><span class="of">/{t}</span>'
            f'<span class="big-pc">{_pct(c, t):.1f}%</span></p>'
            f'{_bar(c, t, kind)}<p class="note">{_esc(note)}</p></article>'
        )
    return '<div class="cards">' + "".join(out) + "</div>"


def _grade_table(units: list[Unit]) -> str:
    rows: list[str] = []
    for g in _GRADE_ORDER:
        c1, t1 = _tally(units, grade=g, deferred=False)
        cd, td = _tally(units, grade=g, deferred=True)
        n_units = sum(1 for u in units if u.grade == g)
        rows.append(
            f'<tr><th scope="row">{_esc(_GRADE_LABELS[g])}</th>'
            f'<td class="n">{n_units}</td><td class="n">{_num(c1, t1)}</td>'
            f'<td>{_bar(c1, t1)}</td><td class="n dim">{cd}/{td}</td></tr>'
        )
    return (
        '<div class="scroll"><table class="grid">'
        "<thead><tr><th>学年</th><th>単元数</th><th>T1 進捗</th><th></th><th>文章題等</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _form_table(units: list[Unit]) -> str:
    rows: list[str] = []
    for f in _FORM_ORDER:
        c, t = _tally(units, form=f)
        kind = "def" if f in _DEFERRED_FORMS else "t1"
        tag = "form ごと未着手" if f in _DEFERRED_FORMS else "T1"
        rows.append(
            f'<tr><th scope="row">{_esc(_FORM_LABELS[f][0])}'
            f'<span class="tag {kind}">{_esc(tag)}</span></th>'
            f'<td class="n">{_num(c, t)}</td><td>{_bar(c, t, kind)}</td></tr>'
        )
    return (
        '<div class="scroll"><table class="grid">'
        "<thead><tr><th>形式</th><th>進捗</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _level_table(units: list[Unit]) -> str:
    levels = sorted({cell.level for u in units for cell in u.cells if not cell.deferred})
    rows: list[str] = []
    for lv in levels:
        c, t = _tally(units, deferred=False, level=lv)
        rows.append(
            f'<tr><th scope="row">Lv{lv}<span class="band">{_esc(_BAND_LABELS.get(lv, ""))}</span></th>'
            f'<td class="n">{_num(c, t)}</td><td>{_bar(c, t)}</td></tr>'
        )
    return (
        '<div class="scroll"><table class="grid">'
        "<thead><tr><th>難易度</th><th>T1 進捗</th><th></th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


def _unit_sections(units: list[Unit]) -> str:
    sections: list[tuple[str, str]] = []
    for u in units:
        if (u.grade, u.section) not in sections:
            sections.append((u.grade, u.section))

    out: list[str] = []
    for g in _GRADE_ORDER:
        gc, gt = _tally(units, grade=g, deferred=False)
        out.append(
            f'<section class="grade"><header class="grade-hd"><h3>{_esc(_GRADE_LABELS[g])}</h3>'
            f'<span class="grade-n">T1 {gc}/{gt}</span>{_bar(gc, gt)}</header>'
        )
        for grade, section in sections:
            if grade != g:
                continue
            members = [u for u in units if u.grade == g and u.section == section]
            sc = sum(u.covered for u in members)
            st = sum(u.total for u in members)
            head = members[0]
            out.append(
                f'<div class="chapter"><div class="chapter-hd"><h4>{_esc(head.chapter)}'
                f'<span class="fieldname">{_esc(head.field)}</span></h4>'
                f'<span class="chapter-n">{_num(sc, st)}</span>{_bar(sc, st)}</div>'
                f'<table class="units"><tbody>'
            )
            for u in members:
                chips: list[str] = []
                for cell in u.cells:
                    state = "done" if cell.covered else ("def" if cell.deferred else "todo")
                    chips.append(
                        f'<span class="chip {state}" '
                        f'title="{_esc(_FORM_LABELS[cell.form][0])} Lv{cell.level}">'
                        f'{_esc(_FORM_LABELS[cell.form][1])}<span class="lv">{cell.level}</span></span>'
                    )
                mark = "full" if u.total and u.covered == u.total else ("part" if u.covered else "none")
                out.append(
                    f'<tr class="{mark}"><td class="uid">{_esc(u.unit)}</td>'
                    f'<td class="utitle">{_esc(u.title)}</td>'
                    f'<td class="uchips">{"".join(chips)}</td>'
                    f'<td class="un">{u.covered}<span class="slash">/</span>{u.total}</td></tr>'
                )
            out.append("</tbody></table></div>")
        out.append("</section>")
    return "".join(out)


def _frontier(units: list[Unit]) -> str:
    rem: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for u in units:
        for cell in u.cells:
            if not cell.covered and not cell.deferred:
                rem[(u.grade, u.chapter, cell.form)] += 1
    rows = [
        f'<tr><td class="n big-n">{v}</td><td>{_esc(_GRADE_LABELS[g])}</td>'
        f"<td>{_esc(ch)}</td><td>{_esc(_FORM_LABELS[f][0])}</td></tr>"
        for (g, ch, f), v in sorted(rem.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return (
        '<div class="scroll"><table class="grid frontier">'
        "<thead><tr><th>残</th><th>学年</th><th>単元群</th><th>形式</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div>"
    )


_CSS = """
:root{
  --ink:#141a26; --ink-2:#43506b; --ink-3:#7b8598;
  --ground:#f2f4f7; --panel:#ffffff; --line:#dde2ea; --line-2:#e9edf3;
  --done:#0f7a72; --done-soft:#d3ece8; --todo:#b9c2d0; --defer:#a9762a; --defer-soft:#f0e5d2;
  --mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,"Cascadia Mono",monospace;
  --jp:"Hiragino Kaku Gothic ProN","Hiragino Sans","Yu Gothic Medium","Yu Gothic",
       "Noto Sans JP",system-ui,sans-serif;
}
@media (prefers-color-scheme:dark){
  :root{
    --ink:#e6eaf2; --ink-2:#a4b0c4; --ink-3:#78829a;
    --ground:#10141b; --panel:#181e27; --line:#2a3341; --line-2:#222a35;
    --done:#3cb3a4; --done-soft:#1d3a3a; --todo:#39445a; --defer:#c79a4e; --defer-soft:#332c1d;
  }
}
:root[data-theme="dark"]{
  --ink:#e6eaf2; --ink-2:#a4b0c4; --ink-3:#78829a;
  --ground:#10141b; --panel:#181e27; --line:#2a3341; --line-2:#222a35;
  --done:#3cb3a4; --done-soft:#1d3a3a; --todo:#39445a; --defer:#c79a4e; --defer-soft:#332c1d;
}
:root[data-theme="light"]{
  --ink:#141a26; --ink-2:#43506b; --ink-3:#7b8598;
  --ground:#f2f4f7; --panel:#ffffff; --line:#dde2ea; --line-2:#e9edf3;
  --done:#0f7a72; --done-soft:#d3ece8; --todo:#b9c2d0; --defer:#a9762a; --defer-soft:#f0e5d2;
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--jp);
  font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:40px 20px 72px;display:flex;
  flex-direction:column;gap:38px}
h1,h2,h3,h4{margin:0;text-wrap:balance;letter-spacing:-.01em}
h1{font-size:1.85rem;font-weight:700;line-height:1.3}
.eyebrow{font-family:var(--mono);font-size:.72rem;letter-spacing:.14em;
  text-transform:uppercase;color:var(--ink-3);margin:0 0 8px}
.lede{color:var(--ink-2);margin:10px 0 0;max-width:62ch}
.lede code,.foot code{font-family:var(--mono);font-size:.88em;color:var(--ink)}
h2{font-size:1.05rem;font-weight:700;padding-bottom:9px;border-bottom:2px solid var(--ink);
  display:flex;align-items:baseline;gap:10px}
h2 .h2note{font-family:var(--mono);font-size:.7rem;letter-spacing:.06em;color:var(--ink-3);
  font-weight:400;margin-left:auto}
section.block{display:flex;flex-direction:column;gap:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(232px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);padding:18px 18px 16px;
  display:flex;flex-direction:column;gap:9px}
.card h3{font-size:.78rem;font-weight:600;color:var(--ink-2);letter-spacing:.02em}
.big{margin:0;font-family:var(--mono);font-size:2.15rem;line-height:1;
  font-variant-numeric:tabular-nums;display:flex;align-items:baseline;gap:2px}
.big b{font-weight:600}
.big .of{font-size:1.05rem;color:var(--ink-3)}
.big .big-pc{margin-left:auto;font-size:.9rem;color:var(--done)}
.note{margin:0;font-size:.76rem;color:var(--ink-3);line-height:1.5}
.bar{display:block;height:6px;background:var(--line-2);overflow:hidden;min-width:56px;width:100%}
.bar-fill{display:block;height:100%}
.bar-fill.t1{background:var(--done)}
.bar-fill.def{background:var(--defer)}
.scroll{overflow-x:auto;background:var(--panel);border:1px solid var(--line)}
table{border-collapse:collapse;width:100%}
.grid{font-size:.86rem}
.grid thead th{text-align:left;font-size:.7rem;font-weight:600;letter-spacing:.07em;
  color:var(--ink-3);padding:10px 14px;border-bottom:1px solid var(--line);white-space:nowrap}
.grid tbody th{text-align:left;font-weight:600;padding:9px 14px;white-space:nowrap;
  border-top:1px solid var(--line-2)}
.grid td{padding:9px 14px;border-top:1px solid var(--line-2);vertical-align:middle}
.grid tbody tr:first-child th,.grid tbody tr:first-child td{border-top:0}
.grid td:last-child{width:34%;min-width:110px}
.frontier td:last-child{width:auto}
.n{font-family:var(--mono);font-variant-numeric:tabular-nums;white-space:nowrap}
.n.dim{color:var(--ink-3)}
.big-n{font-size:1.05rem;font-weight:600;color:var(--defer)}
.frac b{font-weight:600}
.slash{color:var(--ink-3);margin:0 1px}
.pc{color:var(--ink-3);margin-left:8px;font-size:.8em}
.tag{font-family:var(--mono);font-size:.62rem;letter-spacing:.06em;padding:2px 5px;
  margin-left:9px;font-weight:500;vertical-align:1px}
.tag.t1{background:var(--done-soft);color:var(--done)}
.tag.def{background:var(--defer-soft);color:var(--defer)}
.band{font-size:.72rem;color:var(--ink-3);margin-left:9px;font-weight:400}
.grade{display:flex;flex-direction:column;gap:12px}
.grade-hd{display:flex;align-items:center;gap:14px;padding-bottom:7px;
  border-bottom:1px solid var(--ink-2)}
.grade-hd h3{font-size:.98rem}
.grade-n{font-family:var(--mono);font-size:.78rem;color:var(--ink-2);
  font-variant-numeric:tabular-nums;margin-left:auto;white-space:nowrap}
.grade-hd .bar{width:120px;flex:0 0 120px}
.chapter{background:var(--panel);border:1px solid var(--line)}
.chapter-hd{display:flex;align-items:center;gap:12px;padding:11px 14px;
  border-bottom:1px solid var(--line)}
.chapter-hd h4{font-size:.86rem;font-weight:700}
.fieldname{font-size:.7rem;color:var(--ink-3);margin-left:9px;font-weight:400;
  font-family:var(--mono);letter-spacing:.04em}
.chapter-n{margin-left:auto;font-family:var(--mono);font-size:.78rem;
  font-variant-numeric:tabular-nums;white-space:nowrap}
.chapter-hd .bar{width:96px;flex:0 0 96px}
.units{font-size:.8rem}
.units td{padding:7px 14px;border-top:1px solid var(--line-2)}
.units tr:first-child td{border-top:0}
.units tr.full{background:linear-gradient(90deg,var(--done-soft),transparent 62%)}
.uid{font-family:var(--mono);font-size:.72rem;color:var(--ink-3);white-space:nowrap;width:1%}
.utitle{color:var(--ink);min-width:13ch}
.uchips{width:1%;white-space:nowrap;text-align:right}
.un{font-family:var(--mono);font-size:.74rem;font-variant-numeric:tabular-nums;
  color:var(--ink-2);text-align:right;white-space:nowrap;width:1%}
.chip{display:inline-flex;align-items:baseline;gap:1px;font-size:.68rem;padding:2px 5px;
  margin-left:3px;border:1px solid transparent;line-height:1.35}
.chip .lv{font-family:var(--mono);font-size:.62rem;opacity:.75}
.chip.done{background:var(--done);color:var(--panel);border-color:var(--done)}
.chip.todo{background:transparent;color:var(--ink-3);border-color:var(--todo)}
.chip.def{background:transparent;color:var(--defer);border-color:var(--defer);
  border-style:dashed;opacity:.75}
.legend{display:flex;flex-wrap:wrap;gap:16px;align-items:center;font-size:.76rem;color:var(--ink-2)}
.legend .chip{margin-left:0;margin-right:5px}
.legend span.item{display:inline-flex;align-items:center}
.foot{font-size:.76rem;color:var(--ink-3);border-top:1px solid var(--line);padding-top:16px;
  display:flex;flex-direction:column;gap:6px}
@media (max-width:640px){
  .wrap{padding:28px 14px 56px;gap:30px}
  h1{font-size:1.45rem}
  .utitle{display:none}
  .grade-hd .bar,.chapter-hd .bar{width:70px;flex:0 0 70px}
}
"""

_LEGEND = (
    '<div class="legend">'
    '<span class="item"><span class="chip done">図<span class="lv">2</span></span>実装済み</span>'
    '<span class="item"><span class="chip todo">図<span class="lv">2</span></span>未実装（T1）</span>'
    '<span class="item"><span class="chip def">証<span class="lv">3</span></span>form ごと未着手</span>'
    '<span class="item">チップの文字＝形式（計＝計算／求＝求値／図＝表・グラフ／知＝知識'
    '／文＝文章題／証＝証明／作＝作図）、数字＝難易度</span>'
    "</div>"
)


def build_html(units: list[Unit], *, revision: str = "") -> str:
    """カバレッジ台帳ページ全体（自己完結・外部リソース参照なし）。"""
    total_c, total_t = _tally(units)
    t1_c, t1_t = _tally(units, deferred=False)
    rev = f" ／ {_esc(revision)}" if revision else ""
    return f"""<title>問題生成エンジン 実装カバレッジ台帳</title>
<style>{_CSS}</style>
<div class="wrap">
<header>
  <p class="eyebrow">engine-m0-rework{rev}</p>
  <h1>問題生成エンジン 実装カバレッジ台帳</h1>
  <p class="lede">単元 × 形式 × 難易度で定めた <b>{total_t} セル</b>のうち、いま実際に問題を生成できる
  セルの一覧。数字は <code>python -m engine.tools.goal_progress</code> と同じ経路
  （分母＝<code>units.generated.yaml</code>、分子＝<code>capabilities()</code>）で測っている。
  このページ自体は <code>python -m engine.tools.coverage_page</code> で再生成する。</p>
</header>

{_stat_cards(units)}

<section class="block">
  <h2>学年ごと<span class="h2note">T1 ＝ 計算・求値・表グラフ・知識</span></h2>
  {_grade_table(units)}
</section>

<section class="block">
  <h2>形式ごと</h2>
  {_form_table(units)}
  <p class="note">文章題・証明・作図の160セルは T3／M2 の機構待ちで、意図的に未着手のまま置いてある。
  ここを分母から外すと T1 は {t1_c}/{t1_t}（{_pct(t1_c, t1_t):.1f}%）。</p>
</section>

<section class="block">
  <h2>難易度ごと<span class="h2note">T1 のみ</span></h2>
  {_level_table(units)}
</section>

<section class="block">
  <h2>単元ごと<span class="h2note">{len(units)} 単元／緑帯 ＝ T1 完走</span></h2>
  {_LEGEND}
  {_unit_sections(units)}
</section>

<section class="block">
  <h2>残っている T1 セル<span class="h2note">計 {t1_t - t1_c}</span></h2>
  {_frontier(units)}
</section>

<footer class="foot">
  <span>出典：<code>engine/curriculum/math/units.generated.yaml</code>（分母）と
  <code>capabilities()</code>（分子）。ゴール仕様は <code>docs/goal_spec_2026-07-12.md</code> §3。</span>
  <span>「実装済み」＝ spec が実在し lint clean で生成可能なセル。
  全 {total_t} セル・{len(units)} 単元・実測 {total_c} セル（{_pct(total_c, total_t):.1f}%）。</span>
</footer>
</div>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="実装カバレッジ台帳を HTML に書き出す")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT, help="出力先（既定: docs/coverage.html）")
    parser.add_argument("--revision", default="", help="見出しに添える版の注記（例: commit 381d600）")
    args = parser.parse_args(argv)

    units = measure()
    args.out.write_text(build_html(units, revision=args.revision), encoding="utf-8")
    covered, total = _tally(units)
    print(f"{args.out} を書き出しました（{covered}/{total} セル・{len(units)} 単元）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
