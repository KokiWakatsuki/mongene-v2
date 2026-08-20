"""INDEX.md を 中1 → 中2 → 中3 → 入試 の順に並べ替える。

生成し直さない（内容は正しく、順番だけの問題）。節は `## <unit>.<form>.Lv<n>` で
始まるので、そこで切って並べ替える。

実行: .venv/bin/python records/work/reorder_corpus.py
"""
from __future__ import annotations

import re
from pathlib import Path

_PATH = Path("records/work/corpus/INDEX.md")

# 学年の並び。exam（入試対策）は最後。
_GRADE_ORDER = {"g1": 0, "g2": 1, "g3": 2, "exam": 3}
_GRADE_LABEL = {"g1": "中学1年", "g2": "中学2年", "g3": "中学3年", "exam": "入試対策"}
# form の並び（教科書の並びに寄せる）。
_FORM_ORDER = {
    "knowledge": 0, "calculation": 1, "find_value": 2, "graph_table": 3,
    "construction": 4, "proof": 5, "word_problem": 6,
}


def sort_key(heading: str) -> tuple:
    """`## g2_l40.proof.Lv3  — 型 3 個` から並べ替えの鍵を作る。"""
    m = re.match(r"##\s+(exam|g[123])_l(\d+)\.(\w+)\.Lv(\d+)", heading)
    if not m:
        return (99, 999, 99, 99)
    grade, lesson, form, level = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
    return (_GRADE_ORDER.get(grade, 9), lesson, _FORM_ORDER.get(form, 9), level)


def main() -> None:
    text = _PATH.read_text(encoding="utf-8")
    # 節の区切りは "---\n\n## " （build_corpus.py がこの形で書いている）。
    parts = text.split("\n---\n")
    head, sections = parts[0], parts[1:]

    def heading_of(sec: str) -> str:
        for line in sec.splitlines():
            if line.startswith("## "):
                return line
        return ""

    sections.sort(key=lambda s: sort_key(heading_of(s)))

    # 学年が変わるところに見出しを立てる。
    out = [head.rstrip(), ""]
    current = None
    for sec in sections:
        grade = (re.match(r"##\s+(exam|g[123])_", heading_of(sec)) or [None, None])[1]
        if grade != current:
            current = grade
            out.append(f"\n# {_GRADE_LABEL.get(grade, grade)}\n")
        out.append("---\n" + sec.strip("\n"))
    _PATH.write_text("\n".join(out) + "\n", encoding="utf-8")

    order = [heading_of(s).removeprefix("## ").split()[0] for s in sections]
    print(f"{len(sections)} 節を並べ替えた。")
    print("先頭:", order[:4])
    print("末尾:", order[-4:])


if __name__ == "__main__":
    main()
