import csv
import os
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT_DIR / "reports" / "forms_research.csv"
OUTPUT_CSV = ROOT_DIR / "reports" / "problem_collection_progress.csv"

def init_progress_csv():
    # 5つの問題形式
    forms = ["calculation", "word_problem", "proof", "knowledge", "visual"]
    difficulties = ["min", "mid", "max"]
    
    rows = []
    
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lesson_id = row.get("lesson_id")
            if not lesson_id:
                continue
                
            # 有効な問題形式（値が "1" のもの）を抽出
            active_forms = [form for form in forms if row.get(form) == "1"]
            
            for form in active_forms:
                for diff in difficulties:
                    rows.append({
                        "lesson_id": lesson_id,
                        "problem_form": form,
                        "difficulty": diff,
                        "status": "未着手",
                        "image_path": "",
                        "source_url": ""
                    })
                    
    # 出力
    os.makedirs(OUTPUT_CSV.parent, exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lesson_id", "problem_form", "difficulty", "status", "image_path", "source_url"])
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Generated {len(rows)} tasks in {OUTPUT_CSV}")

if __name__ == "__main__":
    init_progress_csv()
