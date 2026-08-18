"""コーパスを、**市販の問題集の体裁**の HTML にする（`build_html.py` とは別物）。

`build_html.py` は「中身を点検するための一覧」で、1問ごとに答えと解説が付いている。
こちらは**生徒が解く問題集**の形にする。市販品との違いはそこにある:

  - 通し番号（第1回 ①②③…）で問題を並べ、**答えは本文に出さない**
  - **解答・解説は巻末にまとめる**（市販品の別冊解答にあたる）
  - 解答欄の余白を取り、印刷（A4）でページが割れないようにする
  - 章扉・目次を置き、単元名と章名を台帳から取る

出力先は `mongene_workbook.html`。**既存の `mongene_problems.html` は触らない。**

実行: PYTHONPATH=engine_core .venv/bin/python records/work/build_workbook_html.py
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import yaml

from engine.core.contracts import GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import make_env

_SRC = Path("records/work/corpus/INDEX.md")
_OUT = Path("records/work/corpus/mongene_workbook.html")

_FORM_JA = {
    "knowledge": "知識", "calculation": "計算", "find_value": "求値",
    "graph_table": "グラフ・表", "construction": "作図", "proof": "証明",
    "word_problem": "文章題",
}
_GRADE_FULL = {"g1": "中学1年", "g2": "中学2年", "g3": "中学3年", "exam": "入試対策"}
_CELL_RE = re.compile(r"^##\s+(exam|g[123])_l(\d+)\.(\w+)\.Lv(\d+)")
_TYPE_RE = re.compile(r"^###\s+型(\d+)\s+`([^`]*)`\s+\(seed (\d+)\)")

# 解答欄の高さ（形式ごとに、書く量が違う）。
_ANSWER_BOX = {
    "proof": 200, "word_problem": 110, "construction": 150,
    "graph_table": 130, "find_value": 80, "calculation": 60, "knowledge": 60,
}


def esc(s: str) -> str:
    return html.escape(s or "")


def para(s: str, cls: str = "") -> str:
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{esc(ln)}</p>" for ln in (s or "").split("\n") if ln.strip())


def parse_index() -> list[dict]:
    cells: list[dict] = []
    for line in _SRC.read_text(encoding="utf-8").splitlines():
        m = _CELL_RE.match(line)
        if m:
            cells.append({"grade": m.group(1), "lesson": int(m.group(2)),
                          "form": m.group(3), "level": int(m.group(4)), "types": []})
            continue
        t = _TYPE_RE.match(line)
        if t and cells:
            cells[-1]["types"].append({"n": int(t.group(1)), "seed": int(t.group(3))})
    return cells


def answer_html(answer) -> str:
    """答えの取り出し方は4種類ちがう（symbolic=display / proof=text /
    choice=correct / graph=features）。display だけ見ると知識と作図が空になる。"""
    kind = getattr(answer, "kind", "")
    if kind == "choice":
        return f'<p class="ans-main">{esc(str(getattr(answer, "correct", "")))}</p>'
    if kind == "graph":
        feats = getattr(answer, "features", None) or []
        items = "、".join(esc(str(getattr(f, "display", None) or f)) for f in feats)
        return f'<p class="ans-main">{items}</p>' if items else ""
    text = getattr(answer, "display", None) or getattr(answer, "text", "")
    return para(str(text), "ans-main")


def main() -> None:
    env = make_env()
    units = yaml.safe_load(
        open("engine_core/engine/curriculum/math/units.generated.yaml", encoding="utf-8")
    )
    units = units.get("units", units)
    cells = parse_index()

    # 回（lesson）ごとにまとめる。市販品は「第N回」が1つの見開きになる。
    lessons: dict[tuple[str, int], list[dict]] = {}
    order: list[tuple[str, int]] = []
    for c in cells:
        key = (c["grade"], c["lesson"])
        if key not in lessons:
            lessons[key] = []
            order.append(key)
        lessons[key].append(c)

    toc: list[str] = []
    body: list[str] = []
    answers: list[str] = []
    cur_grade = None
    cur_chapter = None
    q_no = 0
    n_types = n_figs = 0

    for grade, lesson in order:
        unit = f"{grade}_l{lesson}"
        meta = units.get(unit, {})
        title = meta.get("title", unit)
        section = meta.get("section", "")
        chapter = section.split("／")[-1].strip() if section else ""

        if grade != cur_grade:
            cur_grade = grade
            cur_chapter = None
            toc.append(f'<li class="t-grade">{esc(_GRADE_FULL[grade])}</li>')
            body.append(
                f'<section class="divider" id="g-{grade}">'
                f'<p class="divider-en">{esc(grade.upper())}</p>'
                f'<h2>{esc(_GRADE_FULL[grade])}</h2></section>'
            )
        if chapter and chapter != cur_chapter:
            cur_chapter = chapter
            toc.append(f'<li class="t-chapter">{esc(chapter)}</li>')

        toc.append(
            f'<li class="t-lesson"><a href="#{unit}">'
            f'<span class="t-no">第{lesson}回</span>'
            f'<span class="t-title">{esc(title)}</span></a></li>'
        )
        body.append(
            f'<section class="lesson" id="{unit}">'
            f'<header class="lesson-head">'
            f'<span class="lesson-no">第{lesson}回</span>'
            f'<h3>{esc(title)}</h3>'
            + (f'<span class="lesson-chapter">{esc(chapter)}</span>' if chapter else "")
            + "</header>"
        )
        answers.append(
            f'<section class="a-lesson"><h3><span class="a-no">第{lesson}回</span>'
            f'{esc(title)}</h3>'
        )

        for cell in sorted(lessons[(grade, lesson)],
                           key=lambda c: (c["form"], c["level"])):
            form, level = cell["form"], cell["level"]
            for t in cell["types"]:
                res = generate(
                    GenerateRequest(subject="math", unit=unit, form=form,
                                    level=level, seed=t["seed"]),
                    curriculum=env.curriculum, families=env.families,
                    registry=env.registry,
                )
                if isinstance(res, Unsupported):
                    continue
                q_no += 1
                n_types += 1
                sq = res.sub_questions[0]
                fig = ""
                if res.visual_svg:
                    n_figs += 1
                    fig = f'<div class="fig">{res.visual_svg}</div>'
                box = _ANSWER_BOX.get(form, 80)
                # **問題面に答えは出さない。** 出したら問題集にならない。
                body.append(
                    f'<article class="q" id="q{q_no}">'
                    f'<div class="q-head">'
                    f'<span class="q-no">{q_no}</span>'
                    f'<span class="q-tag tag-{form}">{esc(_FORM_JA.get(form, form))}</span>'
                    f'<span class="q-lv">Lv{level}</span></div>'
                    f'<div class="q-body">{para(res.problem_text)}'
                    f'<p class="q-ask">{esc(sq.prompt_text)}</p></div>'
                    f'{fig}'
                    f'<div class="q-space" style="height:{box}px"></div>'
                    f'</article>'
                )
                hints = "".join(
                    f"<li>{esc(h)}</li>" for h in (sq.hints or [])
                )
                answers.append(
                    f'<article class="a-item">'
                    f'<div class="a-head"><span class="a-num">{q_no}</span>'
                    f'<a class="a-back" href="#q{q_no}">問題へ</a></div>'
                    f'<div class="a-ans">{answer_html(sq.answer)}</div>'
                    f'<div class="a-sol">{para(sq.explanation)}</div>'
                    + (f'<details class="a-hint"><summary>ヒント</summary>'
                       f'<ul>{hints}</ul></details>' if hints else "")
                    + "</article>"
                )
        body.append("</section>")
        answers.append("</section>")

    page = _TEMPLATE.format(
        toc="\n".join(toc), body="\n".join(body), answers="\n".join(answers),
        n_q=q_no, n_units=len(order), n_figs=n_figs,
    )
    _OUT.write_text(page, encoding="utf-8")
    print(f"問題 {q_no} 問 / 単元 {len(order)} / 図 {n_figs} → {_OUT} "
          f"({_OUT.stat().st_size / 1048576:.1f} MB)")


_TEMPLATE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中学数学 問題集</title>
<style>
:root {{
  --ink:#1a1a1a; --sub:#666; --line:#d8d8d8; --rule:#333;
  --accent:#1c4f8b; --paper:#fff; --tint:#f3f5f8;
}}
* {{ box-sizing:border-box; }}
body {{
  margin:0; background:#e9ecf0; color:var(--ink);
  font-family:"Hiragino Mincho ProN","Yu Mincho",serif;
  font-size:15px; line-height:1.85;
}}
.sheet {{
  max-width:820px; margin:0 auto; background:var(--paper);
  padding:0 56px 80px; box-shadow:0 0 0 1px rgba(0,0,0,.06);
}}
h2,h3,.q-no,.a-num,.lesson-no,.t-no {{
  font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",sans-serif;
}}

/* 表紙 */
.cover {{ padding:120px 0 90px; text-align:center; border-bottom:3px double var(--rule); }}
.cover h1 {{ font-size:40px; letter-spacing:.28em; margin:0 0 14px; font-weight:600; }}
.cover .sub {{ color:var(--sub); letter-spacing:.2em; font-size:13px; }}
.cover .stat {{ margin-top:44px; font-size:12px; color:var(--sub); letter-spacing:.12em; }}

/* 目次 */
.toc {{ padding:52px 0 20px; }}
.toc h2 {{ font-size:17px; letter-spacing:.3em; margin:0 0 24px;
  padding-bottom:8px; border-bottom:1px solid var(--rule); }}
.toc ul {{ list-style:none; margin:0; padding:0; }}
.t-grade {{ margin:26px 0 10px; font-weight:600; letter-spacing:.18em;
  font-family:"Hiragino Kaku Gothic ProN",sans-serif; font-size:14px; }}
.t-chapter {{ margin:14px 0 6px; color:var(--accent); font-size:12.5px;
  letter-spacing:.1em; padding-left:2px; }}
.t-lesson a {{ display:flex; gap:14px; text-decoration:none; color:var(--ink);
  padding:3px 0 3px 16px; font-size:13.5px; }}
.t-lesson a:hover {{ background:var(--tint); }}
.t-no {{ color:var(--sub); font-size:11.5px; min-width:56px; letter-spacing:.06em; }}

/* 学年扉 */
.divider {{ margin:72px -56px 40px; padding:56px 56px; background:var(--tint);
  border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
.divider-en {{ margin:0; color:var(--accent); letter-spacing:.4em; font-size:11px;
  font-family:"Hiragino Kaku Gothic ProN",sans-serif; }}
.divider h2 {{ margin:6px 0 0; font-size:28px; letter-spacing:.2em; font-weight:600; }}

/* 回 */
.lesson {{ margin:0 0 46px; }}
.lesson-head {{ display:flex; align-items:baseline; gap:12px; margin:38px 0 18px;
  padding-bottom:9px; border-bottom:2px solid var(--rule); }}
.lesson-no {{ background:var(--rule); color:#fff; font-size:11.5px; letter-spacing:.1em;
  padding:3px 9px; white-space:nowrap; }}
.lesson-head h3 {{ margin:0; font-size:19px; letter-spacing:.06em; font-weight:600; }}
.lesson-chapter {{ margin-left:auto; color:var(--sub); font-size:11.5px; }}

/* 問題 */
.q {{ margin:0 0 26px; padding:0 0 6px; page-break-inside:avoid; }}
.q-head {{ display:flex; align-items:center; gap:8px; margin-bottom:7px; }}
.q-no {{ min-width:26px; height:26px; border-radius:50%; background:var(--rule);
  color:#fff; font-size:12.5px; display:grid; place-items:center; }}
.q-tag {{ font-size:10.5px; letter-spacing:.08em; color:var(--accent);
  border:1px solid currentColor; padding:1px 6px;
  font-family:"Hiragino Kaku Gothic ProN",sans-serif; }}
.q-lv {{ font-size:10.5px; color:var(--sub); letter-spacing:.06em; }}
.q-body {{ padding-left:34px; }}
.q-body p {{ margin:.35em 0; }}
.q-ask {{ margin-top:.5em !important; }}
.fig {{ padding-left:34px; margin:10px 0; }}
.fig svg {{ max-width:340px; height:auto; }}
.q-space {{ margin-left:34px; border-left:1px solid var(--line); }}

/* 解答編 */
.answers {{ margin-top:90px; padding-top:52px; border-top:3px double var(--rule);
  page-break-before:always; }}
.answers > h2 {{ font-size:22px; letter-spacing:.3em; margin:0 0 8px; }}
.answers > .lead {{ color:var(--sub); font-size:12px; margin:0 0 34px; }}
.a-lesson {{ margin:0 0 30px; }}
.a-lesson h3 {{ font-size:14px; margin:26px 0 12px; padding-bottom:6px;
  border-bottom:1px solid var(--line); letter-spacing:.06em; }}
.a-no {{ color:var(--sub); font-size:11px; margin-right:10px; }}
.a-item {{ display:grid; grid-template-columns:34px 1fr; gap:0 10px;
  margin:0 0 16px; page-break-inside:avoid; }}
.a-head {{ display:flex; flex-direction:column; align-items:center; gap:4px; }}
.a-num {{ min-width:24px; height:24px; border-radius:50%; border:1px solid var(--rule);
  font-size:12px; display:grid; place-items:center; }}
.a-back {{ font-size:9px; color:var(--sub); text-decoration:none; letter-spacing:.04em; }}
.a-ans {{ grid-column:2; }}
.ans-main {{ margin:0 0 6px; font-weight:600; }}
.a-sol {{ grid-column:2; color:#333; font-size:13.5px; line-height:1.8; }}
.a-sol p {{ margin:.2em 0; }}
.a-hint {{ grid-column:2; margin-top:5px; font-size:12px; color:var(--sub); }}
.a-hint ul {{ margin:.3em 0; padding-left:1.2em; }}

@media print {{
  body {{ background:#fff; }}
  .sheet {{ box-shadow:none; max-width:none; padding:0 14mm; }}
  .divider, .answers {{ page-break-before:always; }}
  .toc {{ page-break-after:always; }}
  a {{ color:inherit; text-decoration:none; }}
}}
@media (max-width:720px) {{
  .sheet {{ padding:0 20px 60px; }}
  .divider {{ margin-left:-20px; margin-right:-20px; padding:40px 20px; }}
}}
</style></head>
<body><div class="sheet">

<div class="cover">
  <h1>中学数学 問題集</h1>
  <p class="sub">MONGENE ENGINE</p>
  <p class="stat">全 {n_q} 問 ／ {n_units} 単元 ／ 図 {n_figs} 点</p>
</div>

<nav class="toc"><h2>目 次</h2><ul>
{toc}
</ul></nav>

{body}

<section class="answers">
  <h2>解答・解説</h2>
  <p class="lead">問題番号に対応しています。まず自分で解いてから読んでください。</p>
  {answers}
</section>

</div></body></html>
"""


if __name__ == "__main__":
    main()
