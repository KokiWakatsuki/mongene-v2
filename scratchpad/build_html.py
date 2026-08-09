"""コーパスを、人に見せられる1枚の HTML にする。

`scratchpad/corpus/INDEX.md` から (セル, 型, seed) を読み、問題をもう一度生成して
（seed があるので同じものが出る）、図は SVG のまま埋め込む。

表示は日本語にする: `knowledge` → 知識、`g1_l7` → 中1 第7回「累乗の計算（指数）」。
単元名・章立て・難易度の帯は台帳（units.generated.yaml）から取る。

実行: PYTHONPATH=. .venv/bin/python scratchpad/build_html.py
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import yaml

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_SRC = Path("scratchpad/corpus/INDEX.md")
_OUT = Path("scratchpad/corpus/mongene_problems.html")

_FORM_JA = {
    "knowledge": "知識", "calculation": "計算", "find_value": "求値",
    "graph_table": "グラフ・表", "construction": "作図", "proof": "証明",
    "word_problem": "文章題",
}
_GRADE_JA = {"g1": "中1", "g2": "中2", "g3": "中3", "exam": "入試"}
_GRADE_FULL = {"g1": "中学1年", "g2": "中学2年", "g3": "中学3年", "exam": "入試対策"}
_GRADE_ORDER = {"g1": 0, "g2": 1, "g3": 2, "exam": 3}
_FORM_ORDER = {
    "knowledge": 0, "calculation": 1, "find_value": 2, "graph_table": 3,
    "construction": 4, "proof": 5, "word_problem": 6,
}

_CELL_RE = re.compile(r"^##\s+(exam|g[123])_l(\d+)\.(\w+)\.Lv(\d+)")
_TYPE_RE = re.compile(r"^###\s+型(\d+)\s+`([^`]*)`\s+\(seed (\d+)\)")


def parse_index() -> list[dict]:
    """INDEX.md から (セル, 型, seed) を拾う。"""
    cells: list[dict] = []
    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cells.append({
                "grade": m.group(1), "lesson": int(m.group(2)),
                "form": m.group(3), "level": int(m.group(4)), "types": [],
            })
            continue
        t = _TYPE_RE.match(line)
        if t and cells:
            cells[-1]["types"].append(
                {"n": int(t.group(1)), "label": t.group(2), "seed": int(t.group(3))}
            )
    return cells


def esc(s: str) -> str:
    return html.escape(s or "")


def para(s: str) -> str:
    """改行を段落に（問題文・解説は複数行になる）。"""
    return "".join(f"<p>{esc(line)}</p>" for line in (s or "").split("\n") if line.strip())


def answer_html(answer) -> str:
    """答えを出す。**答えは4種類あって、取り出し方が違う。**

    symbolic は `display`、proof は `text`、choice は `correct`（選択肢は別に見せる）、
    graph は `features` の並び。`display` だけを見ていると、知識（choice）と
    作図（graph）の答えが空欄になる。
    """
    kind = getattr(answer, "kind", "")
    if kind == "choice":
        correct = esc(str(getattr(answer, "correct", "")))
        others = [esc(str(d)) for d in (getattr(answer, "distractors", None) or [])]
        chips = "".join(f'<span class="opt">{o}</span>' for o in others)
        return (
            f'<p class="correct">{correct}</p>'
            + (f'<p class="opts">ほかの選択肢 {chips}</p>' if chips else "")
        )
    if kind == "graph":
        feats = getattr(answer, "features", None) or []
        items = "".join(
            f'<li>{esc(str(getattr(f, "display", None) or f))}</li>' for f in feats
        )
        return f'<ul class="feats">{items}</ul>' if items else ""
    text = getattr(answer, "display", None) or getattr(answer, "text", "")
    return para(str(text))


def main() -> None:
    env = make_env()
    units = yaml.safe_load(open("engine/curriculum/math/units.generated.yaml", encoding="utf-8"))
    units = units.get("units", units)
    cells = parse_index()

    body: list[str] = []
    toc: list[str] = []
    current_grade = None
    current_unit = None
    n_types = n_figs = 0

    for cell in cells:
        grade, lesson = cell["grade"], cell["lesson"]
        unit = f"{grade}_l{lesson}"
        form, level = cell["form"], cell["level"]
        meta = units.get(unit, {})
        title = meta.get("title", unit)
        section = meta.get("section", "")
        band = (
            meta.get("forms", {}).get(form, {})
            .get("levels", {}).get(str(level), {}).get("band", "")
        )

        if grade != current_grade:
            current_grade = grade
            current_unit = None
            toc.append(f'<li class="toc-grade">{esc(_GRADE_FULL[grade])}</li>')
            body.append(
                f'<section class="grade-break" id="grade-{grade}">'
                f'<h2>{esc(_GRADE_FULL[grade])}</h2></section>'
            )
        if unit != current_unit:
            current_unit = unit
            toc.append(
                f'<li class="toc-unit"><a href="#{unit}">'
                f'<span class="toc-no">{_GRADE_JA[grade]} 第{lesson}回</span>'
                f'<span class="toc-title">{esc(title)}</span></a></li>'
            )
            chapter = section.split("／")[-1].strip() if section else ""
            body.append(
                f'<header class="unit" id="{unit}">'
                f'<p class="eyebrow">{esc(_GRADE_JA[grade])} 第{lesson}回'
                + (f' <span class="chapter">{esc(chapter)}</span>' if chapter else "")
                + f'</p><h3>{esc(title)}</h3></header>'
            )

        body.append(
            f'<div class="cell" data-form="{form}" data-grade="{grade}">'
            f'<div class="cell-head">'
            f'<span class="tag tag-{form}">{esc(_FORM_JA.get(form, form))}</span>'
            f'<span class="lv">Lv{level}</span>'
            + (f'<span class="band">{esc(band)}</span>' if band else "")
            + f'<span class="count">{len(cell["types"])} 型</span>'
            f'</div>'
        )

        for t in cell["types"]:
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form,
                                level=level, seed=t["seed"]),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                continue
            n_types += 1
            sq = res.sub_questions[0]
            ans_html = answer_html(sq.answer)
            fig = ""
            if res.visual_svg:
                n_figs += 1
                fig = f'<figure class="fig">{res.visual_svg}</figure>'
            label = t["label"]
            label_html = (
                f'<span class="type-label">{esc(label)}</span>'
                if label not in ("（軸なし）",) else ""
            )
            body.append(
                f'<article class="card">'
                f'<div class="card-head"><span class="type-n">型 {t["n"]}</span>'
                f'{label_html}<span class="seed">seed {t["seed"]}</span></div>'
                f'<div class="q">{para(res.problem_text)}</div>'
                f'{fig}'
                f'<div class="ask">{esc(sq.prompt_text)}</div>'
                f'<div class="a"><span class="a-label">答え</span>'
                f'<div class="a-body">{ans_html}</div></div>'
                f'<details class="ex"><summary>解説</summary>'
                f'<div class="ex-body">{para(sq.explanation)}</div></details>'
                f'</article>'
            )
        body.append("</div>")

    counts = {
        "cells": len(cells), "types": n_types, "figs": n_figs,
        "units": len({(c["grade"], c["lesson"]) for c in cells}),
    }
    page = _TEMPLATE.format(
        toc="\n".join(toc), body="\n".join(body),
        n_cells=counts["cells"], n_types=counts["types"],
        n_figs=counts["figs"], n_units=counts["units"],
    )
    _OUT.write_text(page, encoding="utf-8")
    print(f"{counts} → {_OUT}  ({_OUT.stat().st_size / 1048576:.1f} MB)")


_TEMPLATE = """<title>中学数学 問題生成エンジン ― 生成できる全問題</title>
<style>
:root {{
  --paper: #FBFBF9;      --ink: #1A2430;
  --indigo: #1F3D7A;     --vermilion: #B23A28;
  --rule: #E1E4E8;       --muted: #616C79;
  --panel: #F3F4F1;      --shadow: 0 1px 2px rgba(26,36,48,.06);
  --serif: "Hiragino Mincho ProN", "Yu Mincho", "YuMincho", "MS PMincho", serif;
  --sans: "Hiragino Sans", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", system-ui, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --paper: #12161C;    --ink: #E4E8ED;
    --indigo: #8FA9E8;   --vermilion: #E58A75;
    --rule: #262E39;     --muted: #8B95A2;
    --panel: #181D25;    --shadow: none;
  }}
}}
:root[data-theme="dark"] {{
  --paper: #12161C;      --ink: #E4E8ED;
  --indigo: #8FA9E8;     --vermilion: #E58A75;
  --rule: #262E39;       --muted: #8B95A2;
  --panel: #181D25;      --shadow: none;
}}
:root[data-theme="light"] {{
  --paper: #FBFBF9;      --ink: #1A2430;
  --indigo: #1F3D7A;     --vermilion: #B23A28;
  --rule: #E1E4E8;       --muted: #616C79;
  --panel: #F3F4F1;      --shadow: 0 1px 2px rgba(26,36,48,.06);
}}

* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--paper); color: var(--ink);
  font-family: var(--sans); font-size: 16px; line-height: 1.85;
  -webkit-font-smoothing: antialiased;
}}
a {{ color: var(--indigo); }}
:focus-visible {{ outline: 2px solid var(--indigo); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}

/* ---- 全体の骨格 ---- */
.wrap {{ display: grid; grid-template-columns: 268px minmax(0, 1fr); gap: 0; }}
.side {{
  position: sticky; top: 0; align-self: start; height: 100vh; overflow-y: auto;
  border-right: 1px solid var(--rule); padding: 28px 20px 60px; background: var(--panel);
}}
main {{ padding: 0 40px 120px; max-width: 860px; }}

/* ---- 表紙 ---- */
.masthead {{ padding: 64px 0 36px; border-bottom: 2px solid var(--ink); margin-bottom: 8px; }}
.masthead h1 {{
  font-family: var(--serif); font-weight: 600; font-size: 2.1rem;
  line-height: 1.4; margin: 0 0 10px; letter-spacing: .02em; text-wrap: balance;
}}
.masthead .lede {{ margin: 0 0 26px; color: var(--muted); max-width: 60ch; }}
.stats {{ display: flex; flex-wrap: wrap; gap: 30px; margin: 0; padding: 0; }}
.stats div {{ display: flex; flex-direction: column; gap: 2px; }}
.stats dt {{
  font-size: .74rem; letter-spacing: .12em; color: var(--muted);
  text-transform: none;
}}
.stats dd {{
  margin: 0; font-family: var(--serif); font-size: 1.75rem; font-weight: 600;
  font-variant-numeric: tabular-nums; line-height: 1.1;
}}

/* ---- 目次 ---- */
.side h2 {{
  font-family: var(--serif); font-size: .95rem; margin: 0 0 16px;
  letter-spacing: .06em; font-weight: 600;
}}
.filter {{
  width: 100%; padding: 8px 10px; margin-bottom: 18px; font: inherit; font-size: .85rem;
  border: 1px solid var(--rule); border-radius: 4px;
  background: var(--paper); color: var(--ink);
}}
.toc {{ list-style: none; margin: 0; padding: 0; font-size: .82rem; line-height: 1.5; }}
.toc-grade {{
  font-family: var(--serif); font-weight: 600; font-size: .9rem; color: var(--indigo);
  margin: 22px 0 8px; padding-bottom: 5px; border-bottom: 1px solid var(--rule);
}}
.toc-grade:first-child {{ margin-top: 0; }}
.toc-unit a {{
  display: flex; flex-direction: column; gap: 1px; padding: 5px 8px;
  text-decoration: none; color: var(--ink); border-radius: 4px;
}}
.toc-unit a:hover {{ background: var(--paper); }}
.toc-no {{
  font-family: var(--mono); font-size: .68rem; color: var(--muted);
  font-variant-numeric: tabular-nums;
}}
.toc-title {{ font-size: .82rem; }}

/* ---- 学年の区切り ---- */
.grade-break {{ margin: 76px 0 8px; padding-top: 20px; border-top: 2px solid var(--ink); }}
.grade-break:first-of-type {{ margin-top: 40px; }}
.grade-break h2 {{
  font-family: var(--serif); font-size: 1.6rem; font-weight: 600;
  margin: 0; letter-spacing: .08em;
}}

/* ---- 単元 ---- */
.unit {{ margin: 52px 0 18px; }}
.eyebrow {{
  font-family: var(--mono); font-size: .7rem; letter-spacing: .1em;
  color: var(--muted); margin: 0 0 4px; font-variant-numeric: tabular-nums;
}}
.chapter {{ font-family: var(--sans); letter-spacing: 0; }}
.unit h3 {{
  font-family: var(--serif); font-size: 1.24rem; font-weight: 600;
  margin: 0; line-height: 1.5; text-wrap: balance;
}}

/* ---- セル（form × Lv） ---- */
.cell {{ margin: 0 0 26px; }}
.cell-head {{
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 6px 0 10px; border-bottom: 1px solid var(--rule); margin-bottom: 14px;
}}
.tag {{
  font-size: .74rem; letter-spacing: .06em; padding: 2px 9px; border-radius: 3px;
  border: 1px solid var(--indigo); color: var(--indigo); font-weight: 600;
}}
.lv {{ font-family: var(--mono); font-size: .78rem; font-weight: 600; }}
.band, .count {{ font-size: .74rem; color: var(--muted); }}
.count {{ margin-left: auto; font-family: var(--mono); font-variant-numeric: tabular-nums; }}

/* ---- 1問 ---- */
.card {{
  border: 1px solid var(--rule); border-radius: 6px; background: var(--paper);
  padding: 18px 20px 14px; margin-bottom: 12px; box-shadow: var(--shadow);
}}
.card-head {{
  display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
  margin-bottom: 10px; font-size: .72rem;
}}
.type-n {{
  font-family: var(--serif); font-weight: 600; font-size: .84rem; color: var(--indigo);
}}
.type-label {{
  font-family: var(--mono); font-size: .68rem; color: var(--muted);
  background: var(--panel); padding: 1px 7px; border-radius: 3px;
  overflow-wrap: anywhere;
}}
.seed {{
  margin-left: auto; font-family: var(--mono); font-size: .66rem; color: var(--muted);
  font-variant-numeric: tabular-nums;
}}
.q p {{ margin: 0 0 .5em; font-size: 1.02rem; }}
.q p:last-child {{ margin-bottom: 0; }}
.ask {{ margin-top: 8px; font-size: .88rem; color: var(--muted); }}
.fig {{
  margin: 14px 0; padding: 10px; border: 1px solid var(--rule); border-radius: 4px;
  overflow-x: auto; background: #fff; text-align: center;
}}
.fig svg {{ max-width: 100%; height: auto; }}

.a {{
  display: flex; gap: 12px; margin-top: 14px; padding: 10px 0 2px 14px;
  border-left: 3px solid var(--vermilion);
}}
.a-label {{
  flex: none; font-family: var(--serif); font-size: .8rem; font-weight: 600;
  color: var(--vermilion); padding-top: .18em;
}}
.a-body p {{ margin: 0 0 .3em; font-size: .95rem; }}
.a-body p:last-child {{ margin-bottom: 0; }}
.a-body .correct {{ font-weight: 600; }}
.a-body .opts {{ font-size: .8rem; color: var(--muted); margin-top: .35em; }}
.a-body .opt {{
  display: inline-block; margin-left: 6px; padding: 0 7px;
  border: 1px solid var(--rule); border-radius: 3px; color: var(--muted);
}}
.a-body .feats {{ margin: 0; padding-left: 1.2em; }}
.a-body .feats li {{ font-size: .93rem; margin-bottom: .15em; }}

.ex {{ margin-top: 12px; border-top: 1px dotted var(--rule); padding-top: 8px; }}
.ex summary {{
  cursor: pointer; font-size: .8rem; color: var(--muted);
  font-family: var(--serif); letter-spacing: .04em;
}}
.ex summary:hover {{ color: var(--indigo); }}
.ex-body {{ margin-top: 8px; }}
.ex-body p {{ margin: 0 0 .4em; font-size: .87rem; color: var(--muted); }}

/* ---- 狭い画面 ---- */
@media (max-width: 900px) {{
  .wrap {{ grid-template-columns: 1fr; }}
  .side {{ position: static; height: auto; border-right: none;
           border-bottom: 1px solid var(--rule); }}
  main {{ padding: 0 20px 80px; }}
  .masthead {{ padding-top: 36px; }}
}}
</style>

<div class="wrap">
<nav class="side">
  <h2>目次</h2>
  <input class="filter" id="filter" type="search" placeholder="単元名でしぼりこむ"
         aria-label="単元名でしぼりこむ">
  <ul class="toc" id="toc">
{toc}
  </ul>
</nav>

<main>
  <div class="masthead">
    <h1>中学数学 問題生成エンジン<br>生成できる問題の全型</h1>
    <p class="lede">単元・形式・難易度のすべての組み合わせについて、構造の違う問題を
    ひとつずつ並べたもの。同じ型でも単元・形式・難易度が違えば別に載せている。
    数値・文字・人名はこのほかに無数の組み合わせがある。</p>
    <dl class="stats">
      <div><dt>単元</dt><dd>{n_units}</dd></div>
      <div><dt>単元 × 形式 × 難易度</dt><dd>{n_cells}</dd></div>
      <div><dt>構造の違う問題</dt><dd>{n_types}</dd></div>
      <div><dt>図</dt><dd>{n_figs}</dd></div>
    </dl>
  </div>
{body}
</main>
</div>

<script>
(function () {{
  var input = document.getElementById('filter');
  var items = Array.prototype.slice.call(
    document.querySelectorAll('#toc .toc-unit')
  );
  input.addEventListener('input', function () {{
    var q = input.value.trim();
    items.forEach(function (li) {{
      li.style.display = !q || li.textContent.indexOf(q) !== -1 ? '' : 'none';
    }});
  }});
}})();
</script>
"""


if __name__ == "__main__":
    main()
