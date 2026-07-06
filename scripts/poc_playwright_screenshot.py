import asyncio
from playwright.async_api import async_playwright
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 広告ブロックを簡易的に設定
        context = await browser.new_context()
        await context.route("**/*", lambda route: route.abort() if "google" in route.request.url or "ads" in route.request.url else route.continue_())
        
        page = await context.new_page()
        
        url = "https://happylilac.net/jhs-math1-01.html"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")
        
        print("Looking for problem links...")
        target_link = page.locator("a:has(img[alt*='問題プリント'])").first
        
        output_path = ROOT_DIR / "tests" / "fixtures" / "real_problems" / "g1_l1" / "word_problem_min.png"
        
        if await target_link.count() > 0:
            href = await target_link.get_attribute("href")
            # 相対パス対策
            if href.startswith("/"):
                href = "https://happylilac.net" + href
            elif not href.startswith("http"):
                href = "https://happylilac.net/" + href

            print(f"Found link: {href}. Navigating directly to avoid ads...")
            await page.goto(href, wait_until="networkidle")
            
            print(f"Navigated to details page: {page.url}")
            
            # 詳細ページの中で PDF を探す
            pdf_link = page.locator("a[href$='.pdf']").first
            if await pdf_link.count() > 0:
                pdf_href = await pdf_link.get_attribute("href")
                if not pdf_href.startswith("http"):
                    pdf_href = "https://happylilac.net/" + pdf_href.lstrip("/")
                
                print(f"Found PDF link: {pdf_href}. Downloading PDF...")
                
                # PlaywrightのAPIを使ってPDFをダウンロード（クッキーやヘッダを引き継ぐ）
                response = await page.request.get(pdf_href)
                pdf_bytes = await response.body()
                
                # PDFを画像に変換
                import fitz # PyMuPDF
                print("Converting PDF to image...")
                doc = fitz.open("pdf", pdf_bytes)
                page_obj = doc.load_page(0) # 1ページ目
                pix = page_obj.get_pixmap(dpi=150) # 高画質で変換
                pix.save(str(output_path))
                print(f"Saved PDF 1st page as image to {output_path}")
                
            else:
                # PDFリンクがなければ、現在見えている大きな画像をスクショする
                print("No PDF link found. Taking full page screenshot...")
                await page.wait_for_timeout(3000)
                await page.screenshot(path=str(output_path), full_page=True)
                print(f"Saved problem page screenshot to {output_path}")
        else:
            print("Target link not found.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
