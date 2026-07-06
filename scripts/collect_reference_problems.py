"""
参照問題画像収集スクリプト
startoo.co から基礎・標準・発展 PDF をダウンロードし、1問ずつ切り抜いた画像を保存する。
"""

import csv
import os
import urllib.request
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image, ImageFilter
import numpy as np

# ===== 設定 =====
OUTPUT_DIR = Path("reports/reference_problems")
PDF_CACHE_DIR = Path("/tmp/math_pdfs")
PDF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# startoo.co 単元マッピング
# CSV の大単元 → (学年, unit番号)
UNIT_MAP = {
    # Grade 1
    "正の数・負の数":     (1, 1),
    "文字の式":          (1, 2),
    "一次方程式":        (1, 3),
    "比例と反比例":      (1, 4),
    "平面図形":          (1, 5),
    "空間図形":          (1, 6),
    "資料の活用":        (1, 7),
    # Grade 2
    "式の計算":          (2, 1),
    "連立方程式":        (2, 2),
    "一次関数":          (2, 3),
    "平行と合同":        (2, 5),
    "三角形・四角形":    (2, 6),
    "確率":              (2, 7),
    "図形の証明":        (2, 10),
    "データの活用":      (2, 11),
}

DIFFICULTY_MAP = {
    "min": "basic",
    "mid": "standard",
    "max": "advanced",
}

# ===== レッスン固有の問題ソース =====
# broad unit PDF では内容が合わないケースの override
# キー: (lesson_id, form)  値: 難易度ごとの (pdf_url, crop_box(x0,y0,x1,y1))
# crop_box は None のとき PDF 全ページを使う
LESSON_OVERRIDES: dict[tuple[str, str], dict] = {
    # g1_l2「数直線と絶対値、数の大小」
    # Unit1 PDF は加法問題が出てしまうため長野県レビュー問題PDFを使用
    ("g1_l2", "calculation"): {
        "min": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 160, 1241, 545)),   # 大問1: 絶対値・数の大小
        "mid": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 160, 1241, 545)),
        "max": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 1160, 1241, 1500)),  # 大問3: 複雑な順番並べ
    },
    ("g1_l2", "visual"): {
        "min": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 730, 1241, 1165)),  # 大問2: 数直線図
        "mid": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 730, 1241, 1165)),
        "max": ("https://www.edu-ctr.pref.nagano.lg.jp/kjouhou/manabi-hiroba"
                "/05_review_mondai/mondai/s_re_chu1_01_13.pdf",
                (0, 730, 1241, 1165)),
    },
    # g1_l24「比例式とその解き方」
    # Unit3 PDF の文章題は一般方程式で比例式ではないため happylilac の比例式PDFを使用
    ("g1_l24", "word_problem"): {
        "min": ("https://happylilac.net/jhs-math1_03-02-03.pdf",
                (0, 0, 1240, 350)),   # 大問1: 比例式の計算
        "mid": ("https://happylilac.net/jhs-math1_03-02-05.pdf",
                (0, 380, 1240, 590)), # 大問2: 比例式文章題（3:2に分ける）
        "max": ("https://happylilac.net/jhs-math1_03-02-05.pdf",
                (0, 590, 1240, 800)), # 大問3: 速さ系の比例式応用
    },
}


def get_pdf_url(grade: int, unit: int, difficulty: str) -> str:
    nn = f"{unit:02d}"
    level = DIFFICULTY_MAP[difficulty]
    return f"https://startoo.co/wp-content/uploads/2026/03/chu{grade}-math-unit{nn}-{level}.pdf"


def download_pdf(url: str, dest: Path) -> bool:
    if dest.exists():
        return True
    try:
        urllib.request.urlretrieve(url, str(dest))
        return True
    except Exception as e:
        print(f"  [ERR] Download failed: {e}")
        return False


def detect_section_starts(img_array: np.ndarray) -> list[int]:
    """
    PDF 画像内のセクションヘッダー（青帯）の開始 y 座標を検出する。
    主ヘッダー（y<200）はスキップして問題セクションのみ返す。
    """
    gray = np.mean(img_array, axis=(1, 2))
    h = len(gray)

    starts = []
    in_dark = False
    band_start = 0
    for y in range(200, h - 10):
        v = gray[y]
        if v < 180 and not in_dark:
            in_dark = True
            band_start = y
        elif v >= 180 and in_dark:
            in_dark = False
            band_h = y - band_start
            # セクションヘッダーは 20px 以上の帯
            if band_h >= 20:
                starts.append(band_start)

    return starts


# 各 form → 使用するセクションインデックス（0=計算, 1=文章題, 2=選択）
FORM_TO_SECTION = {
    "calculation": 0,
    "visual":      0,
    "word_problem": 1,
    "proof":       1,
    "knowledge":   2,
}

