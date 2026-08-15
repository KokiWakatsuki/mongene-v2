"""実物の**解説**を、系統を散らして取ってくる。

## なぜ散らすか

表記の調査（`ref_conventions.py`）で学んだこと——**1系統だけ見ると、その系統の癖を
「一般的な慣習」だと錯覚する。** 最初に NIER 1件だけを見て「公的資料は100%敬体」と
結論し、4年度に広げたら70%、練習系まで広げたら0%の系統が出た。

解説でも同じ罠がある。手元にあったのは教育委員会のプリント4件だけで、
これは「学校が配る補充プリント」の癖しか映さない。塾・解説サイト・教科書会社を
足して、**系統をまたいで共通するものだけ**を規範にする。

## 取るもの・取らないもの

取るのは**構成の頻度**（理由を書くか・途中式を何行出すか・別解を出すか）。
問題文や解説の文そのものは他社の著作物なので**追跡しない**（`.gitignore` 済み）。
慣習は事実であって著作物ではない。

実行: .venv/bin/python records/work/ref_collect.py
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

_REF = Path("records/work/ref")

# (保存名, URL)。接頭辞が系統になる（ref_conventions._LINEAGE と揃える）。
_PAGES: list[tuple[str, str]] = [
    ("juku_sukyo_kaisetsu", "https://sukyojuku.com/tangen-ichiji-hoteishiki/"),
    ("juku_005net_yoten", "https://math.005net.com/yoten/houte.php"),
    ("juku_frontiesta_kaisetsu", "https://frontiesta.com/linear-equation/"),
    ("juku_ways_kaisetsu", "https://ways-sch.jp/junior-high/57525"),
    ("juku_benesse_kaisetsu", "https://kou.benesse.co.jp/nigate/math/a15m0065.html"),
]

_PDFS: list[tuple[str, str]] = [
    ("kyoiku_tokushima_step", "https://school.e-tokushima.or.jp/file/attachment/1249126.pdf"),
]

_STRIP = re.compile(r"(?is)<(script|style|nav|footer|header|noscript)[^>]*>.*?</\1>")
_TAG = re.compile(r"(?s)<[^>]+>")


def _fetch(url: str) -> bytes | None:
    r = subprocess.run(
        ["curl", "-sL", "--max-time", "40", "-A", "Mozilla/5.0", url],
        capture_output=True,
    )
    return r.stdout if r.returncode == 0 and r.stdout else None


def main() -> int:
    _REF.mkdir(parents=True, exist_ok=True)
    for name, url in _PAGES:
        raw = _fetch(url)
        if not raw:
            print(f"  × {name}")
            continue
        t = raw.decode("utf-8", errors="ignore")
        t = html.unescape(_TAG.sub(" ", _STRIP.sub(" ", t)))
        t = re.sub(r"[ \t\xa0]+", " ", t)
        (_REF / f"{name}.txt").write_text(t, encoding="utf-8")
        print(f"  ✓ {name:<28}{len(t):>8} 字")

    for name, url in _PDFS:
        raw = _fetch(url)
        if not raw:
            print(f"  × {name}")
            continue
        pdf = _REF / f"{name}.pdf"
        pdf.write_bytes(raw)
        subprocess.run(["pdftotext", "-layout", str(pdf), str(_REF / f"{name}.txt")])
        print(f"  ✓ {name:<28}{len((_REF / f'{name}.txt').read_text(encoding='utf-8')):>8} 字")
    return 0


if __name__ == "__main__":
    sys.exit(main())
