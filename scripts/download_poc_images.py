import os
import urllib.request
import csv
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "tests" / "fixtures" / "real_problems"
PROGRESS_CSV = ROOT_DIR / "reports" / "problem_collection_progress.csv"

# PoC用のダミーURL（実際のサイトのサムネイル等のURLを想定）
# 本来はスクレイピングや検索で取得するが、今回はPoCとしていくつかの実際のフリー教材の画像URLを指定
POC_IMAGES = {
    "g1_l1": {
        "word_problem_min": "https://happylilac.net/thumb/mat-c1-01-01.png",
        "word_problem_mid": "https://happylilac.net/thumb/mat-c1-01-02.png",
        "word_problem_max": "https://happylilac.net/thumb/mat-c1-01-03.png",
        "knowledge_min": "https://happylilac.net/thumb/mat-c1-01-04.png",
        "knowledge_mid": "https://happylilac.net/thumb/mat-c1-01-05.png",
        "knowledge_max": "https://happylilac.net/thumb/mat-c1-01-06.png"
    },
    "g1_l2": {
        "calculation_min": "https://happylilac.net/thumb/mat-c1-02-01.png",
        "calculation_mid": "https://happylilac.net/thumb/mat-c1-02-02.png",
        "calculation_max": "https://happylilac.net/thumb/mat-c1-02-03.png",
        "knowledge_min": "https://happylilac.net/thumb/mat-c1-02-04.png",
        "knowledge_mid": "https://happylilac.net/thumb/mat-c1-02-05.png",
        "knowledge_max": "https://happylilac.net/thumb/mat-c1-02-06.png",
        "visual_min": "https://happylilac.net/thumb/mat-c1-02-07.png",
        "visual_mid": "https://happylilac.net/thumb/mat-c1-02-08.png",
        "visual_max": "https://happylilac.net/thumb/mat-c1-02-09.png"
    },
    "g1_l3": {
        "calculation_min": "https://happylilac.net/thumb/mat-c1-03-01.png",
        "calculation_mid": "https://happylilac.net/thumb/mat-c1-03-02.png",
        "calculation_max": "https://happylilac.net/thumb/mat-c1-03-03.png"
    }
}

def download_images():
    # 既存の進捗を読み込む
    rows = []
    with open(PROGRESS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    updated_count = 0
    
    for lesson_id, forms in POC_IMAGES.items():
        lesson_dir = OUTPUT_DIR / lesson_id
        os.makedirs(lesson_dir, exist_ok=True)
        
        for form_diff, url in forms.items():
            form, diff = form_diff.rsplit("_", 1)
            filename = f"{form}_{diff}.png"
            filepath = lesson_dir / filename
            
            try:
                print(f"Downloading {url} to {filepath}...")
                # Download image
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(filepath, 'wb') as out_file:
                    data = response.read()
                    out_file.write(data)
                
                # 進捗シートの更新
                for row in rows:
                    if row["lesson_id"] == lesson_id and row["problem_form"] == form and row["difficulty"] == diff:
                        row["status"] = "完了"
                        row["image_path"] = str(filepath.relative_to(ROOT_DIR))
                        row["source_url"] = url
                        updated_count += 1
                        break
            except Exception as e:
                print(f"Failed to download {url}: {e}")

    # 進捗を保存
    with open(PROGRESS_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lesson_id", "problem_form", "difficulty", "status", "image_path", "source_url"])
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Updated {updated_count} rows in progress sheet.")

if __name__ == "__main__":
    download_images()
