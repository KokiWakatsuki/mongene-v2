import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from playwright.async_api import async_playwright

ROOT_DIR = Path(__file__).resolve().parent.parent
PROGRESS_CSV = ROOT_DIR / "reports" / "problem_collection_progress.csv"
URL_MAPPING = ROOT_DIR / "reports" / "url_mapping.json"
OUTPUT_DIR = ROOT_DIR / "tests" / "fixtures" / "real_problems"

async def process_task(task, mapping, context, rows):
    lesson_id = task["lesson_id"]
    form = task["problem_form"]
    diff = task["difficulty"]
    
    url = mapping.get(lesson_id)
    if not url:
        print(f"[{lesson_id} - {form}_{diff}] Skip: No URL mapped.")
        task["status"] = "スキップ(URLなし)"
        return
        
    output_path = OUTPUT_DIR / lesson_id / f"{form}_{diff}.png"
    os.makedirs(output_path.parent, exist_ok=True)
    
    # 既に画像が存在する場合は完了扱いにする
    if output_path.exists() and task["status"] != "完了":
        task["status"] = "完了"
        task["image_path"] = str(output_path.relative_to(ROOT_DIR))
        return

    print(f"[{lesson_id} - {form}_{diff}] Processing: {url}")
    
    page = None
    try:
        page = await context.new_page()
        # タイムアウトを少し長めに設定
        page.set_default_timeout(30000)
        
        await page.goto(url, wait_until="domcontentloaded")
        
        # 広告を回避するため、ページ内のリンクを探して直接飛ぶ (PoCのロジック)
        pdf_href = None
        
        # 1. 直接PDFリンクがないか探す
        pdf_link = page.locator("a[href$='.pdf']").first
        if await pdf_link.count() > 0:
            pdf_href = await pdf_link.get_attribute("href")
        else:
            # 2. 問題プリントへのリンクを探してさらに遷移
            target_link = page.locator("a:has(img[alt*='問題プリント'])").first
            if await target_link.count() > 0:
                href = await target_link.get_attribute("href")
                if href.startswith("/"): href = "https://happylilac.net" + href
                elif not href.startswith("http"): href = "https://happylilac.net/" + href
                
                await page.goto(href, wait_until="domcontentloaded")
                
                # 詳細ページ内でPDFを探す
                pdf_link = page.locator("a[href$='.pdf']").first
                if await pdf_link.count() > 0:
                    pdf_href = await pdf_link.get_attribute("href")
        
        if pdf_href:
            if not pdf_href.startswith("http"):
                pdf_href = "https://happylilac.net/" + pdf_href.lstrip("/")
            
            print(f"  -> Found PDF: {pdf_href}. Downloading...")
            response = await page.request.get(pdf_href)
            pdf_bytes = await response.body()
            
            # PDFからPNGへ変換
            import fitz
            doc = fitz.open("pdf", pdf_bytes)
            page_obj = doc.load_page(0)
            # 問題形式・難易度に応じてページや切り取りを変えることも可能だが、今回は一律1ページ目を保存
            pix = page_obj.get_pixmap(dpi=150)
            pix.save(str(output_path))
            print(f"  -> Saved to {output_path}")
            
            task["status"] = "完了"
            task["image_path"] = str(output_path.relative_to(ROOT_DIR))
            task["source_url"] = pdf_href
            
        else:
            print(f"  -> Warning: No PDF found. Taking fallback screenshot.")
            await page.wait_for_timeout(2000)
            await page.screenshot(path=str(output_path), full_page=True)
            
            task["status"] = "完了(スクショ)"
            task["image_path"] = str(output_path.relative_to(ROOT_DIR))
            task["source_url"] = url
            
    except Exception as e:
        print(f"  -> Error: {e}")
        task["status"] = f"エラー"
        
    finally:
        if page:
            await page.close()


async def main():
    if not URL_MAPPING.exists():
        print("Error: url_mapping.json not found.")
        sys.exit(1)
        
    with open(URL_MAPPING, "r", encoding="utf-8") as f:
        mapping = json.load(f)

    # 進捗の読み込み
    rows = []
    with open(PROGRESS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
            
    tasks_to_do = [r for r in rows if r["status"] == "未着手"]
    print(f"Total tasks remaining: {len(tasks_to_do)}")
    
    if not tasks_to_do:
        return

    # CSV保存用ヘルパー
    def save_progress():
        with open(PROGRESS_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["lesson_id", "problem_form", "difficulty", "status", "image_path", "source_url"])
            writer.writeheader()
            writer.writerows(rows)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        # 広告ブロック
        await context.route("**/*", lambda route: route.abort() if "google" in route.request.url or "ads" in route.request.url else route.continue_())
        
        for i, task in enumerate(tasks_to_do):
            await process_task(task, mapping, context, rows)
            
            # 1件ごとに進捗を保存（強制終了に備える）
            save_progress()
            
            # 少し待機
            await asyncio.sleep(1)
            
        await browser.close()
        
    print("All tasks processed.")

if __name__ == "__main__":
    asyncio.run(main())
