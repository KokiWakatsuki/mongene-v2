import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = "https://happylilac.net/jhs-math1-01.html"
        await page.goto(url, wait_until="networkidle")
        
        print("--- All Images ---")
        images = await page.locator("img").all()
        for i, img in enumerate(images):
            src = await img.get_attribute("src")
            alt = await img.get_attribute("alt")
            width = await img.evaluate("node => node.width")
            height = await img.evaluate("node => node.height")
            if width > 100 and height > 100: # 小さいアイコンを除外
                print(f"[{i}] src={src}, alt={alt}, size={width}x{height}")
        
        print("\n--- PDF Links ---")
        links = await page.locator("a[href$='.pdf']").all()
        for i, link in enumerate(links):
            href = await link.get_attribute("href")
            text = await link.inner_text()
            print(f"[{i}] text='{text.strip()}', href={href}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
