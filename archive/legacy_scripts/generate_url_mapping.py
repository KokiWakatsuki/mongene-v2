import csv
import json
import time
from pathlib import Path
from duckduckgo_search import DDGS

ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_CSV = ROOT_DIR / "reports" / "forms_research.csv"
OUTPUT_JSON = ROOT_DIR / "reports" / "url_mapping.json"

def generate_mapping():
    mapping = {}
    
    # 既存のマッピングがあれば読み込む（途中再開用）
    if OUTPUT_JSON.exists():
        with open(OUTPUT_JSON, "r", encoding="utf-8") as f:
            mapping = json.load(f)

    # lesson_id ごとの重複を防ぐため、一意なレッスンを抽出
    lessons = []
    with open(INPUT_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lesson_id = row.get("lesson_id")
            if not lesson_id or lesson_id in mapping:
                continue
            lessons.append(row)

    print(f"Total remaining lessons to search: {len(lessons)}")
    
    # 検索実行
    with DDGS() as ddgs:
        for i, row in enumerate(lessons):
            lesson_id = row["lesson_id"]
            grade = row["学年"]
            unit = row["大単元"]
            title = row["タイトル"]
            
            # クエリの作成 (ちびむすドリル内で検索)
            # 例: site:happylilac.net 中学 数学 1年 正の数・負の数 加法
            query = f"site:happylilac.net 中学 数学 {grade}年 {unit} {title}"
            
            print(f"[{i+1}/{len(lessons)}] Searching: {query}")
            try:
                results = list(ddgs.text(query, max_results=1))
                if results:
                    url = results[0].get("href")
                    mapping[lesson_id] = url
                    print(f" -> Found: {url}")
                else:
                    mapping[lesson_id] = None
                    print(" -> Not found")
            except Exception as e:
                print(f" -> Error: {e}")
                # レートリミット対策で長めに待機
                time.sleep(10)
                continue
            
            # 頻繁なリクエストによるブロックを避けるための待機
            time.sleep(1.5)
            
            # 10件ごとに保存
            if (i + 1) % 10 == 0:
                with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                    
    # 最終保存
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    
    print(f"Finished mapping. Saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    generate_mapping()