# セクションごとの最初の問題を切り抜く高さ（px）
SECTION_CROP_HEIGHT = {
    0: 240,   # 計算問題: ヘッダー + 問題1行 (2問並列)
    1: 210,   # 文章題: ヘッダー + 問題1問
    2: 230,   # 選択問題: ヘッダー + 問題1問
}


def crop_first_problem(img: Image.Image, section_idx: int) -> Image.Image:
    """
    指定セクションの最初の問題を切り抜く。
    """
    arr = np.array(img)
    starts = detect_section_starts(arr)

    if not starts or section_idx >= len(starts):
        # フォールバック: 画像上部 35% を返す
        return img.crop((0, 0, img.width, int(img.height * 0.35)))

    y_start = starts[section_idx]
    crop_h = SECTION_CROP_HEIGHT.get(section_idx, 230)
    y_end = min(y_start + crop_h, img.height)

    return img.crop((0, y_start, img.width, y_end))


def collect_problem_image(
    lesson_id: str,
    unit_name: str,
    form: str,
    difficulty: str,
) -> Path | None:
    """
    1件の問題画像を取得して保存する。
    lesson-specific override があればそちらを優先する。
    """
    out_name = f"{lesson_id}_{form}_{difficulty}.png"
    out_path = OUTPUT_DIR / out_name

    override_key = (lesson_id, form)

    # ===== Override: レッスン固有ソースを使う =====
    if override_key in LESSON_OVERRIDES:
        override = LESSON_OVERRIDES[override_key][difficulty]
        pdf_url, crop_box = override
        pdf_name = pdf_url.split("/")[-1]
        pdf_path = PDF_CACHE_DIR / pdf_name
        print(f"  [OVERRIDE] PDF: {pdf_url}")
        if not download_pdf(pdf_url, pdf_path):
            return None
        pages = convert_from_path(str(pdf_path), dpi=150)
        page_img = pages[0]
        if crop_box:
            x0, y0, x1, y1 = crop_box
            # 画像サイズに合わせてクランプ
            x1 = min(x1, page_img.width)
            y1 = min(y1, page_img.height)
            cropped = page_img.crop((x0, y0, x1, y1))
        else:
            cropped = page_img
        cropped.save(str(out_path))
        return out_path

    # ===== 通常パス: startoo.co 単元 PDF =====
    if unit_name not in UNIT_MAP:
        print(f"  [SKIP] unit_name not mapped: {unit_name}")
        return None

    grade, unit_no = UNIT_MAP[unit_name]
    url = get_pdf_url(grade, unit_no, difficulty)

    level = DIFFICULTY_MAP[difficulty]
    pdf_name = f"chu{grade}-math-unit{unit_no:02d}-{level}.pdf"
    pdf_path = PDF_CACHE_DIR / pdf_name

    print(f"  PDF: {url}")
    if not download_pdf(url, pdf_path):
        return None

    pages = convert_from_path(str(pdf_path), dpi=150)
    page_img = pages[0]

    raw_idx = FORM_TO_SECTION.get(form, 0)
    cropped = crop_first_problem(page_img, raw_idx)

    cropped.save(str(out_path))
    return out_path


# ===== テスト実行 =====
if __name__ == "__main__":
    # CSV から 10 件を選択
    with open("reports/forms_research.csv") as f:
        rows = list(csv.DictReader(f))

    form_cols = ["calculation", "word_problem", "proof", "knowledge", "visual"]
    test_cases = []
    seen = set()

    for row in rows:
        grade = int(row["学年"])
        if grade > 2:
            continue
        for form in form_cols:
            if row[form] == "1":
                key = (grade, row["大単元"], form)
                if key not in seen:
                    seen.add(key)
                    test_cases.append({
                        "lesson_id": row["lesson_id"],
                        "title": row["タイトル"],
                        "unit": row["大単元"],
                        "form": form,
                    })
            if len(test_cases) >= 10:
                break
        if len(test_cases) >= 10:
            break

    print(f"テストケース数: {len(test_cases)}")
    print()

    results = []
    for tc in test_cases:
        for diff in ["min", "mid", "max"]:
            print(f"[{tc['lesson_id']}] {tc['title']} | form={tc['form']} | diff={diff}")
            out = collect_problem_image(
                lesson_id=tc["lesson_id"],
                unit_name=tc["unit"],
                form=tc["form"],
                difficulty=diff,
            )
            status = "OK" if out else "FAILED"
            print(f"  -> {status}: {out}")
            results.append({
                "lesson_id": tc["lesson_id"],
                "form": tc["form"],
                "difficulty": diff,
                "status": status,
                "path": str(out) if out else "",
            })

    ok = sum(1 for r in results if r["status"] == "OK")
    total = len(results)
    print(f"\n=== 結果: {ok}/{total} 成功 ===")

    # CSV に保存
    out_csv = Path("reports/problem_collection_test.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["lesson_id", "form", "difficulty", "status", "path"])
        w.writeheader()
        w.writerows(results)
    print(f"結果: {out_csv}")
